const express = require('express');
const multer = require('multer');
const fs = require('fs');
const bcrypt = require('bcryptjs');
const session = require('express-session');
const bodyParser = require('body-parser');
const path = require('path');
const { execFile } = require('child_process');

const app = express();
const PORT = 3000;
const USERS_FILE = 'users.json';

// Serve evaluated videos directly by web path
app.use('/evaluated_videos', express.static('evaluated_videos'));

// Body & static middleware
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));
app.use(express.static('public'));
app.use('/static', express.static('static'));
app.use(session({
  secret: 'supersecretkey123',
  resave: false,
  saveUninitialized: false,
}));

// Multer config for file uploads (.mp4)
const upload = multer({
  dest: 'uploads/',
  fileFilter: (req, file, cb) => {
    if (file.mimetype.startsWith('video/')) cb(null, true);
    else cb(new Error('Only video files allowed!'), false);
  }
});

function getUsers() {
  if (!fs.existsSync(USERS_FILE)) return [];
  return JSON.parse(fs.readFileSync(USERS_FILE));
}
function saveUsers(users) {
  fs.writeFileSync(USERS_FILE, JSON.stringify(users, null, 2));
}
function isAuthenticated(req) {
  return !!(req.session && req.session.user);
}
function authMiddleware(req, res, next) {
  if (isAuthenticated(req)) next();
  else res.redirect('/login.html');
}

// Basic routes
app.get('/', (req, res) => {
  if (isAuthenticated(req)) res.sendFile(path.join(__dirname, 'public', 'dashboard.html'));
  else res.redirect('/login.html');
});
app.get('/dashboard', authMiddleware, (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'dashboard.html'));
});
app.get('/login', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'login.html'));
});
app.get('/signup', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'signup.html'));
});
app.get('/physical', authMiddleware, (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'physical.html'));
});
app.get('/physical_test/:test', authMiddleware, (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'physical_test.html'));
});
// Yoga test selection (secure, user must be logged in)
app.get('/yoga', authMiddleware, (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'yoga_select.html'));
});
// Yoga pose detection (live feedback/practice page)
app.get('/pose/:pose', authMiddleware, (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'yoga_detect.html'));
});

// User management
app.post('/signup', async (req, res) => {
  const { username, password } = req.body;
  const users = getUsers();
  if (users.find(u => u.username === username)) {
    return res.status(400).json({ success: false, message: 'User already exists' });
  }
  const hashed = await bcrypt.hash(password, 10);
  users.push({ username, password: hashed });
  saveUsers(users);
  res.json({ success: true, message: 'Signup successful' });
});
app.post('/login', async (req, res) => {
  const { username, password } = req.body;
  const users = getUsers();
  const user = users.find(u => u.username === username);
  if (!user || !(await bcrypt.compare(password, user.password))) {
    return res.status(401).json({ success: false, message: 'Invalid username or password' });
  }
  req.session.user = { username };
  res.json({ success: true, message: 'Login successful' });
});
app.post('/logout', (req, res) => {
  req.session.destroy(() => res.json({ success: true, message: 'Logged out successfully' }));
});

// Core: Upload, process, return evaluated video
app.post('/upload', authMiddleware, upload.single('video'), (req, res) => {
  if (!req.file || !req.body.testType) {
    return res.status(400).json({ error: 'Missing video or test type' });
  }
  const videoPath = req.file.path;
  const testType = req.body.testType.toLowerCase();

  execFile('python', ['eval_script.py', testType, videoPath], (err, stdout, stderr) => {
    // Remove uploaded video after processing
    fs.unlink(videoPath, () => {});

    if (err) {
      return res.status(500).json({ error: 'Python script failed', details: stderr || err.toString() });
    }

    // Try parse JSON
    let result, parsed = false;
    try {
      result = JSON.parse(stdout);
      parsed = true;
    } catch (e) {
      result = { terminal: stdout };
    }
    result.terminal = parsed ? (result.terminal || stdout) : stdout;
    if (result.video) result.video = result.video.replace(/\\/g, '/');
    res.json(result);
  });
});

// Start
app.listen(PORT, () => console.log(`Server running at http://localhost:${PORT}`));
