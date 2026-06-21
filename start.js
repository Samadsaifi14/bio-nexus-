const { spawn } = require('child_process');
const path = require('path');

const frontendDir = path.join(__dirname, 'bioai-platform', 'frontend');
const backendDir = path.join(__dirname, 'bioai-platform', 'backend');

const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';

spawn(npm, ['start'], {
  cwd: frontendDir,
  stdio: 'inherit',
  env: { ...process.env, PORT: '3000' },
  shell: true,
});

spawn('python', ['-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000'], {
  cwd: backendDir,
  stdio: 'inherit',
  shell: true,
});
