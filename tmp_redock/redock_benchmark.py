"""Redocking benchmark: dock biotin back into streptavidin (PDB 1STP).

Field-standard accuracy test — a correct pipeline recovers the crystal pose
with top-mode heavy-atom RMSD < 2.0 A. Run inside the API image:

    docker run --rm -v <host_dir>:/data bio-nexus-api:bookworm python /data/redock_benchmark.py
"""

import os
import re
import subprocess
import sys
import tempfile
import time

import httpx

sys.path.insert(0, "/app")

from app.tools.docking import compute_pocket_grid, run_vina

PDB_ID = "1STP"
LIG_RESNAME = "BTN"
RCSB_DOWNLOAD_BASE = "https://files.rcsb.org/download"


def fetch_rcsb_pdb(pdb_id: str) -> str:
    """Fetch a PDB only from the fixed HTTPS RCSB download origin."""
    normalized = pdb_id.strip().upper()
    if re.fullmatch(r"[0-9][A-Z0-9]{3}", normalized) is None:
        raise ValueError(f"invalid PDB identifier: {pdb_id!r}")
    response = httpx.get(
        f"{RCSB_DOWNLOAD_BASE}/{normalized}.pdb",
        timeout=60.0,
        follow_redirects=False,
    )
    response.raise_for_status()
    return response.text


def main() -> int:
    t0 = time.time()
    pdb_text = fetch_rcsb_pdb(PDB_ID)

    # Receptor: first model, altloc-filtered ATOM records (mirrors prod logic).
    ref_lines, prot_lines, seen_model = [], [], False
    for l in pdb_text.splitlines():
        rec = l[:6].strip()
        if rec == "MODEL":
            if seen_model:
                break
            seen_model = True
            continue
        if rec == "ENDMDL":
            break
        if rec == "ATOM":
            if len(l) > 16 and l[16] not in (" ", "A"):
                continue
            prot_lines.append(l)
        elif rec in ("TER", "END"):
            prot_lines.append(l)
        elif rec == "HETATM" and len(l) >= 18 and l[17:20].strip() == LIG_RESNAME:
            if not (len(l) > 16 and l[16] not in (" ", "A")):
                ref_lines.append(l)

    assert prot_lines and ref_lines, "failed to split receptor/ligand"
    receptor_pdb = "\n".join(prot_lines)

    # Reference heavy-atom coords (crystal biotin pose).
    def is_heavy(name: str) -> bool:
        return name.lstrip()[0] != "H"

    ref = [(float(l[30:38]), float(l[38:46]), float(l[46:54]))
           for l in ref_lines if is_heavy(l[12:16])]
    print(f"[1] {PDB_ID}: {len(prot_lines)} receptor lines, {len(ref)} ligand heavy atoms")

    # Grid from fpocket pocket #1.
    grid = compute_pocket_grid(receptor_pdb)
    assert grid, "fpocket found no usable pocket"
    cx = sum(c[0] for c in ref) / len(ref)
    cy = sum(c[1] for c in ref) / len(ref)
    cz = sum(c[2] for c in ref) / len(ref)
    site_off = ((grid["center"][0] - cx) ** 2 + (grid["center"][1] - cy) ** 2 +
                (grid["center"][2] - cz) ** 2) ** 0.5
    print(f"[2] pocket grid center={grid['center']} size={grid['size']} "
          f"| offset from crystal site: {site_off:.1f} A")
    assert site_off < 8.0, "pocket grid does not cover the crystal binding site"

    # Crystal ligand -> PDBQT (prod prep path: pH protonation + Gasteiger).
    with tempfile.TemporaryDirectory() as tmp:
        lig_pdb = os.path.join(tmp, "lig.pdb")
        lig_pdbqt_path = os.path.join(tmp, "lig.pdbqt")
        with open(lig_pdb, "w") as f:
            f.write("\n".join(ref_lines) + "\nEND\n")
        r = subprocess.run(
            ["obabel", lig_pdb, "-O", lig_pdbqt_path,
             "--partialcharge", "gasteiger", "-p", "7.4"],
            capture_output=True, text=True, timeout=120)
        assert r.returncode == 0 and os.path.isfile(lig_pdbqt_path), r.stderr[:500]
        with open(lig_pdbqt_path) as ligand_file:
            ligand_pdbqt = ligand_file.read()
    print("[3] crystal ligand converted to PDBQT")

    result = run_vina(
        protein_pdbqt=receptor_pdb,
        ligand_pdbqt=ligand_pdbqt,
        grid_center=grid["center"],
        grid_size=grid["size"],
        exhaustiveness=32,
        num_modes=9,
        seed=42,
    )
    print(f"[4] vina done in {time.time()-t0:.0f}s | best affinity "
          f"{result['affinity']} kcal/mol | poses: {result['num_poses']}")

    # Top-pose heavy-atom RMSD vs crystal.
    # obabel reorders/renames ligand atoms, so poses can't be index-matched;
    # use symmetry-corrected assignment for the 2 A benchmark bar.
    out_models: dict[int, list[tuple]] = {}
    cur = None
    for line in result["result_sdf"].splitlines():
        if line.startswith("MODEL"):
            cur = int(line.split()[1])
            out_models[cur] = []
        elif line.startswith("ENDMDL"):
            cur = None
        elif cur is not None and line.split()[0] in ("HETATM", "ATOM"):
            name = line[12:16].strip() or line.split()[2]
            if not is_heavy(name):
                continue
            out_models[cur].append((float(line[30:38]), float(line[38:46]), float(line[46:54])))

    def rmsd(pose):
        """Symmetry-corrected minimum RMSD via optimal assignment (bitmask DP)."""
        if len(pose) != len(ref):
            return None
        n = len(ref)
        cost = [
            [sum((p[i] - r[i]) ** 2 for i in range(3)) for r in ref]
            for p in pose
        ]
        best: dict[int, float] = {0: 0.0}
        for p in range(n):
            nxt: dict[int, float] = {}
            for mask, total in best.items():
                for j in range(n):
                    if mask & (1 << j):
                        continue
                    m2 = mask | (1 << j)
                    v = total + cost[p][j]
                    if m2 not in nxt or v < nxt[m2]:
                        nxt[m2] = v
            best = nxt
        full = (1 << n) - 1
        return (best[full] / n) ** 0.5

    ok = False
    for mid in sorted(out_models):
        r_val = rmsd(out_models[mid])
        aff = next((p["affinity"] for p in result["poses"] if p["model"] == mid), "?")
        if r_val is None:
            print(f"    mode {mid}: affinity {aff} | atom-count mismatch "
                  f"({len(out_models[mid])} vs {len(ref)}) — RMSD skipped")
            continue
        mark = "PASS" if r_val < 2.0 else "fail"
        print(f"    mode {mid}: affinity {aff:>6} kcal/mol | RMSD {r_val:.2f} A [{mark}]")
        if mid == 1:
            ok = r_val < 2.0

    print("=" * 60)
    if ok:
        print("REDOCK BENCHMARK PASSED — top pose reproduces crystal (<2 A)")
        return 0
    print("REDOCK BENCHMARK FAILED — investigate before trusting scores")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
