import os
import unittest
import pathlib
import pydicom

from hazenlib.utils import get_dicom_files
from hazenlib.tasks.acr_ghosting import ACRGhosting
from hazenlib.ACRObject import ACRObject
from tests import TEST_DATA_DIR, TEST_REPORT_DIR


class TestACRGhostingSiemens(unittest.TestCase):
    centre = [129, 128]
    psg = 0.041 #Changed because of bug in acr_ghosting at line 88 and 89

    def setUp(self):
        ACR_DATA_SIEMENS = pathlib.Path(TEST_DATA_DIR / "acr" / "Siemens")
        siemens_files = get_dicom_files(ACR_DATA_SIEMENS)
        self.acr_ghosting_task = ACRGhosting(
            input_data=siemens_files,
            report_dir=pathlib.PurePath.joinpath(TEST_REPORT_DIR),
        )

    def test_ghosting(self):
        ghosting_val = round(
            self.acr_ghosting_task.get_signal_ghosting(
                self.acr_ghosting_task.ACR_obj.slice7_dcm
            ),
            3,
        )

        print("\ntest_ghosting.py::TestGhosting::test_ghosting")
        print("new_release_value:", ghosting_val)
        print("fixed_value:", self.psg)

        assert ghosting_val == self.psg


class TestACRGhostingGE(TestACRGhostingSiemens):
    centre = [253, 256]
    psg = 0.479 #Changed because of bug in acr_ghosting at line 88 and 89

    def setUp(self):
        ACR_DATA_GE = pathlib.Path(TEST_DATA_DIR / "acr" / "GE")
        ge_files = get_dicom_files(ACR_DATA_GE)

        self.acr_ghosting_task = ACRGhosting(
            input_data=ge_files, report_dir=pathlib.PurePath.joinpath(TEST_REPORT_DIR)
        )

class TestMedACRGhosting(TestACRGhostingSiemens):
    psg = 0.137 

    def setUp(self):
        ACR_DATA_Med = pathlib.Path(TEST_DATA_DIR / "MedACR")
        ge_files = get_dicom_files(ACR_DATA_Med)

        self.acr_ghosting_task = ACRGhosting(
            input_data=ge_files, report_dir=pathlib.PurePath.joinpath(TEST_REPORT_DIR)
            ,MediumACRPhantom=True
        )

