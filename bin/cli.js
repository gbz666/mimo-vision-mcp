#!/usr/bin/env node
'use strict';

const { spawn, spawnSync } = require('child_process');
const path = require('path');

const scriptPath = path.join(__dirname, '..', 'mimo_vision.py');

function findPython() {
  const candidates = process.platform === 'win32'
    ? ['python', 'python3', 'py']
    : ['python3', 'python'];

  for (const cmd of candidates) {
    try {
      const r = spawnSync(cmd, ['--version'], { stdio: 'pipe' });
      if (r.status !== 0) continue;
      const out = (r.stdout || r.stderr).toString();
      const m = out.match(/Python (\d+)\.(\d+)/);
      if (m && (parseInt(m[1]) > 3 || (parseInt(m[1]) === 3 && parseInt(m[2]) >= 10))) {
        return cmd;
      }
    } catch (_) {}
  }
  process.stderr.write(
    '[mimo-vision-mcp] Python 3.10+ is required. Install from https://python.org\n'
  );
  process.exit(1);
}

function ensureDeps(python) {
  const check = spawnSync(python, ['-c', 'import mcp, httpx'], { stdio: 'pipe' });
  if (check.status === 0) return;

  process.stderr.write('[mimo-vision-mcp] Installing Python dependencies...\n');
  const install = spawnSync(
    python,
    ['-m', 'pip', 'install', '--quiet', 'mcp>=1.0.0', 'httpx>=0.27.0'],
    { stdio: 'inherit' }
  );
  if (install.status !== 0) {
    process.stderr.write(
      '[mimo-vision-mcp] Failed to install deps. Run manually: pip install mcp httpx\n'
    );
    process.exit(1);
  }
}

const python = findPython();
ensureDeps(python);

const proc = spawn(python, [scriptPath], {
  stdio: 'inherit',
  env: process.env,
});

proc.on('exit', (code) => process.exit(code ?? 0));
process.on('SIGINT', () => proc.kill('SIGINT'));
process.on('SIGTERM', () => proc.kill('SIGTERM'));
