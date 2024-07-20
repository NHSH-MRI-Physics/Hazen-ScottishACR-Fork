"""
ACR Uniformity

https://www.acraccreditation.org/-/media/acraccreditation/documents/mri/largephantomguidance.pdf

Calculates the percentage integral uniformity for slice 7 of the ACR phantom.

This script calculates the percentage integral uniformity in accordance with the ACR Guidance.
This is done by first defining a large 200cm2 ROI before placing 1cm2 ROIs at every pixel within
the large ROI. At each point, the mean of the 1cm2 ROI is calculated. The ROIs with the maximum and
minimum mean value are used to calculate the integral uniformity. The results are also visualised.

Created by Yassine Azma
yassine.azma@rmh.nhs.uk

13/01/2022
"""

import os
import sys
import traceback
import numpy as np
import math as math
import math as math

from hazenlib.HazenTask import HazenTask
from hazenlib.ACRObject import ACRObject
import matplotlib.pyplot as plot #Didn't like 'plt' with error: "cannot access local variable 'plt' where it is not associated with a value"
import matplotlib.pyplot as plot #Didn't like 'plt' with error: "cannot access local variable 'plt' where it is not associated with a value"
from pydicom.pixel_data_handlers.util import apply_modality_lut


class ACRUniformity(HazenTask):
    """Uniformity measurement class for DICOM images of the ACR phantom

    Inherits from HazenTask class
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialise ACR object
        self.ACR_obj = ACRObject(self.dcm_list,kwargs)

    def run(self) -> dict:
        """Main function for performing uniformity measurement
        using slice 7 from the ACR phantom image set

        Returns:
            dict: results are returned in a standardised dictionary structure specifying the task name, input DICOM Series Description + SeriesNumber + InstanceNumber, task measurement key-value pairs, optionally path to the generated images for visualisation
        """
        # Initialise results dictionary
        results = self.init_result_dict()
        results["file"] = self.img_desc(self.ACR_obj.slice7_dcm)

        try:
            unif, max_roi, min_roi, max_pos, min_pos = self.get_integral_uniformity(self.ACR_obj.slice7_dcm)
            unif, max_roi, min_roi, max_pos, min_pos = self.get_integral_uniformity(self.ACR_obj.slice7_dcm)
            results["measurement"] = {
                "integral uniformity %": round(unif, 2),
                "max roi": round(max_roi,1),
                "min roi": round(min_roi,1),
                "max pos": max_pos,
                "min pos": min_pos
                "max pos": max_pos,
                "min pos": min_pos
                }

        except Exception as e:
            print(
                f"Could not calculate the percent integral uniformity for"
                f"{self.img_desc(self.ACR_obj.slice7_dcm)} because of : {e}"
            )
            traceback.print_exc(file=sys.stdout)

        # only return reports if requested
        if self.report:
            results["report_image"] = self.report_files

        return results

    def get_integral_uniformity(self, dcm):
        """Calculate the integral uniformity in accordance with ACR guidance.
        global plt
        global plt
        Args:
            dcm (pydicom.Dataset): DICOM image object to calculate uniformity from

        Returns:
            int or float: value of integral unformity
        """
        img = apply_modality_lut(dcm.pixel_array, dcm).astype('uint16') #Must apply_modality_lut here since it's not applied to slice7_dcm in ACRObject
#        img = dcm.pixel_array 

        img = apply_modality_lut(dcm.pixel_array, dcm).astype('uint16') #Must apply_modality_lut here since it's not applied to slice7_dcm in ACRObject
#        img = dcm.pixel_array 

        res = dcm.PixelSpacing  # In-plane resolution from metadata
        r_large = np.ceil(80 / res[0]).astype(
            int
        )  # Required pixel radius to produce ~200cm2 ROI
        r_small = np.ceil(np.sqrt(100 / np.pi) / res[0]).astype(
            int
        )  # Required pixel radius to produce ~1cm2 ROI

        if self.ACR_obj.MediumACRPhantom==True:
            r_large = np.ceil(np.sqrt(16000*0.90 / np.pi) / res[0]).astype(int) #Making it a 90% smaller than 160cm^2 (16000mm^2) to avoid the bit at the top
            r_large = np.ceil(np.sqrt(16000*0.90 / np.pi) / res[0]).astype(int) #Making it a 90% smaller than 160cm^2 (16000mm^2) to avoid the bit at the top


        d_void = np.ceil(5 / res[0]).astype(
            int
        )  # Offset distance for rectangular void at top of phantom
        dims = img.shape  # Dimensions of image

        cxy = self.ACR_obj.centre
        base_mask = ACRObject.circular_mask(
            (cxy[0], cxy[1] + d_void), r_small, dims
        )  # Dummy circular mask at
        # centroid
        coords = np.nonzero(base_mask)  # Coordinates of mask

        lroi = self.ACR_obj.circular_mask([cxy[0], cxy[1] + d_void], r_large, dims)
        img_masked = lroi * img
        buffer_roi = self.ACR_obj.circular_mask([cxy[0], cxy[1] + d_void], 1.05*r_large, dims)
        img_buffer = buffer_roi * img

        half_max = np.percentile(img_masked[np.nonzero(img_masked)], 50)

        min_image = img_masked * (img_masked < half_max)
        max_image = img_masked * (img_masked > half_max)
        #Check data:
#        plot.imshow(min_image, cmap=plot.cm.bone)  # set the color map to bone 
#        plot.show() 
#        plot.imshow(max_image, cmap=plot.cm.bone)  # set the color map to bone 
#        plot.show()         
        
        #Check data:
#        plot.imshow(min_image, cmap=plot.cm.bone)  # set the color map to bone 
#        plot.show() 
#        plot.imshow(max_image, cmap=plot.cm.bone)  # set the color map to bone 
#        plot.show()         
        
        min_rows, min_cols = np.nonzero(min_image)[0], np.nonzero(min_image)[1]
        max_rows, max_cols = np.nonzero(max_image)[0], np.nonzero(max_image)[1]

        mean_array = np.zeros(img_masked.shape)

        def uniformity_iterator(masked_image, sample_mask, rows, cols):
            """Iterate through a pixel array and determine mean value

            Args:
                masked_image (np.array): subset of pixel array
                sample_mask (np.array): _description_
                rows (np.array): 1D array
                cols (np.array): 1D array

            Returns:
                np.array: array of mean values
            """
            coords = np.nonzero(sample_mask)  # Coordinates of mask
            for idx, (row, col) in enumerate(zip(rows, cols)):
                centre = [row, col]
                translate_mask = [
                    coords[0] + centre[0] - cxy[0] - d_void,
                    coords[1] + centre[1] - cxy[1],
                ]
                values = masked_image[translate_mask[0], translate_mask[1]]
                if np.count_nonzero(values) < np.count_nonzero(sample_mask):
                    mean_val = 0
                else:
                    mean_val = np.mean(values[np.nonzero(values)])

                mean_array[row, col] = mean_val

            return mean_array

        min_data = uniformity_iterator(min_image, base_mask, min_rows, min_cols)
        plot.imshow(min_data, cmap=plot.cm.bone)  # set the color map to bone 
        plot.show()
        max_data = uniformity_iterator(max_image, base_mask, max_rows, max_cols)      
        plot.imshow(max_data, cmap=plot.cm.bone)  # set the color map to bone 
        plot.show()
        sig_max = np.max(max_data) #This is a single pixel. ACR standard requires a 1cm2 ROI [HR 27.06.24]
        sig_min = np.min(min_data[np.nonzero(min_data)]) #   -similarly, this is a single-pixel value, therefore more liable to noise [HR 27.06.24]

        max_loc = np.where(max_data == sig_max)
        min_loc = np.where(min_data == sig_min)
        


        #sig_max = np.max(img_masked) #This is a single pixel. ACR standard requires a 1cm2 ROI [HR 27.06.24]
        #sig_min = np.min(img_masked[np.nonzero(img_masked)]) #   -similarly, this is a single-pixel value, therefore more liable to noise [HR 27.06.24]

        #New code based on 1cm2 ROI centred at positions of max and min pixels in the large ROI
        #Will compare the mean of ROIs centred at multiple identical max-or-min pixels (should they occur) and use the highest/lowest mean ROI, respectively [HR 11.07.24]
        """max_locs = np.where(img_masked == np.max(img_masked))
        print(f'max_locs={max_locs}, length = {len(max_locs[1])}')
        roi_max=np.zeros(10)
        for i in range(len(max_locs[1])):
            print(f'Loop#{i}: Max pixel value(s) {img_buffer[max_locs[0][i],max_locs[1][i]]} at voxel [x,y] {max_locs[0][i],max_locs[1][i]}')
            max_roi = img_buffer[int(max_locs[0][i])-round(5/res[0]):int(max_locs[0][i])+round(5/res[0]),int(max_locs[1][i])-round(5/res[0]):int(max_locs[1][i])+round(5/res[0])],
            roi_max[i] = np.mean(max_roi)
            plot.imshow(max_roi[0], cmap=plot.cm.bone)  # set the color map to bone 
            plot.show() 
        print(f'Mean of max_roi(s): {roi_max}')
        
        min_locs = np.where(img_masked == np.min(img_masked[np.nonzero(img_masked)]))
        print(f'min_locs={min_locs}, length = {len(min_locs[1])}')
        roi_min=np.zeros(10)
        for i in range(len(min_locs[1])):
            print(f'Loop# {i}: Min pixel value(s) {img_buffer[min_locs[0][i],min_locs[1][i]]} at voxel [x,y] {min_locs[0][i],min_locs[1][i]}')
            min_roi = img_buffer[int(min_locs[0][i])-round(5/res[0]):int(min_locs[0][i])+round(5/res[0]),int(min_locs[1][i])-round(5/res[0]):int(min_locs[1][i])+round(5/res[0])],
            roi_min[i] = np.mean(min_roi)
            plot.imshow(min_roi[0], cmap=plot.cm.bone)  # set the color map to bone 
            plot.show() 
        print(f'Mean of min_roi(s): {roi_min}')
  
        min_loc = round(np.mean(min_locs[0])),round(np.mean(min_locs[1]))
        for i in min_locs:
            min_roi = img_buffer[int(min_locs[0])-round(5/res[0]):int(min_locs[0])+round(5/res[0]),int(min_locs[1])-round(5/res[0]):int(min_locs[1])+round(5/res[0])],
            roi_min = np.mean(min_roi)   
        min_loc = min_locs.index(min(min_locs))        
        print(f'Min ROI values {roi_min} for 100 pixel ROI centred at voxel [x,y] {min_locs[1], min_locs[0]}')
        
        #print(f'Min value(s) {min_data[min_locs[0],min_locs[1]]} at voxel [x,y] {min_loc[1], min_loc[0]}')        
        #max_roi = img[int(max_loc[0])-round(5/res[0]):int(max_loc[0])+round(5/res[0]),int(max_loc[1])-round(5/res[0]):int(max_loc[1])+round(5/res[0])]
        #plot.imshow(max_roi, cmap=plot.cm.bone)  # set the color map to bone 
        #plot.show()
        
        sig_max = np.max(roi_max)
        sig_min = np.min(roi_min[np.nonzero(roi_min)])
        max_index = max(enumerate(roi_max),key=lambda x: x[1])[0]# np.where(roi_max == sig_max)
        min_index = min(enumerate(roi_min[np.nonzero(roi_min)]),key=lambda x: x[1])[0] #np.where(roi_min == sig_min)
        print(f'max pixel at {max_locs[0][max_index],max_locs[1][max_index]}')
        print(f'min pixel at {min_locs[0][min_index],min_locs[1][min_index]}')
        max_loc=max_locs[0][max_index],max_locs[1][max_index]
        min_loc=min_locs[0][min_index],min_locs[1][min_index]


        print(f'Max ROI value is {sig_max} for 100 pixel ROI centred at voxel [x,y] {max_loc[0], max_loc[1]}')
        print(f'Min ROI value is {sig_min} for 100 pixel ROI centred at voxel [x,y] {min_loc[0], min_loc[1]}')

#        min_roi = img[int(min_loc[0])-round(5/res[0]):int(min_loc[0])+round(5/res[0]),int(min_loc[1])-round(5/res[0]):int(min_loc[1])+round(5/res[0])]
#        print(f'Limits of min_roi are {int(min_loc[0])-round(5/res[0])} and {int(min_loc[0])+round(5/res[0])}')
#        plot.imshow(img_masked, cmap=plot.cm.bone)  # set the color map to bone 
#        plot.show()
#        plot.imshow(min_roi, cmap=plot.cm.bone)  # set the color map to bone 
#        plot.show() 
#        sig_min = np.mean(min_roi)
        """
        
        piu = 100 * (1 - (sig_max - sig_min) / (sig_max + sig_min))

        if self.report:
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(2, 1)
            fig.set_size_inches(8, 16)
            fig.tight_layout(pad=4)

            theta = np.linspace(0, 2 * np.pi, 360)

            axes[0].imshow(img)
            axes[0].scatter(cxy[0], cxy[1], c="red")
            circle1 = plt.Circle((cxy[0], cxy[1]), self.ACR_obj.radius, color='r',fill=False)
            axes[0].add_patch(circle1)
            axes[0].axis("off")
            axes[0].set_title("Centroid Location")

            axes[1].imshow(img)
            axes[1].imshow(lroi,alpha=0.4)
            axes[1].scatter(
                [max_loc[1], min_loc[1]], [max_loc[0], min_loc[0]], c="red", marker="x"
            )

            """ROI_min=plt.Rectangle((min_loc[1]-round(5/res[0]),min_loc[0]-round(5/res[0])),10/res[0],10/res[0],color='y',fill=False)
            axes[1].add_patch(ROI_min)
            ROI_max=plt.Rectangle((max_loc[1]-round(5/res[0]),max_loc[0]-round(5/res[0])),10/res[0],10/res[0],color='y',fill=False)
            axes[1].add_patch(ROI_max)"""

            axes[1].plot(
                r_small * np.cos(theta) + max_loc[1],
                r_small * np.sin(theta) + max_loc[0],
                c="yellow",
            )'''
            axes[1].annotate(
                "Min = " + str(np.round(sig_min, 1)),
                [min_loc[1], min_loc[0] + 10 / res[0]],
                c="white",
            )

            '''axes[1].plot(
                r_small * np.cos(theta) + min_loc[1],
                r_small * np.sin(theta) + min_loc[0],
                c="yellow",
            )'''
            axes[1].annotate(
                "Max = " + str(np.round(sig_max, 1)),
                [max_loc[1], max_loc[0] + 10 / res[0]],
                c="white",
            )

            axes[1].plot(
                r_large * np.cos(theta) + cxy[0],
                r_large * np.sin(theta) + cxy[1] + d_void,
                c="black",
            )

            axes[1].axis("off")
            axes[1].set_title(
                "Percent Integral Uniformity = " + str(np.round(piu, 2)) + "%"
            )

            img_path = os.path.realpath(
                os.path.join(self.report_path, f"{self.img_desc(dcm)}.png")
            )
            fig.savefig(img_path)
            self.report_files.append(img_path)

        return piu, sig_max, sig_min, max_loc, min_loc
