import { test } from 'node:test';
import assert from 'node:assert/strict';
import { checkEnvironment } from './check-environment.mjs';

const valid = { pid: 42, nodeVersion: '24.21.0', platform: 'linux', readStat: () => '42 (node) S', readProcessTable: () => ' 42 1 42 1000 S node\n' };
test('accepts consistent procfs and process table', () => assert.equal(checkEnvironment(valid).compatible, true));
test('fails before spawning ps when the namespace disagrees', () => {
  const result = checkEnvironment({ ...valid, readStat: () => '4888 (node) S', readProcessTable: () => assert.fail('must not spawn') });
  assert.equal(result.compatible, false);
  assert.match(result.reason, /namespace/);
});
test('fails closed on missing identity and procps failure', () => {
  assert.equal(checkEnvironment({ ...valid, readProcessTable: () => '7 1 7 1000 S node' }).compatible, false);
  assert.equal(checkEnvironment({ ...valid, readProcessTable: () => { throw new Error('lookup self'); } }).compatible, false);
});
test('rejects unsupported Node versions and unverified platforms', () => {
  for (const nodeVersion of ['20.19.0', '22.18.0', '23.0.0', '24.10.0', '25.0.0']) assert.equal(checkEnvironment({ ...valid, nodeVersion }).compatible, false);
  assert.equal(checkEnvironment({ ...valid, platform: 'darwin' }).compatible, false);
});
