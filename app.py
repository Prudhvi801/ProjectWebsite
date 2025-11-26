from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import sqlite3
import uuid
import cv2
import numpy as np
import mediapipe as mp
import traceback
import bcrypt
import subprocess
import json
import shutil

app = Flask(__name__, template_folder='public', static_folder='static')
app.secret_key = 'replace-with-a-strong-secret'
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB max upload size
DB_PATH = 'users.db'

POSES = [
    {"key": "tree", "name": "Tree Pose", "image": "/static/images/tree.png"},
    {"key": "ardhachandrasana", "name": "Ardha Chandrasana", "image": "/static/images/ardhachandrasana.png"},
    {"key": "baddhakonasana", "name": "Baddha Konasana", "image": "/static/images/baddhakonasana.png"},
    {"key": "triangle", "name": "Triangle Pose", "image": "/static/images/triangle.png"},
    {"key": "utkatasana", "name": "Utkata Konasana", "image": "/static/images/utkatasana.png"},
    {"key": "veerabhadrasana", "name": "Veerabhadrasana", "image": "/static/images/veerabhadrasana.png"}
]

# --- Database Helpers ---
def db_execute(query, args=(), one=False):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(query, args)
    conn.commit()
    results = c.fetchall()
    conn.close()
    return (results[0] if results else None) if one else results

def db_create_users():
    db_execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE, 
        password TEXT
    )''')
db_create_users()

# --- Video Conversion Helper ---
def convert_to_h264(input_path, output_path):
    """
    Converts video to H.264 format using FFmpeg for browser compatibility.
    Returns True if successful, False otherwise.
    """
    try:
        if shutil.which('ffmpeg') is None:
            print("FFmpeg not found. Skipping conversion.")
            return False

        print(f"Converting {input_path} to H.264...")
        command = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vcodec', 'libx264',
            '-acodec', 'aac',
            '-movflags', 'faststart',
            output_path
        ]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("Conversion successful!")
        return True
    except Exception as e:
        print(f"Video conversion failed: {e}")
        return False

# --- Routes ---

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            uname = data.get('username')
            pwd = data.get('password')
        else:
            uname = request.form.get('username')
            pwd = request.form.get('password')
            
        exists = db_execute('SELECT * FROM users WHERE username=?', (uname,), one=True)
        if exists:
            error = "Username exists!"
            if request.is_json:
                return jsonify({'success': False, 'message': error}), 400
            else:
                return render_template('signup.html', error=error)
                
        hashed = bcrypt.hashpw(pwd.encode('utf-8'), bcrypt.gensalt())
        db_execute('INSERT INTO users(username, password) VALUES (?,?)', (uname, hashed))
        
        if request.is_json:
            return jsonify({'success': True, 'redirect': url_for('login')})
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            uname = data.get('username')
            pwd = data.get('password')
        else:
            uname = request.form.get('username')
            pwd = request.form.get('password')
            
        row = db_execute('SELECT * FROM users WHERE username=?', (uname,), one=True)
        
        if row:
            if bcrypt.checkpw(pwd.encode('utf-8'), row[2]):
                session['user'] = uname
                return jsonify({'success': True, 'redirect': url_for('dashboard')}) if request.is_json else redirect(url_for('dashboard'))
            else:
                error = "Incorrect password"
        else:
            error = "Account not found. Please Sign Up."

        if request.is_json:
            return jsonify({'success': False, 'message': error}), 401

    return render_template('login.html', error=error)

@app.route('/logout', methods=['POST', 'GET'])
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/physical')
def physical():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('physical.html')

@app.route('/yoga')
def yoga():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('yoga_select.html', poses=POSES)

@app.route('/physical_test/<test>', methods=['GET', 'POST'])
def physical_test(test):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        video = request.files.get('video')
        if not video:
            return "No video file", 400
            
        uploads_dir = os.path.join(app.static_folder, 'uploads')
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)
            
        savename = f"{test}_{uuid.uuid4().hex}.mp4"
        filepath = os.path.join(uploads_dir, savename)
        video.save(filepath)
        
        try:
            result = subprocess.run(
                ['python', 'eval_script.py', test, filepath],
                capture_output=True,
                text=True,
                timeout=900
            )
            
            output_json = result.stdout.strip().splitlines()[-1]
            try:
                res_data = json.loads(output_json)
                summary = res_data['result']
                raw_video_path = res_data['video'].lstrip('/')
                
                if not raw_video_path.startswith('evaluated_videos/'):
                    filename = os.path.basename(raw_video_path)
                    rel_path = f"evaluated_videos/{filename}"
                else:
                    rel_path = raw_video_path

                full_source_path = os.path.join(app.static_folder, rel_path)
                web_filename = f"web_{os.path.basename(rel_path)}"
                web_rel_path = f"evaluated_videos/{web_filename}"
                full_dest_path = os.path.join(app.static_folder, web_rel_path)

                conversion_success = False
                if os.path.exists(full_source_path):
                    if convert_to_h264(full_source_path, full_dest_path):
                        conversion_success = True
                
                if conversion_success:
                    download_url = url_for('static', filename=web_rel_path)
                else:
                    download_url = url_for('static', filename=rel_path)

            except Exception as ex:
                print(f"JSON Parse Error: {ex}")
                summary = f"Analysis complete, but output parsing failed.\nRaw: {output_json}"
                download_url = url_for('static', filename=f"uploads/{savename}")
                
        except Exception as e:
            print(f"Script Error: {e}")
            summary = f"Error running analysis: {e}"
            download_url = url_for('static', filename=f"uploads/{savename}")

        return render_template('physical_result.html',
                               result=summary,
                               download_url=download_url)
                               
    return render_template('physical_test.html', test=test)

@app.route('/pose/<pose_name>')
def show_pose_page(pose_name):
    if 'user' not in session:
        return redirect(url_for('login'))
    pose = next((p for p in POSES if p['key'] == pose_name), None)
    if not pose:
        return "Pose not found!", 404
    return render_template('yoga_detect.html', ideal_img=pose["image"], pose_name=pose_name)

@app.route('/compare_pose/<pose_name>', methods=['POST'])
def compare_pose(pose_name):
    try:
        print(f"compare_pose received: {pose_name}")
        if 'frame' not in request.files:
            print("No frame in request")
            return jsonify({'feedback': 'No frame in request', 'matches': [], 'user_keypoints': [], 'accuracy': 0})
        
        file = request.files['frame']
        arr = np.frombuffer(file.read(), np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        
        if frame is None:
            print("Frame read error")
            return jsonify({'feedback': 'Frame read error', 'matches': [], 'user_keypoints': [], 'accuracy': 0})

        mp_pose = mp.solutions.pose
        pose_model = mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.5, min_tracking_confidence=0.5)
        results = pose_model.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        feedback = "No pose detected"
        matches = []
        user_keypoints = []
        accuracy = 0

        if results.pose_landmarks:
            # Extract landmarks
            user_keypoints = np.array([[lm.x, lm.y] for lm in results.pose_landmarks.landmark])
            
            # Path to ideal pose
            ideal_path = os.path.join(app.static_folder, 'ideal_poses', f'{pose_name}.npy')
            
            # Check if file exists
            if not os.path.exists(ideal_path):
                # Return user_keypoints to prevent blinking even if ideal pose is missing
                return jsonify({
                    'feedback': 'Ideal pose keypoints not found', 
                    'matches': [], 
                    'user_keypoints': user_keypoints.tolist(), 
                    'accuracy': 0
                })
            
            ideal_kps = np.load(ideal_path)
            
            # Check shape mismatch
            if user_keypoints.shape != ideal_kps.shape:
                # Return user_keypoints to prevent blinking
                return jsonify({
                    'feedback': f'Keypoint shape mismatch', 
                    'matches': [], 
                    'user_keypoints': user_keypoints.tolist(), 
                    'accuracy': 0
                })
            
            # Calculate matches and accuracy
            tolerance = 0.09
            # Check if absolute difference is within tolerance for both X and Y
            match_bools = np.all(np.abs(user_keypoints - ideal_kps) < tolerance, axis=1)
            matches = match_bools.tolist()
            match_count = np.sum(match_bools)
            
            # Accuracy based on count of matched points vs total points
            if len(matches) > 0:
                accuracy = int((match_count / len(matches)) * 100)
            
            feedback = f"Accuracy: {accuracy}%" + (" - Great job!" if accuracy == 100 else " - Keep adjusting!")

        return jsonify({
            'feedback': feedback,
            'matches': matches,
            'user_keypoints': user_keypoints.tolist() if len(user_keypoints) > 0 else [],
            'accuracy': accuracy
        })
    except Exception as e:
        print("Exception in compare_pose:", repr(e))
        traceback.print_exc()
        return jsonify({'feedback': f'Error: {repr(e)}', 'matches': [], 'user_keypoints': [], 'accuracy': 0})

@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')

if __name__ == "__main__":
    uploads_dir = os.path.join('static', 'uploads')
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
    print("---- Flask server running ----")
    app.run(debug=True, port=5000)