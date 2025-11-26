import numpy as np
import cv2
import mediapipe as mp
import os

# List of (image filename, keypoints filename) for each pose
POSES = [
    ('tree.png', 'tree.npy'),
    ('ardhachandrasana.png', 'ardhachandrasana.npy'),
    ('baddhakonasana.png', 'baddhakonasana.npy'),
    ('triangle.png', 'triangle.npy'),
    ('utkatasana.png', 'utkatasana.npy'),
    ('veerabhadrasana.png', 'veerabhadrasana.npy'),
]

# Path to your pose images and where to save keypoints
IMG_DIR = os.path.join('public', 'images')
SAVE_DIR = os.path.join('static', 'ideal_poses')

mp_pose = mp.solutions.pose

def extract_and_save_keypoints(image_file, npy_file):
    image_path = os.path.join(IMG_DIR, image_file)
    save_path = os.path.join(SAVE_DIR, npy_file)
    image = cv2.imread(image_path)
    if image is None:
        print(f"Image not found: {image_path}")
        return
    pose = mp_pose.Pose(static_image_mode=True, model_complexity=2)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = pose.process(image_rgb)
    if results.pose_landmarks:
        keypoints = np.array([[lm.x, lm.y] for lm in results.pose_landmarks.landmark])
        print(f"Extracted keypoints shape: {keypoints.shape} from {image_file}")
        if keypoints.shape == (33, 2):
            np.save(save_path, keypoints)
            print(f"Saved keypoints to {save_path}")
        else:
            print(f"Warning: Shape {keypoints.shape} unexpected for {image_file}")
    else:
        print(f"No pose detected in the image: {image_file}")
    pose.close()

if __name__ == "__main__":
    for img_file, npy_file in POSES:
        extract_and_save_keypoints(img_file, npy_file)
