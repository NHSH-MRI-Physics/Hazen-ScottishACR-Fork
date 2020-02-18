"""
Assumptions:
Square voxels, no multi-frame support
"""

from math import pi
import sys
from copy import copy

import pydicom
import numpy as np
from scipy import ndimage
from scipy.interpolate import interp1d
from scipy.optimize import curve_fit
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def get_fov(dcm):

    if dcm.Manufacturer == "GE MEDICAL SYSTEMS":
        return dcm['0019', '101e']
    elif dcm.Manufacturer == 'SIEMENS':
        return dcm.Rows*dcm.PixelSpacing[0]
    elif dcm.Manufacturer =='Philips Medical Systems':
        if dcm.SOPClassUID == '1.2.840.10008.5.1.4.1.1.4.1':
        #Enhanced DICOM i.e. Multiframe DICOM
            return dcm.Rows*dcm.PerFrameFunctionalGroupsSequence.Item_1.PixelMeasuresSequence.Item_1.PixelSpacing[0]
        elif dcm.SOPClassUID == '1.2.840.10008.5.1.4.1.1.4':
        #MRImageStorage Class
            return dcm.Rows*dcm.PixelSpacing[0]
    else:
        raise Exception('Unrecognised SOPClassUID')


class Rod:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f'Rod: {self.x}, {self.y}'

    def __str__(self):
        return f'Rod: {self.x}, {self.y}'

    @property
    def centroid(self):
        return self.x, self.y

    def __lt__(self, other):
        """Using "reading order" in a coordinate system where 0,0 is bottom left"""
        try:
            x0, y0 = self.centroid
            x1, y1 = other.centroid
            return (-y0, x0) < (-y1, x1)
        except AttributeError:
            return NotImplemented

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y


def sort_rods(rods):

    lower_row = sorted(rods, key=lambda rod: rod.y)[-3:]
    lower_row = sorted(lower_row, key=lambda rod: rod.x)
    middle_row = sorted(rods, key=lambda rod: rod.y)[3:6]
    middle_row = sorted(middle_row, key=lambda rod: rod.x)
    upper_row = sorted(rods, key=lambda rod: rod.y)[0:3]
    upper_row = sorted(upper_row, key=lambda rod: rod.x)
    return lower_row + middle_row + upper_row


def get_rods(dcm):
    """
    The rod indices are ordered as:
        789
        456
        123
    Args:
        dcm:

    Returns:

    """
    arr = dcm.pixel_array
    # threshold and binaries the image in order to locate the rods.
    # this is achieved by masking the
    img_max = np.max(arr)  # maximum number of img intensity
    no_region = [None] * img_max

    # smooth the image with a 0.5sig kernal - this is to avoid noise being counted in .label function
    # img_tmp = ndimage.gaussian_filter(arr, 0.5)
    # commented out smoothing as not in original MATLAB - Haris
    img_tmp = arr
    # step over a range of threshold levels from 0 to the max in the image
    # using the ndimage.label function to count the features for each threshold
    for x in range(0, img_max):
        tmp = img_tmp <= x
        labeled_array, num_features = ndimage.label(tmp.astype(np.int))
        no_region[x] = num_features

    # find the indices that correspond to 10 regions and pick the median
    index = [i for i, val in enumerate(no_region) if val == 10]

    thres_ind = np.median(index).astype(np.int)

    # Generate the labeled array with the threshold chosen
    img_threshold = img_tmp <= thres_ind

    labeled_array, num_features = ndimage.label(img_threshold.astype(np.int))

    # check that we have got the 10 rods!
    if num_features != 10:
        sys.exit("Did not find the 9 rods")

    rods = ndimage.measurements.center_of_mass(arr, labeled_array, range(2, 11))

    rods = [Rod(x=x[1], y=x[0]) for x in rods]
    rods = sort_rods(rods)

    return rods


def plot_rods(arr, rods): # pragma: no cover
    # fig, ax = plt.subplots(nrows=1, ncols=2)
    # fig.suptitle("get_rods")
    plt.imshow(arr, cmap='gray')
    # ax[0][1].imshow(img_threshold, cmap='gray')
    # ax[1][0].imshow(labeled_array, cmap='gray')
    # ax[1][1].imshow(arr, cmap='gray')

    mark = ['1', '2', '3', '4', '5', '6', '7', '8', '9']

    for idx, i in enumerate(rods):
        plt.scatter(x=i.x, y=i.y, marker=f"${mark[idx]}$", s=10, linewidths=0.4)
    # ax[1][1].scatter(x=[i.x for i in rods], y=[i.y for i in rods], marker="+", s=1, linewidths=0.5)
    # fig.savefig('rods.png')
    plt.show()


def get_rod_distances(rods):
    """
    Calculate horizontal and vertical distances of rods in terms of pixels

    Args:
        rods:

    Returns:

    """
    horz_dist = [None] * 3
    vert_dist = [None] * 3
    horz_dist[0] = round((((rods[2].y - rods[0].y) ** 2) + (rods[2].x - rods[0].x) ** 2) ** 0.5, 3)
    horz_dist[1] = round((((rods[5].y - rods[3].y) ** 2) + (rods[5].x - rods[3].x) ** 2) ** 0.5, 3)
    horz_dist[2] = round((((rods[8].y - rods[6].y) ** 2) + (rods[8].x - rods[6].x) ** 2) ** 0.5, 3)

    vert_dist[2] = round((((rods[2].y - rods[8].y) ** 2) + (rods[2].x - rods[8].x) ** 2) ** 0.5, 3)
    vert_dist[1] = round((((rods[1].y - rods[7].y) ** 2) + (rods[1].x - rods[7].x) ** 2) ** 0.5, 3)
    vert_dist[0] = round((((rods[0].y - rods[6].y) ** 2) + (rods[0].x - rods[6].x) ** 2) ** 0.5, 3)

    return horz_dist, vert_dist


def get_rod_distortion_correction_coefficients(horizontal_distances) -> dict:
    """
    To remove the effect of geometric distortion from the slice width measurement. Assumes that rod separation is
    120 mm.
    Args:
        horizontal_distances: list containing horizontal rod distances

    Returns:
        coefficients: dictionary containing top and bottom distortion corrections
    """
    coefficients = {"top": round(np.mean(horizontal_distances[1:3]) / 120, 4),
                    "bottom": round(np.mean(horizontal_distances[0:2]) / 120, 4)}

    return coefficients


def get_rod_distortions(rods, dcm):
    pixel_spacing = dcm.PixelSpacing[0]

    horz_dist, vert_dist = get_rod_distances(rods)

    # calculate the horizontal and vertical distances
    horz_dist_mm = np.multiply(pixel_spacing, horz_dist)
    vert_dist_mm = np.multiply(pixel_spacing, vert_dist)

    horz_distortion = 100 * np.std(horz_dist_mm, ddof=1) / np.mean(horz_dist_mm) # ddof to match MATLAB std
    vert_distortion = 100 * np.std(vert_dist_mm, ddof=1) / np.mean(vert_dist_mm)
    return horz_distortion, vert_distortion


# class Trapezoid(np.ndarray):
#     def __init__(self, n_ramp, n_plateau, n_left_baseline, n_right_baseline, plateau_amplitude, shape):
#         super().__init__(shape)
#         self.n_ramp, self.n_plateau, self.n_left_baseline, self.n_right_baseline, self.plateau_amplitude = n_ramp, n_plateau, n_left_baseline, n_right_baseline, plateau_amplitude
#
#     def __repr__(self):
#         return f'Trapezoid: {self.n_ramp}, {self.n_plateau}, {self.n_left_baseline}, {self.n_right_baseline}, {self.plateau_amplitude}'


def baseline_correction(profile, sample_spacing):
    """
    Calculates quadratic fit of the baseline and subtracts from profile

    Args:
        profile:
        sample_spacing:

    Returns:

    """
    profile_width = len(profile)
    padding = 30
    outer_profile = np.concatenate([profile[0:padding], profile[-padding:]])
    # create the x axis for the outer profile
    x_left = np.arange(padding)
    x_right = np.arange(profile_width - padding, profile_width)
    x_outer = np.concatenate([x_left, x_right])

    # seconds order poly fit of the outer profile
    polynomial_coefficients = np.polyfit(x_outer, outer_profile, 2)
    polynomial_fit = np.poly1d(polynomial_coefficients)

    # use the poly fit to generate a quadratic curve with 0.25 space (high res)
    x_interp = np.arange(0, profile_width, sample_spacing)
    x = np.arange(0, profile_width)

    baseline_interp = polynomial_fit(x_interp)
    baseline = polynomial_fit(x)

    # Remove the baseline effects from the profiles
    profile_corrected = profile - baseline
    f = interp1d(x, profile_corrected, fill_value="extrapolate")
    profile_corrected_interp = f(x_interp)
    profile_interp = profile_corrected_interp + baseline_interp

    return {"f": polynomial_coefficients,
            "x_interpolated": x_interp,
            "baseline_fit": polynomial_fit,
            "baseline_interpolated": baseline_interp,
            "profile_interpolated": profile_interp,
            "profile_corrected_interpolated": profile_corrected_interp}


def plot_baseline_correction(profile, corrected_profiles): # pragma: no cover
    baseline = corrected_profiles["baseline"]
    profile_corrected_interp = corrected_profiles["profile_corrected_interpolated"]

    plt.figure()
    plt.plot(profile, label='profile')
    plt.plot(baseline, label='baseline')
    plt.legend()
    plt.title('Baseline fitted')

    plt.figure()
    plt.plot(profile_corrected_interp)
    plt.title("profile_corrected_interp")


def trapezoid(n_ramp, n_plateau, n_left_baseline, n_right_baseline, plateau_amplitude):
    # n_ramp
    # n_plateau
    # n_left_baseline
    # n_right_baseline
    # plateau_amplitude

    if n_left_baseline < 1:
        left_baseline = []
    else:
        left_baseline = np.zeros(n_left_baseline)

    if n_ramp < 1:
        left_ramp = []
        right_ramp = []
    else:
        left_ramp = np.linspace(0, plateau_amplitude, n_ramp)
        right_ramp = np.linspace(plateau_amplitude, 0, n_ramp)

    if n_plateau < 1:
        plateau = []
    else:
        plateau = plateau_amplitude * np.ones(n_plateau)

    if n_right_baseline < 1:
        right_baseline = []
    else:
        right_baseline = np.zeros(n_right_baseline)

    trap = np.concatenate([left_baseline, left_ramp, plateau, right_ramp, right_baseline])
    fwhm = n_plateau + n_ramp

    return trap, fwhm


def get_ramp_profiles(image_array, rods) -> dict:
    # Find the central y-axis point for the top and bottom profiles
    # done by finding the distance between the mid-distances of the central rods

    top_profile_vertical_centre = np.round(((rods[3].y - rods[6].y) / 2) + rods[6].y).astype(int)
    bottom_profile_vertical_centre = np.round(((rods[0].y - rods[3].y) / 2) + rods[3].y).astype(int)

    # Selected 20mm around the mid-distances and take the average to find the line profiles
    top_profile = image_array[
                  (top_profile_vertical_centre - 10):(top_profile_vertical_centre + 10),
                  int(rods[3].x):int(rods[5].x)]

    bottom_profile = image_array[
                     (bottom_profile_vertical_centre - 10):(bottom_profile_vertical_centre + 10),
                     int(rods[3].x):int(rods[5].x)]

    return {"top": top_profile, "bottom": bottom_profile,
            "top-centre": top_profile_vertical_centre, "bottom-centre": bottom_profile_vertical_centre}


def plot_ramp_profiles(arr, ramp_profiles): # pragma: no cover
    plt.figure()
    plt.imshow(arr)
    top_profile_mean = np.mean(ramp_profiles["top"], axis=0)
    bottom_profile_mean = np.mean(ramp_profiles['bottom'], axis=0)
    for i, val in enumerate(ramp_profiles["top"]):
        plt.plot([ramp_profiles["top"] - 10 + i] * 120, '-', color='red')

    for i, val in enumerate(ramp_profiles["bottom"]):
        plt.plot([ramp_profiles["bottom"] - 10 + i] * 120, '-',
                 color='red')

    plt.figure()
    for i in ramp_profiles["top"]:
        plt.plot(i)
    plt.plot(ramp_profiles["top"][1])

    plt.figure()
    plt.plot(top_profile_mean)

    top_profile_mean_corrected = baseline_correction(profile=top_profile_mean, sample_spacing=0.25)
    plt.figure()
    plt.plot(top_profile_mean_corrected)
    plt.title('top_profile_mean_corrected')

    bottom_profile_mean_corrected = baseline_correction(profile=bottom_profile_mean, sample_spacing=0.25)
    plt.figure()
    plt.plot(bottom_profile_mean_corrected)
    plt.title('bottom_profile_mean_corrected')
    plt.show()


def get_initial_trapezoid_fit_and_coefficients(profile, slice_thickness):
    n_plateau, n_ramp = None, None

    if slice_thickness == 3:
        # not sure where these magic numbers are from, I subtracted 1 from MATLAB numbers
        n_ramp = 7
        n_plateau = 32

    elif slice_thickness == 5:
        # not sure where these magic numbers are from, I subtracted 1 from MATLAB numbers
        n_ramp = 47
        n_plateau = 55

    trapezoid_centre = round(np.median(np.argwhere(profile < np.mean(profile)))).astype(int)

    n_total = len(profile)
    n_left_baseline = int(trapezoid_centre - round(n_plateau / 2) - n_ramp - 1)
    n_right_baseline = n_total - n_left_baseline - 2 * n_ramp - n_plateau
    plateau_amplitude = np.percentile(profile, 5) - np.percentile(profile, 95)
    trapezoid_fit_coefficients = [n_ramp, n_plateau, n_left_baseline, n_right_baseline, plateau_amplitude]

    trapezoid_fit_initial, _ = trapezoid(n_ramp, n_plateau, n_left_baseline, n_right_baseline, plateau_amplitude)

    return trapezoid_fit_initial, trapezoid_fit_coefficients


def fit_trapezoid(profiles, slice_thickness):
    trapezoid_fit, trapezoid_fit_coefficients = get_initial_trapezoid_fit_and_coefficients(
        profiles["profile_corrected_interpolated"], slice_thickness)

    x_interp = profiles["x_interpolated"]
    profile_interp = profiles["profile_interpolated"]
    baseline_interpolated = profiles["baseline_fit"](x_interp)
    baseline_fit_coefficients = profiles["baseline_fit"]
    baseline_fit_coefficients = [baseline_fit_coefficients.c[0], baseline_fit_coefficients.c[1], baseline_fit_coefficients.c[2]]
    # sum squared differences
    current_error = sum((profiles["profile_corrected_interpolated"] - (baseline_interpolated + trapezoid_fit)) ** 2)

    def get_error(base, trap):
        """ Check if fit is improving """
        trapezoid_fit_temp, _ = trapezoid(*trap)

        baseline_fit_temp = np.poly1d(base)(x_interp)

        sum_squared_difference = sum((profile_interp - (baseline_fit_temp + trapezoid_fit_temp)) ** 2)

        return sum_squared_difference

    cont = 1
    j = 0
    """Go through a series of changes to reduce error, if error doesnt reduced in one entire loop then exit"""
    while cont == 1:
        j += 1
        cont = 0

        for i in range(14):
            baseline_fit_coefficients_temp = copy(baseline_fit_coefficients)
            trapezoid_fit_coefficients_temp = copy(trapezoid_fit_coefficients)

            if i == 0:
                baseline_fit_coefficients_temp[0] = baseline_fit_coefficients_temp[0] - 0.0001

            elif i == 1:
                baseline_fit_coefficients_temp[0] = baseline_fit_coefficients_temp[0] + 0.0001
            elif i == 2:
                baseline_fit_coefficients_temp[1] = baseline_fit_coefficients_temp[1] - 0.001
            elif i == 3:
                baseline_fit_coefficients_temp[1] = baseline_fit_coefficients_temp[1] + 0.001
            elif i == 4:
                baseline_fit_coefficients_temp[2] = baseline_fit_coefficients_temp[2] - 0.1
            elif i == 5:
                baseline_fit_coefficients_temp[2] = baseline_fit_coefficients_temp[2] + 0.1
            elif i == 6:  # Decrease the ramp width
                trapezoid_fit_coefficients_temp[0] = trapezoid_fit_coefficients_temp[0] - 1
                trapezoid_fit_coefficients_temp[2] = trapezoid_fit_coefficients_temp[2] + 1
                trapezoid_fit_coefficients_temp[3] = trapezoid_fit_coefficients_temp[3] + 1
            elif i == 7:  # Increase the ramp width
                trapezoid_fit_coefficients_temp[0] = trapezoid_fit_coefficients_temp[0] + 1
                trapezoid_fit_coefficients_temp[2] = trapezoid_fit_coefficients_temp[2] - 1
                trapezoid_fit_coefficients_temp[3] = trapezoid_fit_coefficients_temp[3] - 1
            elif i == 8:  # Decrease plateau width
                trapezoid_fit_coefficients_temp[1] = trapezoid_fit_coefficients_temp[1] - 2
                trapezoid_fit_coefficients_temp[2] = trapezoid_fit_coefficients_temp[2] + 1
                trapezoid_fit_coefficients_temp[3] = trapezoid_fit_coefficients_temp[3] + 1

            elif i == 9:  # Increase plateau width
                trapezoid_fit_coefficients_temp[1] = trapezoid_fit_coefficients_temp[1] + 2
                trapezoid_fit_coefficients_temp[2] = trapezoid_fit_coefficients_temp[2] - 1
                trapezoid_fit_coefficients_temp[3] = trapezoid_fit_coefficients_temp[3] - 1

            elif i == 10:  # Shift centre to the left
                trapezoid_fit_coefficients_temp[2] = trapezoid_fit_coefficients_temp[2] - 1
                trapezoid_fit_coefficients_temp[3] = trapezoid_fit_coefficients_temp[3] + 1

            elif i == 11:  # Shift centre to the right
                trapezoid_fit_coefficients_temp[2] = trapezoid_fit_coefficients_temp[2] + 1
                trapezoid_fit_coefficients_temp[3] = trapezoid_fit_coefficients_temp[3] - 1

            elif i == 12:  # Reduce amplitude
                trapezoid_fit_coefficients_temp[4] = trapezoid_fit_coefficients_temp[4] - 0.1

            elif i == 13:  # Increase amplitude
                trapezoid_fit_coefficients_temp[4] = trapezoid_fit_coefficients_temp[4] + 0.1

            new_error = get_error(base=baseline_fit_coefficients_temp, trap=trapezoid_fit_coefficients_temp)

            if new_error < current_error:
                cont = 1
                if i > 6:
                    trapezoid_fit_coefficients = trapezoid_fit_coefficients_temp
                else:
                    baseline_fit_coefficients = baseline_fit_coefficients_temp
                current_error = new_error

    return trapezoid_fit_coefficients, baseline_fit_coefficients


def get_slice_width(dcm):
    """
    Calculates slice width using double wedge image

    Args:
        dcm:

    Returns:

    """
    slice_width = {"top": {}, "bottom": {}, "combined": {}}
    arr = dcm.pixel_array
    sample_spacing = 0.25
    pixel_size = dcm.PixelSpacing[0]

    rods = get_rods(dcm)
    horz_distances, vert_distances = get_rod_distances(rods)
    horz_distortion, vert_distortion = get_rod_distortions(rods, dcm)
    correction_coefficients = get_rod_distortion_correction_coefficients(horizontal_distances=horz_distances)

    ramp_profiles = get_ramp_profiles(arr, rods)
    ramp_profiles_baseline_corrected = {"top": baseline_correction(np.mean(ramp_profiles["top"], axis=0),
                                                                   sample_spacing),
                                        "bottom": baseline_correction(np.mean(ramp_profiles["bottom"], axis=0),
                                                                      sample_spacing)}

    trapezoid_coefficients, baseline_coefficients = fit_trapezoid(ramp_profiles_baseline_corrected["top"],
                                                                  dcm.SliceThickness)
    _, fwhm = trapezoid(*trapezoid_coefficients)

    slice_width["top"]["default"] = fwhm * sample_spacing * pixel_size * np.tan((11.3*pi)/180)
    # Factor of 4 because interpolated by factor of four

    slice_width["top"]["geometry_corrected"] = slice_width["top"]["default"]/correction_coefficients["top"]

    # AAPM method directly incorporating phantom tilt
    slice_width["top"]["aapm"] = fwhm * sample_spacing * pixel_size

    # AAPM method directly incorporating phantom tilt and independent of geometric linearity
    slice_width["top"]["aapm_corrected"] = (fwhm * sample_spacing * pixel_size) / correction_coefficients["top"]

    trapezoid_coefficients, baseline_coefficients = fit_trapezoid(ramp_profiles_baseline_corrected["bottom"],
                                                                  dcm.SliceThickness)
    _, fwhm = trapezoid(*trapezoid_coefficients)

    slice_width["bottom"]["default"] = fwhm * sample_spacing * pixel_size * np.tan((11.3 * pi) / 180)
    # Factor of 4 because interpolated by factor of four

    slice_width["bottom"]["geometry_corrected"] = slice_width["bottom"]["default"] / correction_coefficients["bottom"]

    # AAPM method directly incorporating phantom tilt
    slice_width["bottom"]["aapm"] = fwhm * sample_spacing * pixel_size

    # AAPM method directly incorporating phantom tilt and independent of geometric linearity
    slice_width["bottom"]["aapm_corrected"] = (fwhm * sample_spacing * pixel_size) / correction_coefficients["bottom"]

    # Geometric mean of slice widths (pg 34 of IPEM Report 80)
    slice_width["combined"]["default"] = (slice_width["top"]["default"] * slice_width["bottom"]["default"]) ** 0.5
    slice_width["combined"]["geometry_corrected"] = (slice_width["top"]["geometry_corrected"] * slice_width["bottom"]["geometry_corrected"]) ** 0.5

    # AAPM method directly incorporating phantom tilt
    theta = (180.0 - 2.0 * 11.3) * pi / 180.0
    term1 = (np.cos(theta)) ** 2.0 * (slice_width["bottom"]["aapm"] - slice_width["top"]["aapm"])**2.0 + (4.0 * slice_width["bottom"]["aapm"] * slice_width["top"]["aapm"])
    term2 = (slice_width["bottom"]["aapm"] + slice_width["top"]["aapm"]) * np.cos(theta)
    term3 = 2.0 * np.sin(theta)

    slice_width["combined"]["aapm_tilt"] = (term1**0.5 + term2)/term3
    phantom_tilt = np.arctan(slice_width["combined"]["aapm_tilt"]/slice_width["bottom"]["aapm"]) + (theta/2.0) - pi/2.0
    phantom_tilt_deg = phantom_tilt * (180.0/pi)

    phantom_tilt_check = -np.arctan(slice_width["combined"]["aapm_tilt"]/slice_width["top"]["aapm"]) - (theta/2.0) + pi/2.0
    phantom_tilt_check_deg = phantom_tilt_check * (180.0/pi)

    # AAPM method directly incorporating phantom tilt and independent of geometric linearity
    theta = (180.0 - 2.0 * 11.3) * pi/180.0
    term1 = (np.cos(theta)) ** 2.0 * (slice_width["bottom"]["aapm_corrected"] - slice_width["top"]["aapm_corrected"])**2.0 + (4.0 * slice_width["bottom"]["aapm_corrected"] * slice_width["top"]["aapm_corrected"])
    term2 = (slice_width["bottom"]["aapm_corrected"] + slice_width["top"]["aapm_corrected"]) * np.cos(theta)
    term3 = 2.0 * np.sin(theta)

    slice_width["combined"]["aapm_tilt_corrected"] = (term1 ** 0.5 + term2) / term3
    phantom_tilt = np.arctan(slice_width["combined"]["aapm_tilt_corrected"] / slice_width["bottom"]["aapm_corrected"]) + (theta / 2.0) - pi / 2.0
    phantom_tilt_deg = phantom_tilt * (180.0 / pi)

    phantom_tilt_check = -np.arctan(slice_width["combined"]["aapm_tilt_corrected"] / slice_width["top"]["aapm_corrected"]) - (
                theta / 2.0) + pi / 2.0
    phantom_tilt_check_deg = phantom_tilt_check * (180.0 / pi)
    horizontal_linearity = np.mean(horz_distances)
    vertical_linearity = np.mean(vert_distances)

    # print(f"Series Description: {dcm.SeriesDescription}\nWidth: {dcm.Rows}\nHeight: {dcm.Columns}\nSlice Thickness(mm):"
    #       f"{dcm.SliceThickness}\nField of View (mm): {get_fov(dcm)}\nbandwidth (Hz/Px) : {dcm.PixelBandwidth}\n"
    #       f"TR  (ms) : {dcm.RepetitionTime}\nTE  (ms) : {dcm.EchoTime}\nFlip Angle  (deg) : {dcm.FlipAngle}\n"
    #       f"Horizontal line bottom (mm): {horz_distances[0]}\nHorizontal line middle (mm): {horz_distances[2]}\n"
    #       f"Horizontal line top (mm): {horz_distances[2]}\nHorizontal Linearity (mm): {np.mean(horz_distances)}\n"
    #       f"Horizontal Distortion: {horz_distortion}\nVertical line left (mm): {vert_distances[0]}\n"
    #       f"Vertical line middle (mm): {vert_distances[1]}\nVertical line right (mm): {vert_distances[2]}\n"
    #       f"Vertical Linearity (mm): {np.mean(vert_distances)}\nVertical Distortion: {vert_distortion}\n"
    #       f"Slice width top (mm): {slice_width['top']['default']}\n"
    #       f"Slice width bottom (mm): {slice_width['bottom']['default']}\nPhantom tilt (deg): {phantom_tilt_deg}\n"
    #       f"Slice width AAPM geometry corrected (mm): {slice_width['combined']['aapm_tilt_corrected']}")

    return {'slice_width': slice_width['combined']['aapm_tilt_corrected'],
            'vertical_distortion': vert_distortion, 'horizontal_distortion': horz_distortion,
            'vertical_linearity': vertical_linearity, 'horizontal_linearity': horizontal_linearity}


def main(data: list) -> dict:
    if len(data) != 1:
        raise Exception('Need one DICOM file only')

    dcm = data[0]
    print(f"Measuring slice width from image: {dcm.SeriesDescription}")
    results = get_slice_width(dcm)

    return {"slice_width_distortion_linearity": results}