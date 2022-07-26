'''
This script was generated to manually register two or more point clouds

User provides a  list of N paths, with the first being the master_1, such as:
    python manual_pointcloud_registration.py /path/to/master_1 path/to/sub_1 path/to/sub_2 

And the script yields N-1 transformations from the sub coordinate frames to the master reference frame
    |_ (saved) /path/to/master_1/transformation_master_sub_1.npy 
    |_ (saved) /path/to/master_1/transformation_master_sub_2.npy
    
'''
import os
import copy
import copy
import argparse
import numpy as np
import open3d as o3d
import pandas as pd

from utils.io import rgbd_to_pointcloud, load_color, load_depth
from utils.processing import synchronize_filenames
from typing import List, Union, Tuple


def load_pointclouds(
    synced_files: Union[pd.DataFrame, str], 
    root_dirs: List[str],
    frame: int = 1, 
    isdir: bool = True
    ) -> o3d.geometry.PointCloud:
    if isdir:
        pcds = []
        for i, device in enumerate(synced_files.columns):
            # generate point cloud
            timestamp = str(int(synced_files[device].iloc[frame]))
            color = load_color(os.path.join(root_dirs[i], 'color', timestamp + '_rgb.png'))
            depth = load_depth(os.path.join(root_dirs[i], 'depths', timestamp + '_depth.dat'))
            pcds.append(rgbd_to_pointcloud(color, depth))
    else:
        for i in range(len(synced_files)):
            pcds.append(o3d.io.read_point_cloud(synced_files[i]))
    return pcds


def draw_registration_result_original_color(
    source: o3d.geometry.PointCloud, 
    target: o3d.geometry.PointCloud, 
    transformation: np.ndarray
    ) -> None:
    source_temp = copy.deepcopy(source)
    source_temp.transform(transformation)
    o3d.visualization.draw_geometries([source_temp, target])

    
def pick_points(pcd: o3d.geometry.PointCloud):
    print("")
    print("1) Please pick at least three correspondences using [shift + left click]")
    print("   Press [shift + right click] to undo point picking")
    print("2) After picking points, press 'Q' to close the window")
    vis = o3d.visualization.VisualizerWithEditing()
    vis.create_window()
    vis.add_geometry(pcd)
    vis.run()  # user picks points
    vis.destroy_window()
    print("")
    return vis.get_picked_points()


def manual_registration(
    pcd_master: o3d.geometry.PointCloud, 
    pcd_sub: o3d.geometry.PointCloud
    ) -> np.ndarray:
    print("Manual ICP")
    source = copy.deepcopy(pcd_sub)
    target = copy.deepcopy(pcd_master)
    print("Visualization of two point clouds before manual alignment")
    draw_registration_result_original_color(source, target, np.identity(4))

    # pick points from two point clouds and builds correspondences
    picked_id_source = pick_points(source)
    picked_id_target = pick_points(target)
    assert (len(picked_id_source) >= 3 and len(picked_id_target) >= 3)
    assert (len(picked_id_source) == len(picked_id_target))
    corr = np.zeros((len(picked_id_source), 2))
    corr[:, 0] = picked_id_source
    corr[:, 1] = picked_id_target

    # estimate rough transformation using correspondences
    print("Compute a rough transform using the correspondences given by user")
    p2p = o3d.pipelines.registration.TransformationEstimationPointToPoint()
    trans_init = p2p.compute_transformation(source, target, o3d.utility.Vector2iVector(corr))

    # point-to-point ICP for refinement
    print("Perform point-to-point ICP refinement")
    threshold = 0.03  # 2cm distance threshold
    reg_p2p = o3d.pipelines.registration.registration_icp(
        source, target, threshold, trans_init,
        o3d.pipelines.registration.TransformationEstimationPointToPoint())
    draw_registration_result_original_color(source, target, reg_p2p.transformation)
    
    return reg_p2p.transformation


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='Given multiple root dirs in the order `master, sub1, sub2, ...` '
                                              'return a rigid transformation from sub1 to master, sub2 to master '
                                              'and so on')
    parser.add_argument('-p','--paths', nargs='+', help='Path to root directories or .pcd files', required=True)
    parser.add_argument('-f', '--frame', type=int, help='Specific frame to use as calibration', required=False, default=1)
    args = vars(parser.parse_args())

    directory_flag = True
    
    if len(args['paths']) < 2:
        raise ValueError('At least two folders must be provided')

    for path in args['paths']:
        if os.path.isdir(path) == False:
            directory_flag = False
            
    if directory_flag == True:
        synced_files = synchronize_filenames(args['paths']).dropna()
        
    pcds = load_pointclouds(synced_files, args['paths'], args['frame'], directory_flag)
  
    # Setting destination path to save .npy transformation
    transformation_dsts = []
    for i, path in enumerate(args['paths']):
        if os.path.isdir(path):
            transformation_dst = os.path.join(
                path.replace(f'sub_{i}', 'master_1'), f'transformation_master_sub_{i}.npy'
                )
        elif os.path.isfile(path):
            transformation_dst = os.path.join(
                path, f'transformation_master_sub_{i+1}.npy'
                )
        else:
            raise ValueError('Please provide the path for a root directory or to a .pcd file')
        
        # Saving transformation destination and point clouds
        if i > 0:
            transformation_dsts.append(transformation_dst)

    # Apply manual registration and save result
    for i in range(1, len(pcds)):
        transformation = manual_registration(pcds[0], pcds[i])
        print('Your transformation is saved under:', transformation_dsts[i-1])
        np.save(transformation_dsts[i-1], transformation)
