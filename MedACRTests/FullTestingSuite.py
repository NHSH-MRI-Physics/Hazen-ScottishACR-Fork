import sys
sys.path.insert(0,"C:\\Users\\Johnt\\Documents\\GitHub\\Hazen-ScottishACR-Fork")
sys.path.insert(0,"D:\\Hazen-ScottishACR-Fork")
import pydicom
from hazenlib.utils import get_dicom_files
from hazenlib.tasks.acr_snr import ACRSNR
from hazenlib.tasks.acr_uniformity import ACRUniformity
from hazenlib.tasks.acr_geometric_accuracy import ACRGeometricAccuracy
from hazenlib.tasks.acr_spatial_resolution import ACRSpatialResolution
from hazenlib.ACRObject import ACRObject
import pathlib
from tests import TEST_DATA_DIR, TEST_REPORT_DIR

ReportDirPath = "MedACRTests/Results"

files = get_dicom_files("ACR_MRI1_20240116_104902641")
ACRDICOMSFiles = {}
for file in files:
    data = pydicom.dcmread(file)
    if (data.SeriesDescription not in ACRDICOMSFiles.keys()):
        ACRDICOMSFiles[data.SeriesDescription]=[]
    ACRDICOMSFiles[data.SeriesDescription].append(file)

DCMData={}
DCMData["ACR AxT1"] = ACRDICOMSFiles["ACR AxT1"]
DCMData["ACR AxT2"] = ACRDICOMSFiles["ACR AxT2"]

def RunSNR(Data):
    for seq in Data.keys():
        acr_snr_task = ACRSNR(input_data=Data[seq], report_dir=ReportDirPath,report=True,MediumACRPhantom=True)
        snr = acr_snr_task.run()
        print(seq+" SNR :" +str(snr["measurement"]["snr by smoothing"]["measured"]))


#Need Sag 
def GeoAcc(Data):
    for seq in Data.keys():
        acr_geometric_accuracy_task = ACRGeometricAccuracy(input_data=Data[seq],report_dir=ReportDirPath,MediumACRPhantom=True,report=True)
        GeoDist = acr_geometric_accuracy_task.run()
        print(seq+" Slice 1 Hor Dist: "+str(GeoDist["measurement"][GeoDist["file"][0]]["Horizontal distance"]) + "   "+ " Vert Dist: "+str(GeoDist["measurement"][GeoDist["file"][0]]["Vertical distance"]))
        print(seq+" Slice 5 Hor Dist:"+str(GeoDist["measurement"][GeoDist["file"][1]]["Horizontal distance"]) + "   "+ " Vert Dist:"+str(GeoDist["measurement"][GeoDist["file"][1]]["Horizontal distance"])+ "   "+ " Diag SW Dist:"+str(GeoDist["measurement"][GeoDist["file"][1]]["Diagonal distance SW"])+ "   "+ "Diag SE Dist:"+str(GeoDist["measurement"][GeoDist["file"][1]]["Diagonal distance SE"]))


def SpatialRes(Data):
    for seq in Data.keys():
        acr_spatial_resolution_task = ACRSpatialResolution(input_data=Data[seq],report_dir=ReportDirPath,report=True,MediumACRPhantom=True)
        Res = acr_spatial_resolution_task.run()
        print(seq+" MTF Raw :" +str(Res["measurement"]["raw mtf50"]) + "     MTF Fitted :" + str(Res["measurement"]["fitted mtf50"]))
SpatialRes(DCMData)