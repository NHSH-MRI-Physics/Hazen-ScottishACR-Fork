# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 14:15:35 2020

@author: Paul Wilson

Overview
========
	1. Import list of DICOM files. The Caliber (HPD) system phantom should be
        scanned https://qmri.com/system-phantom/. 
        TODO: add protocol details.
	2. Create container object / array (all-slices) containing:
        a. Target images (to be ordered by TE or TI). Should be same position on same phantom, different TE or TI
		b. Transformation matrix to map template image spcae to target image space
        c. List of coordinates of centres of each sphere in template image (to enable ROI generation)
	3. Image alignment-generate RT (rotation - translation) transformation matrix
        fitting a Euclidean transformation.
		a. Poss use https://www.learnopencv.com/image-alignment-ecc-in-opencv-c-python/ , https://alexanderpacha.com/2018/01/29/aligning-images-an-engineers-solution/
		b. Generate coordinates of sphere centres by transforming list of coordinates from template.
			i. CHECK-Display image with overlays showing sampling locations AND mounting pins / coffin (to check alignment).
        c. Create mask for each sphere by placing structuring element (e.g. binary disk, diameter=?5px) centred on taget sphere coordinates.
            i. CHECK-overlay contour map on target image.
	4. For each sphere:
		a. Find array of mean PVs foreach slice.
			i. CHK--is max/min range too big--indicates poor position localisation
		b. Fit array to decay curve.
			i. Use different fitting algorithm for T1, T2. CHK sampling is relevant--i.e. different TIs, TEs at each slice.
		c. Numeric and graphical output. Poss include known values if available.


TODO
====

Sort images by TE or TI.



FEATURE ENHANCEMENT
===================
Template fit on bolt holes--possibly better with large rotation angles and faster
    -have bolthole template, find 3 positions in template and image, figure out
    transformation.

"""
import pydicom
import cv2 as cv
import numpy as np
import matplotlib.pyplot as plt
import os
import skimage.morphology
import scipy.ndimage

# import hazenlib


def outline_mask(im):
    """Create contour lines to outline pixels."""
    # Adapted from https://stackoverflow.com/questions/40892203/can-matplotlib-contours-match-pixel-edges
    lines = []
    pad = np.pad(im, [(1, 1), (1, 1)])  # zero padding

    im0 = np.abs(np.diff(pad, n=1, axis=0))[:, 1:]
    im1 = np.abs(np.diff(pad, n=1, axis=1))[1:, :]

    im0 = np.diff(im0, n=1, axis=1)
    starts = np.argwhere(im0 == 1)
    ends = np.argwhere(im0 == -1)
    lines += [([s[0]-.5, s[0]-.5], [s[1]+.5, e[1]+.5]) for s, e
              in zip(starts, ends)]

    im1 = np.diff(im1, n=1, axis=0).T
    starts = np.argwhere(im1 == 1)
    ends = np.argwhere(im1 == -1)
    lines += [([s[1]+.5, e[1]+.5], [s[0]-.5, s[0]-.5]) for s, e
              in zip(starts, ends)]

    return lines


def transform_coords(coords, rt_matrix, input_yx=True, output_yx=True):
    """
    Convert coordinates using RT transformation matrix.

    Note that arrays containing pixel information as displayed using
    plt.imshow(pixel_array), for example are referenced using the yx notation,
    e.g. pixel_array[y,x]. Plotting points or patches using matplotlib requires
    xy notation, e.g. plt.scatter(x,y). The correct input and output notation
    must be selected for the correct transformation.

    Parameters
    ----------
    coords : np.array or tuple
        Array (n,2) of coordinates to transform.
    rt_matrix : np.array
        Array (2,3) of transform matrix (Rotation and Translation). See e.g.
        cv2.transform() for details.
    input_yx : bool, optional
        Select the input coordinate format relative to the image.
        If True, input array has y-coordinate first, i.e.:
            [[y1,x1],
             [y2,x2],
             ...,
             [yn,xn]].
        If False, input array has x-coordinate first, i.e.:
            [[x1,y1],
             [x2,y2],
             ...,
             [xn,yn]].
        The default is True.
    output_yx : bool, optional
        Select the output coordinate order. If True, output matrix is in yx
        order, otherwise it is in xy order. The default is True.

    Returns
    -------
    out_coords : np.array
        Returns (n,2) array of transformed coordinates.

    """
    in_coords = np.array(coords)  # ensure using np array

    if input_yx:  # convert to xy format
        in_coords = np.flip(in_coords, axis=1)

    out_coords = cv.transform(np.array([in_coords]), rt_matrix)
    out_coords = out_coords[0]  # reduce to two dimensions

    if output_yx:
        out_coords = np.flip(out_coords, axis=1)

    return out_coords


def pixel_LUT(dcmfile):
    """Transforms pixel values according to LUT in DICOM header."""
    return pydicom.pixel_data_handlers.util.apply_modality_lut(
            dcmfile.pixel_array, dcmfile)


class ROITimeSeries():
    """"Pixel values for one image location at numerous sample times."""

    SAMPLE_ELEMENT = skimage.morphology.square(5)

    def __init__(self, dcm_images, poi_coords_yx,
                 time_attr=None, kernel=None):
        
        if kernel is None:
            kernel = self.SAMPLE_ELEMENT
        self.POI_mask = np.zeros((dcm_images[0].pixel_array.shape[0],
                                  dcm_images[0].pixel_array.shape[1]),
                                 dtype=np.int8)
        self.POI_mask[poi_coords_yx[0], poi_coords_yx[1]] = 1

        self.ROI_mask = np.zeros_like(self.POI_mask)
        self.ROI_mask = scipy.ndimage.filters.convolve(self.POI_mask, kernel)
        self._time_attr = time_attr
        
        if time_attr is not None:
            self.times = [x[time_attr].value.real for x in dcm_images]
        self.pixel_values = [
            pixel_LUT(img)[self.ROI_mask > 0] for img in dcm_images]
            
    
    def __len__(self):
        """Number of time samples in series."""
        return len(self.pixel_values)
    
    @property
    def means(self):
        """List of mean ROI values at different times."""
        return [np.mean(self.pixel_values[i]) for i in range(len(self))]


class ImageStack():
    """Object to hold image_slices and methods for T1, T2 calculation."""

    # TODO define in subclasses
    T1_sphere_centres = []
    T1_bolt_centres = []
    
    def __init__(self, image_slices, template_dcm, plate_number=None,
                 dicom_order_key=None):
        """
        Create ImageStack object.

        Parameters
        ----------
        image_slices : list of pydicom.FileDataSet objects
            List of pydicom objects to perform relaxometry analysis on.
        template_dcm : pydicom FileDataSet (or None)
            DICOM template object.
        plate_number : int {3,4,5}, optional
            For future use. Reference to the plate in the relaxometry phantom.
            The default is None.
        dicom_order_key : string, optional
            DICOM attribute to order images. Typically 'InversionTime' for T1
            relaxometry or 'EchoTime' for T2.

        Returns
        -------
        None.

        """
        # Store template pixel array, after LUT in 0028,1052 and 0028,1053
        # applied
        self.template_dcm = template_dcm
        if template_dcm is not None:
            self.template_px = pixel_LUT(template_dcm)
            
        self.dicom_order_key = dicom_order_key
        self.images = image_slices  # store images
        if dicom_order_key is not None:
            self.order_by(dicom_order_key)


    def template_fit(self, image_index=0):
        """
        Calculate transformation matrix to fit template to image.

        The template pixel array, self.template_px, is fitted to one of the
        images in self.images (default=0). The resultant RT matrix is stored as
        self.warp_matrix.

        This matrix can be used to map coordinates from template space to image
        space using transform_coords(...), or to map masks from template space
        to image space using cv2.warpAffine(...).

        To map from image space to template space, the 'inverse' RT matrix can
        be calculated using:
          inverse_transform_matrix = cv.invertAffineTransform(self.warp_matrix)

        Parameters
        ----------
        image_index : int, optional
            Index of image to be used for template matching. The default is 0.

        Returns
        -------
        warp_matrix : np.array
            RT transform matrix (2,3).

        Further details
        ---------------

        TODO
        ----
        This routine is suboptimal. It may be better to extract the bolt
        hole locations and fit from them, or run an edge-detection algorithm
        as pixel values are highly variable between scanners and manufacturers.

        Need to check if image is real valued, typically signed then shifted so
        background is 2048, or magnitude image. Currently it assumes magnitude
        image.

        """
        target_px = pixel_LUT(self.images[0])

        # Always fit on magnitude images for simplicity. May be suboptimal
        # TODO check for better solution
        self.template8bit = \
            cv.normalize(abs(self.template_px),
                         None, 0, 255, norm_type=cv.NORM_MINMAX,
                         dtype=cv.CV_8U)

        self.target8bit = cv.normalize(abs(target_px),
                                       None, 0, 255, norm_type=cv.NORM_MINMAX,
                                       dtype=cv.CV_8U)

        # initialise transofrmation fitting parameters.
        number_of_iterations = 500
        termination_eps = 1e-10
        criteria = (cv.TERM_CRITERIA_EPS | cv.TERM_CRITERIA_COUNT,
                    number_of_iterations, termination_eps)
        self.warp_matrix = np.eye(2, 3, dtype=np.float32)

        # Apply transformation
        self.template_cc, self.warp_matrix = \
            cv.findTransformECC(self.template8bit, self.target8bit,
                                self.warp_matrix, criteria=criteria)

        self.warped_template8bit = cv.warpAffine(self.template8bit,
                                                 self.warp_matrix,
                                                 (self.template8bit.shape[1],
                                                  self.template8bit.shape[0]))

        return self.warp_matrix

    def plot_fit(self):
        """
        Visual representation of target fitting.

        Create 2x2 subplot showing 8-bit version of:
            1. Template
            2. Original image
            3. Overlay of (1) and (2)
            4. Overlay of RT transformed template and (2)

        Returns
        -------
        None.

        TODO
        ----

        """
        plt.subplot(2, 2, 1)
        plt.imshow(self.template8bit, cmap='gray')
        plt.title('Template')
        plt.axis('off')

        plt.subplot(2, 2, 2)
        plt.imshow(self.target8bit, cmap='gray')
        plt.title('Image')
        plt.axis('off')
        if hasattr(self, 'ROI_time_series'):
            combined_ROI_map = np.zeros_like(self.ROI_time_series[0].ROI_mask)
            for roi in self.ROI_time_series:
                combined_ROI_map += roi.ROI_mask
            lines = outline_mask(combined_ROI_map)
            for line in lines:
                plt.plot(line[1], line[0], color='r', alpha=1)

        plt.subplot(2, 2, 3)
        plt.imshow(self.template8bit/2 + self.target8bit/2, cmap='gray')
        plt.title('Image / template overlay')
        plt.axis('off')

        plt.subplot(2, 2, 4)
        plt.imshow(self.warped_template8bit/2 + self.target8bit/2, cmap='gray')
        plt.title('Image / fitted template overlay')
        plt.axis('off')

        plt.tight_layout()

    def order_by(self, att):
        """Order images by attribute (e.g. EchoTime, InversionTime)."""
        self.images.sort(key=lambda x: x[att].value.real)
        
    def generate_time_series(self, coords_yx, fit_coords=True, 
                              kernel=None):
        """Create list of ROITimeSeries objects."""
        
        num_coords = np.size(coords_yx, axis=0)
        if fit_coords:
            coords_yx = transform_coords(coords_yx, self.warp_matrix,
                                              input_yx=True, output_yx=True)

        self.ROI_time_series = []
        for i in range(num_coords):
            self.ROI_time_series.append(ROITimeSeries(
                self.images, coords_yx[i], time_attr=self.dicom_order_key,
                kernel=kernel))


class T1ImageStack(ImageStack):
    """Calculates T1 relaxometry."""

    def __init__(self, image_slices, template_dcm=None, plate_number=None):
        super().__init__(image_slices, template_dcm, plate_number=plate_number,
                         dicom_order_key='InversionTime')


class T2ImageStack(ImageStack):
    """Calculates T2 relaxometry."""

    def __init__(self, image_slices, template_dcm=None, plate_number=None):
        super().__init__(image_slices, template_dcm, plate_number=plate_number,
                         dicom_order_key='EchoTime')


# Coordinates of centre of spheres in plate 5.
# Coordinates are in array format (y,x), rather than plt.patches format (x,y)
plate5_sphere_centres_yx = (
    (56, 95),
    (62, 117),
    (81, 133),
    (104, 134),
    (124, 121),
    (133, 98),
    (127, 75),
    (109, 61),
    (84, 60),
    (64, 72),
    (80, 81),
    (78, 111),
    (109, 113),
    (110, 82))

plate5_bolt_centres_yx = (
    (52, 80),
    (92, 141),
    (138, 85))

plate5_template_path = \
    os.path.join(os.path.dirname(os.path.realpath(__file__)),
                 'data', 'relaxometry',
                 'Plate5_T1_signed')
template_path = plate5_template_path

def main(dcm_target_list, template_dcm, show_plot=True):

    # debug-show only do T1
    t1_image_stack = T1ImageStack(dcm_target_list, template_dcm,
                                  plate_number=5)
    t1_image_stack.template_fit()
    t1_image_stack.generate_time_series(plate5_sphere_centres_yx)

    if show_plot:
        t1_image_stack.plot_fit()

    return t1_image_stack  # for debbing only



# Code below is for development only and should be deleted before release.
if __name__ == '__main__':

    import os, os.path
    import logging  # better to set up module level logging
    from pydicom.errors import InvalidDicomError

    template_dcm = pydicom.read_file(template_path)

    # get list of pydicom objects
    target_folder = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                 '..', 'tests', 'data', 'relaxometry', 'T1',
                                 'site1 20200218', 'plate 5')
    dcm_target_list = []
    (_,_,filenames) = next(os.walk(target_folder)) # get filenames, don't go to subfolders
    for filename in filenames:
        try:
            with pydicom.dcmread(os.path.join(target_folder, filename)) as dcm_target:
                dcm_target_list.append(dcm_target)
        except InvalidDicomError:
            logging.info(' Skipped non-DICOM file %r',
                         os.path.join(target_folder, filename))

    t1_image_stack = main(dcm_target_list, template_dcm)
    #t1_image_stack = main([template_dcm], template_dcm)
    
    rois = t1_image_stack.ROI_time_series
