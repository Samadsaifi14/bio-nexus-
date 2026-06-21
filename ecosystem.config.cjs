module.exports = {
  apps: [
    {
      name: 'bio-nexus-frontend',
      cwd: './bioai-platform/frontend',
      script: 'npm',
      args: ['start'],
      autorestart: true,
      watch: false,
      env: { PORT: 3000 },
    },
    {
      name: 'bio-nexus-backend',
      cwd: './bioai-platform/backend',
      script: 'python',
      args: ['-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000'],
      autorestart: true,
      watch: false,
    },
  ],
};
