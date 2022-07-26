import wandb
import os, sys
import glob
import logging
import argparse
import numpy as np
import tensorflow as tf

from pathlib import Path
from tensorflow import keras
from models.pointnet import create_pointnet
from datasets.kinect_dataset_npz import KinectDataset
from metrics.metric import percentual_correct_keypoints
from options.normalization import normalization_options
from configs.config import get_default_config
from wandb.keras import WandbCallback

np.set_printoptions(suppress=True)
tf.random.set_seed(1234)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 


# Give path to the yaml configuration file using argument parser
parser = argparse.ArgumentParser(description=__doc__, add_help=True)
parser.add_argument('--config', help='configuration file *.yaml', required=True)


# Path to subjects
MASTER_ROOT_DIRS = glob.glob('E:/sampled_points_dataset/train/*')
TEST_ROOT_DIRS = glob.glob('E:/sampled_points_dataset/test/*')
VAL_ROOT_DIRS = glob.glob('E:/sampled_points_dataset/val/*')


# Loading configuration and defining constants
CONFIGS = get_default_config(parser)
EPOCHS = CONFIGS.TRAIN.EPOCHS
BATCH_SIZE = CONFIGS.TRAIN.BATCH_SIZE
JOINTS = CONFIGS.DATA.JOINTS
NUMBER_OF_POINTS = CONFIGS.DATA.SAMPLING_POINTS
NORMALIZATION = CONFIGS.DATA.NORMALIZATION
LEARNING_RATE = CONFIGS.TRAIN.LEARNING_RATE
THRESHOLDS = CONFIGS.EVAL.THRESHOLDS
LOSS = CONFIGS.TRAIN.LOSS
METRICS = CONFIGS.EVAL.METRICS
PROJECT = CONFIGS.PROJECT.NAME
NAME = CONFIGS.PROJECT.EXPERIMENT
CKPT_DIR = CONFIGS.DIRS.CHECKPOINT_DIR
LOGS_DIR = CONFIGS.DIRS.LOGS_DIR


# Logging options
Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOGS_DIR, 'train.log'), 
    level=logging.DEBUG, 
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    force=True
)


MASTER_ROOT_DIRS = glob.glob('E:/sampled_points_dataset/train/*')
TEST_ROOT_DIRS = glob.glob('E:/sampled_points_dataset/test/*')
VAL_ROOT_DIRS = glob.glob('E:/sampled_points_dataset/val/*')


if __name__ == '__main__':

    print(CONFIGS, flush=True)

    # Import dataset
    train_dataset = KinectDataset(
        subjects_dirs=MASTER_ROOT_DIRS, 
        number_of_points=NUMBER_OF_POINTS,
        joints=JOINTS,
        flag='train'
    )
    
    val_dataset = KinectDataset(
        subjects_dirs=VAL_ROOT_DIRS, 
        number_of_points=NUMBER_OF_POINTS,
        joints=JOINTS,
        flag='val'
    )

    test_dataset = KinectDataset(
        subjects_dirs=TEST_ROOT_DIRS, 
        number_of_points=NUMBER_OF_POINTS,
        joints=JOINTS,
        flag='test'
    )

    train_ds = train_dataset().batch(BATCH_SIZE).cache().prefetch(tf.data.AUTOTUNE)
    val_ds = val_dataset().batch(BATCH_SIZE, drop_remainder=True).cache().prefetch(tf.data.AUTOTUNE)
    test_ds = test_dataset().batch(BATCH_SIZE).cache().prefetch(tf.data.AUTOTUNE)

    if NORMALIZATION != '':
        train_ds = train_ds.map(normalization_options[NORMALIZATION])
        val_ds = val_ds.map(normalization_options[NORMALIZATION])
        test_ds = test_ds.map(normalization_options[NORMALIZATION])   
        
    # Create model and compile
    model = create_pointnet(NUMBER_OF_POINTS, len(JOINTS))
    
    if type(THRESHOLDS) == float or type(THRESHOLDS) == int or len(THRESHOLDS) == 1:
        metrics = percentual_correct_keypoints(THRESHOLDS)
    else:
        metrics = [percentual_correct_keypoints(t) for t in range(THRESHOLDS[0], THRESHOLDS[1])]

    model.compile(
        loss=LOSS,
        optimizer=keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        metrics=metrics
    )

    # Passing configs to wandb
    wandb.init(project=PROJECT, name=NAME)
    wandb.config = CONFIGS 
    wandb.config['train_dir'] = MASTER_ROOT_DIRS 
    wandb.config['val_dir'] = VAL_ROOT_DIRS 


    def scheduler(epoch, lr):
        if epoch < 5:
            return lr
        else:
            return lr * tf.math.exp(-0.1)

    early_stopping_cb = tf.keras.callbacks.EarlyStopping(
        monitor='val_loss',
        patience=5,
        mode='auto'
    )
    
    ckpt_dir = os.path.join(CKPT_DIR, PROJECT, NAME)

    cp_cb = tf.keras.callbacks.ModelCheckpoint(
        filepath=ckpt_dir, 
        verbose=1, 
        save_weights_only=False,
        monitor='val_loss', 
        save_best_only=True,
        mode='auto'
        )

    lr_cb = tf.keras.callbacks.LearningRateScheduler(scheduler, verbose=0)

    model.fit(
         train_ds,
         epochs=EPOCHS, 
         validation_data=val_ds, 
         callbacks=[
            cp_cb,
            early_stopping_cb,
            lr_cb, 
            WandbCallback()
            ],
     )

    logs_dir = os.path.join(LOGS_DIR, PROJECT, NAME)

    # wandb.tensorflow.log(
    #     tf.summary.create_file_writer(os.path.join(logs_dir, 'tf_experiments'))
    # )

    test_loss, test_metric = model.evaluate(test_ds, steps=test_dataset.dataset_size)

    logging.info("Mean loss, Mean PCK:" + str(test_loss) + ', ' + str(test_metric))
    print("Mean loss, Mean PCK:" + str(test_loss) + ', ' + str(test_metric))
