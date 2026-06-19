import os
import sys
import cv2
import mediapipe as mp
import numpy as np
import math
import time
import json

EVAL_FOLDER = os.path.join("static", "evaluated_videos")
os.makedirs(EVAL_FOLDER, exist_ok=True)

mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

def draw_text(img, text, position, color=(36,255,12), font_scale=0.7, thickness=2, shadow=True):
    x, y = position
    font = cv2.FONT_HERSHEY_SIMPLEX
    if shadow:
        cv2.putText(img, text, (x+2, y+2), font, font_scale, (0,0,0), thickness+2, cv2.LINE_AA)
    cv2.putText(img, text, (x, y), font, font_scale, color, thickness, cv2.LINE_AA)

def calculate_angle(a, b, c):
    a, b, c = np.array(a), np.array(b), np.array(c)
    radians = math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(a[1] - b[1], a[0] - b[0])
    angle = abs(radians * 180.0 / math.pi)
    return 360 - angle if angle > 180 else angle

def squat_test(cap, out):
    counter, stage, live_feedback = 0, None, "Start!"
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False
        results = pose.process(image)
        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            hip = [landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x, landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y]
            knee = [landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x, landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y]
            ankle = [landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x, landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y]
            angle = calculate_angle(hip, knee, ankle)
            if angle > 160: 
                stage = 'up'
                live_feedback = "Go Lower!"
            if angle < 90 and stage == 'up':
                stage = 'down'
                counter += 1
                live_feedback = "Nice rep!"
            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
        else:
            live_feedback = "Pose not detected"
        draw_text(image, f"Squat Counter: {counter}", (10, 35), (255, 70, 0), 0.8, 2)
        draw_text(image, f"{live_feedback}", (10, 65), (72, 255, 120), 0.75, 2)
        out.write(image)
    return f"Squat Test Complete. Total Squats: {counter}"

def pushup_test(cap, out):
    counter, stage, live_feedback = 0, None, "Start!"
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image_rgb.flags.writeable = False
        results = pose.process(image_rgb)
        image_rgb.flags.writeable = True
        image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
            left_elbow = landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value]
            left_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]
            right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
            right_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value]
            elbow_angle = calculate_angle(
                [left_shoulder.x, left_shoulder.y],
                [left_elbow.x, left_elbow.y],
                [left_wrist.x, left_wrist.y]
            )
            hands_on_ground = (left_wrist.y > left_shoulder.y) and (right_wrist.y > right_shoulder.y)
            if hands_on_ground:
                if elbow_angle > 160: 
                    stage = 'up'
                    live_feedback = "Go Deeper!"
                if elbow_angle < 90 and stage == 'up':
                    stage = 'down'
                    counter += 1
                    live_feedback = "Good pushup!"
            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
        else:
            live_feedback = "Pose not detected"
        draw_text(image, f"Pushup Counter: {counter}", (10, 35), (255, 70, 0), 0.8, 2)
        draw_text(image, f"{live_feedback}", (10, 65), (72, 255, 120), 0.75, 2)
        out.write(image)
    return f"Pushup Test Complete. Total Pushups: {counter}"

def jump_test(cap, out):
    real_hip_height_cm = 100
    baseline_hip_y, prev_hip_y = None, None
    jump_started, max_jump_height_px, jump_count = False, 0, 0
    live_feedback, output = "Start!", ""
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image_rgb.flags.writeable = False
        results = pose.process(image_rgb)
        image_rgb.flags.writeable = True
        image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            left_hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP.value]
            hip_y_px = int(left_hip.y * frame.shape[0])
            if baseline_hip_y is None:
                baseline_hip_y = hip_y_px
                pixels_hip_height = frame.shape[0] - baseline_hip_y
                pixels_per_cm = pixels_hip_height / real_hip_height_cm if pixels_hip_height else 1
            if prev_hip_y is not None:
                if not jump_started and (baseline_hip_y - hip_y_px) > 30:
                    jump_started = True
                    max_jump_height_px = baseline_hip_y - hip_y_px
                    live_feedback = "Jump started!"
                if jump_started and (baseline_hip_y - hip_y_px) > max_jump_height_px:
                    max_jump_height_px = baseline_hip_y - hip_y_px
                if jump_started and (hip_y_px >= baseline_hip_y - 10):
                    jump_started = False
                    jump_count += 1
                    jump_height_cm = max_jump_height_px / pixels_per_cm
                    live_feedback = f"Jump {jump_count}: {jump_height_cm:.2f} cm"
                    output += live_feedback + "\n"
            prev_hip_y = hip_y_px
            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
        else:
            live_feedback = "Pose not detected"
        draw_text(image, f"Jump Counter: {jump_count}", (10, 35), (255, 70, 0), 0.8, 2)
        draw_text(image, f"{live_feedback}", (10, 65), (72, 255, 120), 0.75, 2)
        out.write(image)
    output += f"Jump Test Complete. Total jumps: {jump_count}"
    return output

def hexagon_test(cap, out):
    output = "Hexagon Test evaluation not implemented yet.\n"
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        # Overlay feedback on each frame
        draw_text(frame, "Hexagon Test evaluation not implemented.", (10, 35), (200, 90, 200), 0.8, 2)
        out.write(frame)
    return output


def process_video(video_path, test_function):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(json.dumps({"result": f"Error: Could not open video file: {video_path}", "video": ""}))
        sys.exit(1)

    # Try to determine a reliable FPS
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    # Ignore garbage FPS values (very low, huge, NaN)
    if fps is None or fps != fps or fps < 10 or fps > 120:
        # Try inferring FPS based on file duration, if possible
        duration_secs = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0 if cap.get(cv2.CAP_PROP_POS_MSEC) > 0 else 0
        if frame_count > 0 and duration_secs > 0:
            fps = frame_count / duration_secs
        else:
            fps = 25.0  # fallback if no info is available
    else:
        fps = float(fps)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if width == 0 or height == 0:
        print(json.dumps({"result": "Error: video frame size not determined.", "video": ""}))
        sys.exit(1)

    filename = os.path.basename(video_path)
    name, ext = os.path.splitext(filename)
    out_path = os.path.join(EVAL_FOLDER, f"{name}_eval.mp4")
    relative_path = f"evaluated_videos/{name}_eval.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
    if not out.isOpened():
        print(json.dumps({"result": f"Failed to open VideoWriter for {out_path}", "video": ""}))
        sys.exit(1)
    output_text = test_function(cap, out)
    cap.release()
    out.release()
    if not os.path.exists(out_path) or os.path.getsize(out_path) < 1000:
        print(json.dumps({"result": f"Error: Output video not created or too small: {out_path}", "video": ""}))
        sys.exit(1)
    return output_text, relative_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"result": "Usage: python eval_script.py <test_type> <video_path>", "video": ""}))
        sys.exit(1)
    test_type = sys.argv[1].lower()
    video_path = sys.argv[2]
    if not os.path.exists(video_path):
        print(json.dumps({"result": f"Error: Video not found at {video_path}", "video": ""}))
        sys.exit(1)
    start_time = time.time()
    try:
        if test_type == 'squats':
            result_text, out_video = process_video(video_path, squat_test)
        elif test_type == 'pushups':
            result_text, out_video = process_video(video_path, pushup_test)
        elif test_type == 'jumps':
            result_text, out_video = process_video(video_path, jump_test)
        elif test_type == 'hexagon':
            result_text, out_video = process_video(video_path, hexagon_test)
        else:
            result_text = "Unknown test type"
            out_video = video_path
        duration = time.time() - start_time
        result_text += f"\nProcessing Time: {duration:.2f} sec"
        print(json.dumps({"result": result_text, "video": out_video.replace('\\', '/') }))
    except Exception as ex:
        print(json.dumps({"result": f"Unexpected error: {ex}", "video": ""}))
        sys.exit(1)
