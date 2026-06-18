const { spawn } = require('child_process');
const path = require('path');

const frontendDir = path.join(__dirname, 'bioai-platform', 'frontend');
const backendDir = path.join(__dirname, 'bioai-platform', 'backend');

// Start frontend
const frontend = spawn('npm.cmd', ['start'], {
  cwd: frontendDir,
  stdio: 'inherit',
  env: { ...process.env, PORT: '3000' },
  shell: true,
});

// Start backend
const backend = spawn('python', ['-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000'], {
  cwd: backendDir,
  stdio: 'inherit',
  shell: true,
});

process.on('SIGINT', () => {
  frontend.kill();
  backend.kill();
  process.exit();
});
