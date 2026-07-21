# DynaSCSH Final Fix Report

Date: 2026-07-20

This document records the final PVLDB cleanup pass for the current manuscript at `paper/main.pdf`.

## What Changed

- Removed unsupported stale claims from the manuscript: fixed-percentage fast-path/hit-rate claims, the hop-limit stress table, the scaled-graph path-dependence claim, the hybrid Q-Ratio time-series claim, and the hybrid memory-overhead claim.
- Reframed D1 as a deletion stress run supported by `results/D1.json` and `results/results_all_22.csv`, reporting 1.4x speedup rather than claiming an every-update adversarial stream.
- Tightened insertion claims: all 17 insertion rows have Jaccard=1.000, average Q-Ratio=1.000, and average speedup 3,824x; per-run rounded Q-Ratio may reach 1.004 because of greedy tie-breaking.
- Tightened deletion claims: three deletion rows have Jaccard 0.36--0.54, Q-Ratio 0.89--0.92, and average speedup 2,188x.
- Tightened hybrid claims to values present in `results/hybrid_summary.json`: 5,900--10,700x speedup, Jaccard=1.000, deletion Q-Ratio 0.933--0.934, and dynamic latency below 1 ms.
- Kept targeted hybrid repair separate from random-stream hybrid latency evidence: `results/hybrid_targeted_repair.json` supports 10/30 local repairs at k=2.
- Updated `paper/PAPER_CLAIM_AUDIT.md`, `paper/PAPER_CLAIM_AUDIT.json`, root `CLAIM_AUDIT.md`, and `ARTIFACT_README.md`.

## Verification

- `experiments/verify_invariants.py` passes.
- `paper/main.pdf` compiles with `pdflatex` to 8 pages.
- PDF text contains no unresolved references, stale oversized-speedup claims, or quality non-degradation overclaims.
- Remaining LaTeX warnings are layout-class warnings only: acmart `\vspace`, underfull vboxes, and a 1.333pt overfull vbox on the final page.

## Current Evidence Files

- `results/results_all_22.csv`
- `results/A1.json`, `results/A2.json`, `results/A3.json`, `results/B1.json`, `results/B2.json`, `results/D1.json`, `results/D2.json`
- `results/A7_s*.json`, `results/A8_k*.json`, `results/C*.json`
- `results/hybrid_summary.json`
- `results/hybrid_targeted_repair.json`
- `results/invariant_checker_overhead.csv`
