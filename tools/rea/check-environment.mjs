import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

export function checkEnvironment({
  pid = process.pid,
  nodeVersion = process.versions.node,
  platform = process.platform,
  readStat = () => readFileSync('/proc/self/stat', 'utf8'),
  readProcessTable = () => execFileSync('ps', ['-axo', 'pid=,ppid=,pgid=,uid=,stat=,command='], { encoding: 'utf8', timeout: 5000 }),
} = {}) {
  const [major, minor] = nodeVersion.split('.').map(Number);
  const nodeSupported = (major === 22 && minor >= 19) || (major === 24 && minor >= 11) || major >= 26;
  const result = { nodeVersion, platform, pid, nodeSupported, compatible: false };
  if (!nodeSupported) return { ...result, reason: 'Unsupported Node version for pinned REA 6.4.0' };
  if (platform !== 'linux') return { ...result, reason: 'This preflight verifies Linux only; use the provider-specific REA readiness check on other platforms' };
  try {
    result.procSelfPid = Number(readStat().split(' ')[0]);
    if (result.procSelfPid !== pid) return { ...result, reason: 'PID namespace and procfs disagree; use an isolated VM with its own consistent procfs' };
    result.psReportsSelf = readProcessTable().split('\n').some(line => Number(line.trim().split(/\s+/)[0]) === pid);
    if (!result.psReportsSelf) return { ...result, reason: 'Process table does not report this process' };
    return { ...result, compatible: true };
  } catch {
    return { ...result, reason: 'Cannot verify process identity through procfs and procps; REA safeguards must remain enabled' };
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const result = checkEnvironment();
  process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  if (!result.compatible) process.exitCode = 78;
}
