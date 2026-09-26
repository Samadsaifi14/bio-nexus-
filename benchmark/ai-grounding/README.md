# BBS-2 AI grounding-gate fixed set

This benchmark evaluates the deterministic BioNexus grounding gate against a
predeclared set of supported and unsupported numeric, citation and evidence-link
cases. It measures whether the gate's pass/fail decision matches the supplied
evidence contract.

It does **not** evaluate a language model's biological knowledge, does not prove
that a supported claim is biologically true, and does not substitute for expert
scientific review. The acceptance criterion is 100% agreement with the
predeclared gate decisions in `cases.json`.
