from __future__ import annotations

from pathlib import Path

path = Path("bioai-platform/backend/app/routers/phylo.py")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Expected phylogeny source block not found:\n{old[:240]}")
    text = text.replace(old, new, 1)


replace_once(
    "import logging\nimport threading\nimport time\nimport uuid\n",
    "import logging\nimport re\nimport threading\nimport time\nimport uuid\n",
)

replace_once(
    '    model: str         = "LG"\n    bootstrap: int     = Field(100, ge=0, le=1000)',
    '    model: Optional[str] = None\n    bootstrap: int     = Field(100, ge=0, le=1000)',
)

replace_once(
    '    bootstrap: Optional[int]\n    phase: JobPhase',
    '    bootstrap: Optional[int]\n    bootstrap_requested: Optional[int] = None\n    bootstrap_effective: Optional[int] = None\n    engine: Optional[str] = None\n    phase: JobPhase',
)

replace_once(
    'class RunResponse(BaseModel):\n    job_id: str\n    status: str\n\n\n# ─── In-memory store',
    '''class RunResponse(BaseModel):
    job_id: str
    status: str


_SAFE_TAXON_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
_DNA_IUPAC = set("ACGTRYSWKMBDHVN")
_PROTEIN_IUPAC = set("ACDEFGHIKLMNPQRSTVWYBXZJUO")


def _validate_sequence_records(sequences: list[dict], seq_type: str) -> list[dict]:
    """Validate and normalize unaligned records before sending them to MSA.

    Taxon identifiers are restricted to a Newick/PHYLIP-safe token alphabet so
    the same identifier survives FASTA -> alignment -> tree -> export without
    silent truncation or reinterpretation. Sequence characters are validated
    against the declared molecule type; no auto-correction is performed.
    """
    if seq_type not in ("protein", "dna"):
        raise ValueError("seq_type must be 'protein' or 'dna'")

    alphabet = _PROTEIN_IUPAC if seq_type == "protein" else _DNA_IUPAC
    seen: set[str] = set()
    out: list[dict] = []

    for index, raw in enumerate(sequences):
        if not isinstance(raw, dict):
            raise ValueError(f"Sequence record {index + 1} must be an object")
        ident = str(raw.get("id") or "").strip()
        seq = "".join(str(raw.get("sequence") or "").split()).upper()
        if not ident:
            raise ValueError(f"Sequence record {index + 1} is missing an identifier")
        if not _SAFE_TAXON_ID.fullmatch(ident):
            raise ValueError(
                f"Sequence identifier {ident!r} contains characters unsafe for Newick/PHYLIP; "
                "use letters, digits, underscore, dot or hyphen"
            )
        if ident in seen:
            raise ValueError(f"Duplicate sequence identifier: {ident}")
        if not seq:
            raise ValueError(f"Sequence {ident!r} is empty")
        bad = sorted(set(seq) - alphabet)
        if bad:
            raise ValueError(
                f"Sequence {ident!r} contains characters invalid for {seq_type}: {', '.join(bad)}"
            )
        seen.add(ident)
        out.append({"id": ident, "sequence": seq})

    return out


def _resolve_ml_model(model: str | None, seq_type: str) -> str:
    valid = PROTEIN_MODELS if seq_type == "protein" else DNA_MODELS
    default = "LG" if seq_type == "protein" else "GTR"
    if model is None or not str(model).strip():
        return default
    lookup = {m.lower(): m for m in valid}
    key = str(model).strip().lower()
    if key not in lookup:
        raise ValueError(
            f"Model {model!r} not valid for {seq_type}. Choose from: {', '.join(valid)}"
        )
    return lookup[key]


def _effective_iqtree_bootstrap(requested: int) -> int:
    """Return the number IQ-TREE will actually execute for UFBoot.

    IQ-TREE requires at least 1000 UFBoot replicates. A request of zero means
    no bootstrap. When a positive request below 1000 is supplied, provenance
    must record that IQ-TREE executes 1000 rather than the smaller requested
    value.
    """
    requested = max(int(requested), 0)
    return 0 if requested == 0 else max(1000, requested)


# ─── In-memory store''',
)

replace_once(
    '''            "model":     req.model,
            "bootstrap": req.bootstrap,
            "phase":     "queued",''',
    '''            "model":     _resolve_ml_model(req.model, req.seq_type) if req.method == "ml" else None,
            "bootstrap": req.bootstrap,
            "bootstrap_requested": req.bootstrap if req.method == "ml" else None,
            "bootstrap_effective": None,
            "engine": None,
            "phase":     "queued",''',
)

replace_once(
    '''def _parse_aligned_fasta(fasta: str) -> dict[str, str]:
    seqs: dict[str, str] = {}
    cur = None
    for line in fasta.strip().splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            cur = stripped[1:].split()[0]
            seqs[cur] = ""
        elif cur:
            seqs[cur] += stripped
    return seqs


def _p_distance(s1: str, s2: str) -> float:
    pairs = [(a, b) for a, b in zip(s1, s2) if a != "-" and b != "-"]
    if not pairs:
        return 1.0
    return sum(1 for a, b in pairs if a != b) / len(pairs)
''',
    '''def _parse_aligned_fasta(fasta: str) -> dict[str, str]:
    seqs: dict[str, str] = {}
    cur: str | None = None
    for line_no, line in enumerate((fasta or "").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            ident = stripped[1:].split()[0] if stripped[1:].strip() else ""
            if not ident:
                raise ValueError(f"Aligned FASTA header at line {line_no} has no identifier")
            if ident in seqs:
                raise ValueError(f"Duplicate aligned FASTA identifier: {ident}")
            if not _SAFE_TAXON_ID.fullmatch(ident):
                raise ValueError(f"Aligned FASTA identifier {ident!r} is not Newick/PHYLIP safe")
            cur = ident
            seqs[cur] = ""
        else:
            if cur is None:
                raise ValueError(f"Aligned FASTA sequence appears before a header at line {line_no}")
            seqs[cur] += "".join(stripped.split()).upper()

    if not seqs:
        return {}
    empty = [name for name, seq in seqs.items() if not seq]
    if empty:
        raise ValueError(f"Aligned FASTA contains empty sequences: {', '.join(empty)}")
    lengths = {len(seq) for seq in seqs.values()}
    if len(lengths) != 1:
        raise ValueError("All aligned FASTA sequences must have the same aligned length")
    return seqs


def _p_distance(s1: str, s2: str) -> float:
    if len(s1) != len(s2):
        raise ValueError("p-distance requires aligned sequences of equal length")
    pairs = [(a, b) for a, b in zip(s1, s2) if a != "-" and b != "-"]
    if not pairs:
        return 1.0
    return sum(1 for a, b in pairs if a != b) / len(pairs)
''',
)

replace_once(
    '''def fasta_to_phylip(fasta: str) -> str:
    """Convert aligned FASTA to relaxed PHYLIP (names up to 100 chars)."""
    seqs: dict[str, str] = {}
    cur: str | None = None
    for line in fasta.strip().splitlines():
        t = line.strip()
        if t.startswith(">"):
            cur = t[1:].split()[0][:100]
            seqs[cur] = ""
        elif cur:
            seqs[cur] += t.upper()
    if not seqs:
        return ""
    n = len(seqs)
    L = len(next(iter(seqs.values())))
    lines = [f"{n} {L}"]
    for name, s in seqs.items():
        lines.append(f"{name:<100}{s}")
    return "\\n".join(lines)
''',
    '''def fasta_to_phylip(fasta: str) -> str:
    """Convert validated aligned FASTA to relaxed PHYLIP."""
    seqs = _parse_aligned_fasta(fasta)
    if not seqs:
        return ""
    truncated = [name[:100] for name in seqs]
    if len(truncated) != len(set(truncated)):
        raise ValueError("Sequence identifiers collide after PHYLIP's 100-character limit")
    n = len(seqs)
    L = len(next(iter(seqs.values())))
    lines = [f"{n} {L}"]
    for name, s in seqs.items():
        lines.append(f"{name[:100]:<100}{s}")
    return "\\n".join(lines)
''',
)

replace_once(
    '''        bs = req.bootstrap if req.bootstrap else 0
        datatype = "aa" if req.seq_type == "protein" else "nt"
        model = req.model if req.model else ("LG" if req.seq_type == "protein" else "GTR")

        if use_iqtree:''',
    '''        bs_requested = req.bootstrap if req.bootstrap else 0
        datatype = "aa" if req.seq_type == "protein" else "nt"
        model = _resolve_ml_model(req.model, req.seq_type)

        if use_iqtree:''',
)

replace_once(
    '''            if bs > 0:
                bb = max(1000, bs)
                cmd += ["-bb", str(bb), "-alrt", str(bb)]
            # IQ-TREE timeout: ultrafast bootstrap is fast even at 1000+
            if bs <= 0:
                timeout_s = 300
            elif bs <= 1000:
                timeout_s = 600
            else:
                timeout_s = 1200
        else:
            cmd = [
                "phyml",
                "-i", aln_path,
                "-d", datatype,
                "-m", model,
                "-b", str(bs),
                "-o", "tlr",
                "--no_memory_check",
            ]
            # PhyML timeout (slow classic bootstrap)
            if bs <= 0:
                timeout_s = 900
            elif bs <= 100:
                timeout_s = 900
            elif bs <= 500:
                timeout_s = 1800
            else:
                timeout_s = 3600

        _patch(job_id, engine=engine, bootstrap=bs)
        logger.info(f"[{job_id}] Running {engine} with bootstrap={bs}")''',
    '''            bs_effective = _effective_iqtree_bootstrap(bs_requested)
            if bs_effective > 0:
                cmd += ["-bb", str(bs_effective)]
            # IQ-TREE timeout: ultrafast bootstrap is fast even at 1000+
            if bs_effective <= 0:
                timeout_s = 300
            elif bs_effective <= 1000:
                timeout_s = 600
            else:
                timeout_s = 1200
        else:
            bs_effective = bs_requested
            cmd = [
                "phyml",
                "-i", aln_path,
                "-d", datatype,
                "-m", model,
                "-b", str(bs_effective),
                "-o", "tlr",
                "--no_memory_check",
            ]
            # PhyML timeout (slow classic bootstrap)
            if bs_effective <= 0:
                timeout_s = 900
            elif bs_effective <= 100:
                timeout_s = 900
            elif bs_effective <= 500:
                timeout_s = 1800
            else:
                timeout_s = 3600

        _patch(
            job_id,
            engine=engine,
            model=model,
            bootstrap=bs_requested,
            bootstrap_requested=bs_requested,
            bootstrap_effective=bs_effective,
        )
        logger.info(
            "[%s] Running %s model=%s bootstrap requested=%d effective=%d",
            job_id, engine, model, bs_requested, bs_effective,
        )''',
)

replace_once(
    '''                   error=f"{engine} timed out after {timeout_s // 60} minutes "
                         f"(bootstrap={bs}). Try reducing to 100-200.")''',
    '''                   error=f"{engine} timed out after {timeout_s // 60} minutes "
                         f"(bootstrap requested={bs_requested}, effective={bs_effective}).")''',
)

replace_once(
    '''    if len(req.sequences) < 2:
        raise HTTPException(400, detail="At least 2 sequences are required")
    if len(req.sequences) > 50:
        raise HTTPException(400, detail="Maximum 50 sequences per run")

    valid_models = PROTEIN_MODELS if req.seq_type == "protein" else DNA_MODELS
    if req.method == "ml" and req.model not in valid_models:
        raise HTTPException(
            400,
            detail=f"Model '{req.model}' not valid for {req.seq_type}. "
                   f"Choose from: {', '.join(valid_models)}"
        )

    job_id = str(uuid.uuid4())''',
    '''    if len(req.sequences) < 2:
        raise HTTPException(400, detail="At least 2 sequences are required")
    if len(req.sequences) > 50:
        raise HTTPException(400, detail="Maximum 50 sequences per run")

    try:
        req.sequences = _validate_sequence_records(req.sequences, req.seq_type)
        if req.method == "ml":
            req.model = _resolve_ml_model(req.model, req.seq_type)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    job_id = str(uuid.uuid4())''',
)

path.write_text(text, encoding="utf-8")
print(f"patched {path}")
