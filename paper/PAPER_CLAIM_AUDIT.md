# Paper Claim Audit Report

**Date**: 2026-07-20
**Auditor**: GPT-5.5 zero-context sidecar (stale-claim check) plus local deterministic post-fix reconciliation.
**Paper**: Dynamic Size-Constrained Community Search over Evolving Heterogeneous Information Networks

## Overall Verdict: PASS

All current headline numerical claims in the compiled paper source match the available raw or compact evidence files under standard rounding. Earlier unsupported claims were removed or scoped rather than retained.

## Claims Verified

| ID | Location | Evidence | Status | Notes |
|---|---|---|---|---|
| C1 | Abstract, Introduction, Section 5.2, Conclusion | results/results_all_22.csv insertion rows | rounding_ok | Insertion rows=17; mean speedup=3823.995484; Jaccard range=(1.0, 1.0); Q-Ratio range=(0.999858, 1.003699). |
| C2 | Abstract, Introduction, Section 5.2, Conclusion | results/results_all_22.csv deletion rows A2/B2/D1 and results/D1.json | rounding_ok | Deletion rows=3; mean speedup=2188.172519; Jaccard range=(0.36236, 0.543979); Q-Ratio range=(0.886833, 0.915944); D1 speedup=1.427013. |
| C3 | Section 5.2 Table 3 | results/results_all_22.csv and corresponding raw JSON files | rounding_ok | Displayed table values use standard rounding; D1 is shown as 1.4x rather than the integer-rounded CSV convenience field. |
| C4 | Section 5.4, Figure 3, and Hybrid table | results/hybrid_summary.json | rounding_ok | Hybrid speed range=5853.011053--10653.955491; dyn_ms max=0.158632; static_ms range=902.051045--943.596036; deletion Q-Ratio range=0.932690--0.934100. |
| C5 | Section 5.4 targeted repair table and caption | results/hybrid_targeted_repair.json | exact_match | Compact targeted-repair evidence is intentionally separate from random-stream hybrid latency evidence. |
| C6 | Method, Section 5.1, Limitations | paper source grep and algorithm condition in sections/s4_method.tex | exact_match | The manuscript now describes the community-miss fast path qualitatively and states that its hit rate must be measured per deployment. |
| C7 | Method and setup | experiments/verify_invariants.py, experiments/config.py, experiments/dynascsh/update.py, experiments/dynascsh/baselines.py | exact_match | verify_invariants.py passes and checks query preservation plus community validation smoke coverage. |
| C8 | Figure 1 teaser | results/results_all_22.csv | rounding_ok | The regenerated teaser uses current type-level means: insertion 3824x, deletion 2188x, mixed 4856x; histogram/scatter use all 22 current rows. |

## Removed Or Scoped Claims

- fixed-percentage fast-path rate
- fixed-percentage community-edge hit rate
- hop-limit stress table
- scaled-graph path-dependence claim
- hybrid Q-Ratio time-series claim
- hybrid memory overhead claim

## Aggregate Checks

- 17 insertion rows mean speedup: 3824.00x; all insertion Jaccard values are 1.000.
- Three deletion rows mean speedup: 2188.17x; Jaccard range 0.362--0.544; Q-Ratio range 0.887--0.916.
- Hybrid speedup range: 5853.01--10653.96x, displayed as 5,900--10,700x; dynamic latency max 0.159 ms.
- Figure 1 type means: insertion 3824.00x; deletion 2188.17x; mixed 4855.60x.
- Targeted hybrid repair evidence remains separate from random-stream hybrid latency evidence.
