# REA process-view compatibility repair

The original process-ownership blocker is resolved by running REA in a compatible isolated Linux VM. The local Work environment remains incompatible: Node reports PID 2 while its mounted `/proc/self/stat` reports a different host PID, and `/proc/2` is absent. Child `ps` consequently fails with `fatal library error, lookup self`. A Node upgrade or another REA installation does not repair that namespace/procfs mismatch.

## Verified environment

- Vercel Sandbox universal image pinned to `sha256:c77f7436b9bc0a8b01ef7b09dbcea2de6a18a9fe2aafa89996d2da193da72cf0`.
- Observed Node 24.21.0, REA 6.4.0, Linux amd64.
- Final VM: 4 vCPUs, 8192 MiB, 10-minute maximum lifetime, non-persistent.
- Egress restricted to npm's registry and the selected Galaxy/Terra public hosts.
- Actual Node PID, procfs PID and process table agree. REA's process ownership checks stayed enabled; vendor bootstrap code was parsed as inert text.
- Both temporary sessions were stopped after exporting evidence.

The VM can be recreated through the connected Vercel Sandbox tools using the pinned image and these settings. Install REA 6.4.0 in the VM, run the process-view preflight, then invoke its supported CLI. This is developer analysis tooling; it does not change production BioNexus execution.

## Repeatable preflight

From a repository checkout with dependencies installed:

```sh
npm ci --prefix tools/rea
npm run check-environment --prefix tools/rea
npm run analyze --prefix tools/rea -- /absolute/application/path --analysis-timeout-ms 30000 --max-heap-mb 512 --format json --full-output
```

`analyze` runs the preflight first and exits 78 on an incompatible process view. Four regression tests cover consistent identity, namespace mismatch, missing/failed process tables and unsupported Node/platform combinations: `npm test --prefix tools/rea`.

## Executed evidence

| Input | Parsing | Semantic boundary |
|---|---|---|
| Synthetic two-file compatibility fixture | Successful; full evidence retained | Synthetic probe only; not a competitor benchmark |
| Terra's actual public `index-B0iiWytN.js`, decoded 33,258 bytes | 5,729 AST nodes, zero parse failures | 3,047 semantic nodes and 3,960 relationships retained; 784 static unknowns. Parent coverage is `unknown`, untruncated. Only the selected entry was analyzed; lazy application modules remain outside scope. |
| Galaxy's actual public `analysis.bundled.js`, 7,036,751 bytes | 2,212,013 AST nodes, zero parse failures | Semantic stage exhausted the configured 2-GiB heap, then also a 5-GiB heap in the 8-GiB VM. Coverage remains partial/truncated, with 12 explicit unknown scopes. |

Successful parsing resolves the process blocker. It does not establish complete semantic recovery, observed backend behavior or competitor equivalence. The large Galaxy bundle needs a different resource/partitioning strategy for its semantic stage; additional identical installations will not resolve that heap limit.

`runtime-report.json` records the observed host checks, input hashes, parent evidence identities, raw-parent hashes and remaining limits. `fixture-evidence.json` retains the complete generated fixture evidence. `terra-summary-evidence.json` and `galaxy-summary-evidence.json` are REA-generated authenticated summary views linked to their parent evidence. Their summary-view completeness is separate from the parent semantic coverage. Full public-app parent records were processed in the temporary VM and are not retained in this repository.

Sources: [REA installation](https://github.com/morluto/rea/blob/main/docs/installation.md), [REA application workflow](https://github.com/morluto/rea/blob/main/.agents/skills/reverse-engineer-anything/references/javascript-applications.md), [Vercel Sandbox](https://vercel.com/docs/sandbox).
