'''
Dataset class to use when pointclouds are saved as .npz files,
with files containing ['points', 'joints'] as headers
'''
import os, sys
import random
import open3d as o3d
import pandas as pd
import tensorflow as tf
import numpy as np
from options.joints import JOINTS_INDICES
from typing import List, Literal, Tuple


class KinectDataset:
    def __init__(
        self,
        subjects_dirs, 
        joints: List[str],
        number_of_points: int,
        flag: Literal['train', 'val', 'test'],
        debug=False,
        ):
        """
        Args:
            subjects_dirs: ['/path/to/train/subject1/', '/path/to/train/subject2', ...]
            batch_size: Number of points in a batch
            joints: Skeleton joints defined by your RGB-D sensor, such as: ['PELVIS', 'FOOT', ...],
                    see all options in options folder
            number_of_points: Number of points to be sub-sampled in a point cloud
            flag: whether the dataset is used for training, validation or testing,
                  it is used to enforce a directory structure such as 
                  /path/to/train/... 
        """
        assert number_of_points <= 4096, 'Number of points supported is currently 4096'
        # Dataset size will be increased when calling tf.data.Dataset.from_generator
        self.dataset_size = 0
        self.joints = joints
        self.output_types = (tf.float32, tf.float32)
        self.number_of_joints = len(joints)
        self.number_of_points = number_of_points
        self.output_shapes = ((self.number_of_points, 3), (self.number_of_joints*3))
        self.flag = flag
        self.joints_columns = np.concatenate([[joint + ' (x)', joint + ' (y)', joint + ' (z)']  for joint in joints])

        master_root_dirs = []
        for subject in subjects_dirs:
            for experiment in os.listdir(subject):
                if experiment.find('_') < 0:
                    master_dir = os.path.join(subject, experiment, 'master_1')
                    master_root_dirs.append(master_dir)
                    
        self.pointcloud_files = []
        self.correspondent_skeleton_csv = {}

        for master_root_dir in master_root_dirs:
            # Save point cloud filenames
            pcd_dir = os.path.join(master_root_dir, 'filtered_and_registered_pointclouds')
            self.pointcloud_files.extend([os.path.join(pcd_dir, fn) for fn in os.listdir(pcd_dir)])
            # Read joints CSV
            skeleton_fp = pcd_dir.replace('filtered_and_registered_pointclouds', os.path.join('skeleton', 'synced_positions_3d.csv'))
            self.correspondent_skeleton_csv[pcd_dir] = pd.read_csv(skeleton_fp, index_col='timestamp')

        self.dataset_size = len(self.pointcloud_files)
        random.shuffle(self.pointcloud_files)

        if debug:
            self.pointcloud_files = self.pointcloud_files[:200]

        # Creating tensorflow dataset
        self.tf_dataset = tf.data.Dataset.from_generator(
            self._pointcloud_skeleton_tf_generator, 
            args= [self.pointcloud_files, self.number_of_points],
            output_types = self.output_types,
            output_shapes = self.output_shapes
            )
        
        
    def _pointcloud_skeleton_tf_generator(
        self,
        pointcloud_files: List[str], 
        number_of_points: int,
        ):
        """
        Args:
            pointcloud_files: Filepaths of all point clouds used
            number_of_points: Downsampling a pointclod to use *number_of_points*
        """
        pointcloud_files = [file.decode('utf-8') for file in pointcloud_files]

        i = 0 
        for file in pointcloud_files:
            # The try-exception is here for when pcds cant find a correspondence in csv
            try:
                ## Reading point cloud and samplingig
                npz_file = np.load(file)
                pcd = npz_file['points'][:self.number_of_points]
                
                correspondent_skeleton_key = tf.io.gfile.join(
                    os.path.sep.join(file.split(os.path.sep)[:-2]), 
                    'filtered_and_registered_pointclouds'
                )

                timestamp = int(file.split(os.path.sep)[-1][:-4])
                skeleton_df = self.correspondent_skeleton_csv[correspondent_skeleton_key]
                skeleton_positions = skeleton_df.loc[timestamp][self.joints_columns].values
                
                yield pcd, skeleton_positions 
                i = i + 1
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(file, flush=True)
                print(exc_type, fname, exc_tb.tb_lineno, flush=True)
                
                
    def __call__(self):
        return self.tf_dataset
        
    
    def visualize_dataset(
        self, 
        number_of_pcds: int = 2
        ):
        pcds = []
        skeleton = []
        for data in self.tf_dataset.take(number_of_pcds):
            points, skeletons = data
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(points.numpy())
            pcds.append(pcd)
            skeleton.append(skeletons.numpy())
        skeleton = pd.DataFrame(skeleton)

        from PyMoCapViewer import MoCapViewer
        viewer = MoCapViewer(grid_axis=None)
        viewer.add_point_cloud_animation(pcds)
        viewer.add_skeleton(skeleton)
        viewer.show_window()
        

if __name__ == '__main__':
    import glob
    # Import dataset
    subject_dirs = glob.glob('D:/azure_kinect/train/*')
    
    train_dataset = KinectDataset(
        subjects_dirs=subject_dirs, 
        number_of_points=4096,
        joints=['HIP_LEFT', 'HIP_RIGHT', 'PELVIS'],
        flag='train'
    )

    train_ds = train_dataset().batch(16).prefetch(10)
