import os
import time
import logging
from preprocessing.extractor import MKVFilesProcessing
from preprocessing.data import DataProcessor
from utils.processing import remove_useless_dirs

try:
    os.mkdir('logs')
except:
    pass

logging.basicConfig(filename='logs/main.log', 
                    level=logging.DEBUG, 
                    format='%(asctime)s %(levelname)s %(name)s %(message)s',
                    force=True)

logger = logging.getLogger(__name__)

# Path to the Azure Kinect offline processor
OFFLINE_PROCESSOR_PATH = os.path.join(
        'C:/', 'Users', 'Tibor', 'source', 'repos', 'Azure-Kinect-Samples', 'body-tracking-samples', 
        'Azure-Kinect-Extractor', 'build', 'bin', 'Debug', 'offline_processor.exe'
        )

MASK_RCNN_PB_FILE = 'D:/azure_kinect/frozen_inference_graph.pb'
MASK_RCNN_PBTXT_FILE = 'D:/azure_kinect/mask_rcnn_inception_v2_coco_2018_01_28.pbtxt'

NUMBER_OF_JOINTS = 32 

if __name__ == '__main__':

    MKV_EXPERIMENTS_DIR = [
        #r'D:/azure_kinect/339F94/02',
        #r'D:/azure_kinect/C47EFC/01',
        #r'D:/azure_kinect/EEFE6D/01',
        #r'D:/azure_kinect/927394/02', r'D:/azure_kinect/927394/03', r'D:/azure_kinect/927394/04',
        #r'D:/azure_kinect/857F1E/04',
        #r'D:/azure_kinect/471EF1/02', r'D:/azure_kinect/471EF1/03', r'D:/azure_kinect/471EF1/04'
        
        #'D:/azure_kinect/20E29D/02', 'D:/azure_kinect/20E29D/03', 'D:/azure_kinect/20E29D/04',
        #'D:/azure_kinect/37A7AA/02', 'D:/azure_kinect/37A7AA/03', 'D:/azure_kinect/37A7AA/04',
        'D:/azure_kinect/76ABFD/03', 'D:/azure_kinect/76ABFD/04',
        'D:/azure_kinect/339F94/03', 'D:/azure_kinect/339F94/04',
        'D:/azure_kinect/AFCD31/02', 'D:/azure_kinect/AFCD31/03', 'D:/azure_kinect/AFCD31/04', 'D:/azure_kinect/AFCD31/05'
    ]

    for experiment_dir in MKV_EXPERIMENTS_DIR:

        try:
            logging.info(f'Starting experiment: {experiment_dir}')
            mkv_input_files = [os.path.join(experiment_dir, 'master_1.mkv'), os.path.join(experiment_dir, 'sub_1.mkv')]
            mkv_output_dirs = [x.replace('.mkv', '') for x in mkv_input_files]
               
            extractor = MKVFilesProcessing(mkv_input_files, 
                                           mkv_output_dirs, 
                                           OFFLINE_PROCESSOR_PATH,
                                           NUMBER_OF_JOINTS) 
            
            # Extract pointclouds, color,depths, skeleton from the MKV file
            #extractor.extract(pointcloud=True, skeleton=True)

            # Filter and register point clouds
            data_processor = DataProcessor(mkv_output_dirs, MASK_RCNN_PB_FILE, MASK_RCNN_PBTXT_FILE)
            
            # Aligning skeletons after registration has been done
            extractor.align_skeletons() 

            # remove colors, depths
            remove_useless_dirs(experiment_dir)

        except Exception as err:
            logging.info(err)
            logger.error(err)
