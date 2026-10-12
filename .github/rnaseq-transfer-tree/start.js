const { spawn } = require('child_process');
const path = require('path');

const frontendDir = path.join(__dirname, 'bioai-platform', 'frontend');
const backendDir = path.join(__dirname, 'bioai-platform', 'backend');

const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';

// Local dev launcher only: fixed argv arrays, no user input reaches spawn.
const npmSpawn = () => spawn(npm, ['start'], { // nosemgrep
  cwd: frontendDir,
  stdio: 'inherit',
  env: { ...process.env, PORT: '3000' },
  shell: true, // npm.cmd on win32 requires a shell; args are hardcoded
});
npmSpawn();

const backendPython = path.join(backendDir, '.venv', 'Scripts', 'python.exe');

spawn(backendPython, ['-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000'], { // nosemgrep
  cwd: backendDir,
  stdio: 'inherit',
  shell: true, // win32 path resolution; args are hardcoded
});
