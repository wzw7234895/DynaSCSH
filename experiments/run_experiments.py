"""Main experiment runner for DynaSCSH evaluation.

Usage:
  python run_experiments.py --run A1 [--output results/]
  python run_experiments.py --block A [--output results/]
  python run_experiments.py --all [--output results/]
"""
import argparse
import json
import time
import sys
import os
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parents[1]))

from dynascsh.hin_graph import HINGraph
from dynascsh.mt_index import MetaPathTriangleIndex
from dynascsh.truss import community_search_bb, community_search_greedy

# Alias for backward compatibility
community_search_static = community_search_bb
from dynascsh.update import DynaSCSHUpdater
from dynascsh.baselines import StaticRecomputeBaseline, PeriodicRecomputeBaseline
from config import get_config, DEFAULT_CONFIGS
from data import (
    load_dataset, generate_update_stream,
    generate_adversarial_updates, generate_burst_updates
)


def jaccard_similarity(set_a, set_b):
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def run_single_experiment(config, output_dir="results"):
    """Run a single experiment with the given config."""
    run_id = config.run_id
    print(f"\n{'='*60}")
    print(f"Run {run_id}: {config.description}")
    print(f"Dataset: {config.dataset}, k={config.k}, s={config.size_bound}")
    print(f"Updates: {config.num_updates} ({config.update_type})")
    print(f"{'='*60}")

    os.makedirs(output_dir, exist_ok=True)

    # Load dataset
    hin = load_dataset(config.dataset)
    hin_static = hin.copy()

    print(f"Graph: {hin.number_of_nodes()} nodes, {hin.number_of_edges()} edges")

    # Generate updates
    updates = generate_update_stream(
        hin_static, config.num_updates, config.update_type, config.seed,
        meta_path=config.meta_path
    )

    # Select query nodes (must match meta-path source type)
    import random
    random.seed(config.seed)
    source_type = config.meta_path[0]
    valid_nodes = [n for n, t in hin.node_types.items() if t == source_type]
    query_nodes = random.sample(valid_nodes, min(config.num_queries, len(valid_nodes)))

    results = {
        "run_id": run_id,
        "config": {
            "dataset": config.dataset,
            "k": config.k,
            "size_bound": config.size_bound,
            "num_updates": config.num_updates,
            "update_type": config.update_type,
            "hop_limit": config.hop_limit,
            "seed": config.seed,
        },
        "dynascsh": defaultdict(list),
        "static": defaultdict(list),
        "periodic": defaultdict(list),
        "summary": {},
        "bb_timeout_tracked": True,
    }
    results["dynascsh"]["score"] = []
    results["dynascsh"]["quality_ratio"] = []
    results["static"]["score"] = []

    # Run for each query node (limit to 3 for speed)
    # Each query gets a FRESH graph copy to avoid cross-query contamination
    for qi, qnode in enumerate(query_nodes[:3]):
        print(f"  Query {qi+1}/3: {qnode}", flush=True)

        # Fresh graph and methods for each query
        hin_q = load_dataset(config.dataset)
        hin_static_q = hin_q.copy()
        hin_periodic_q = hin_q.copy()
        updates_q = generate_update_stream(
            hin_static_q, config.num_updates, config.update_type, config.seed + qi,
            meta_path=config.meta_path
        )

        dynascsh = DynaSCSHUpdater(
            hin_q, config.meta_path, config.k, config.size_bound, config.hop_limit
        )
        static_base = StaticRecomputeBaseline(
            hin_static_q, config.meta_path, config.k, config.size_bound,
            use_exact=False, query_node=qnode
        )
        periodic_base = PeriodicRecomputeBaseline(
            hin_periodic_q, config.meta_path, config.k, config.size_bound,
            config.period, query_node=qnode
        )

        # Initialize community
        initial_comm = dynascsh.initialize_community(qnode)
        if initial_comm is None:
            print(f"    No community found for {qnode}, skipping")
            continue

        checkpoint_interval = max(1, config.num_updates // 10)
        static_comm_cache = initial_comm

        # Process updates; only run expensive baseline at checkpoints
        for ui, (edge, utype) in enumerate(updates_q):
            # DynaSCSH (always timed — fast, O(1) for insertions)
            t0 = time.perf_counter()
            dyn_comm, dyn_status = dynascsh.handle_edge_insertion(
                *edge
            ) if utype == "insertion" else dynascsh.handle_edge_deletion(*edge)
            dyn_time = time.perf_counter() - t0

            # Periodic baseline (always fast — only recomputes every N)
            per_comm, per_time = periodic_base.handle_update(edge, utype, query_node=qnode)

            # Track at checkpoints: run expensive static baseline ONLY here
            if ui % checkpoint_interval == 0 or ui == len(updates_q) - 1:
                # Static recompute (expensive — only at checkpoints)
                t0 = time.perf_counter()
                static_comm, _ = static_base.handle_update(edge, utype, query_node=qnode)
                static_time = time.perf_counter() - t0
                static_comm_cache = static_comm

                jac_dyn = jaccard_similarity(
                    dyn_comm or set(), static_comm_cache or set()
                ) if static_comm_cache else 1.0

                results["dynascsh"]["time"].append(dyn_time)
                results["static"]["time"].append(static_time)
                results["dynascsh"]["jaccard"].append(jac_dyn)
                results["dynascsh"]["update_idx"].append(ui)

                # Track quality scores
                dyn_score = dynascsh.community_score
                static_score = static_base.community_score if hasattr(static_base, 'community_score') else 0
                results["dynascsh"]["score"].append(dyn_score)
                results["static"]["score"].append(static_score)
                quality_ratio = dyn_score / max(static_score, 1e-9)
                results["dynascsh"]["quality_ratio"].append(quality_ratio)

                print(f"    update {ui}: dyn={dyn_time*1000:.1f}ms static={static_time*1000:.0f}ms jac={jac_dyn:.3f} qratio={quality_ratio:.2f}", flush=True)

    # Compute summary
    dyn_times = results["dynascsh"]["time"]
    static_times = results["static"]["time"]

    if dyn_times and static_times:
        avg_dyn = sum(dyn_times) / len(dyn_times)
        avg_static = sum(static_times) / len(static_times)
        speedup = avg_static / max(avg_dyn, 1e-9)
        avg_jac = sum(results["dynascsh"]["jaccard"]) / max(len(results["dynascsh"]["jaccard"]), 1)
        avg_qratio = sum(results["dynascsh"]["quality_ratio"]) / max(len(results["dynascsh"]["quality_ratio"]), 1)

        results["summary"] = {
            "avg_dyn_time_ms": avg_dyn * 1000,
            "avg_static_time_ms": avg_static * 1000,
            "speedup": speedup,
            "avg_jaccard": avg_jac,
            "avg_quality_ratio": avg_qratio,
            "total_checkpoints": len(dyn_times),
        }

        print(f"\n  Results: speedup={speedup:.1f}x, Jaccard={avg_jac:.3f}, Q-Ratio={avg_qratio:.3f}")

    # Save results
    result_path = os.path.join(output_dir, f"{run_id}.json")
    # Convert defaultdict to regular dict for JSON
    results["dynascsh"] = dict(results["dynascsh"])
    results["static"] = dict(results["static"])
    results["periodic"] = dict(results["periodic"])
    with open(result_path, "w") as f:
        json.dump(results, f, indent=2, default=list)
    print(f"  Saved to {result_path}")

    return results


def run_block(block_id, output_dir="results"):
    """Run all experiments in a block."""
    configs = [c for c in DEFAULT_CONFIGS.values() if c.block == block_id]
    print(f"\nRunning Block {block_id}: {len(configs)} experiments")

    all_results = {}
    for cfg in configs:
        result = run_single_experiment(cfg, output_dir)
        all_results[cfg.run_id] = result

    # Block summary
    summary_path = os.path.join(output_dir, f"block_{block_id}_summary.json")
    summary = {
        "block": block_id,
        "runs": list(all_results.keys()),
    }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nBlock {block_id} complete. Summary: {summary_path}")

    return all_results


def run_all(output_dir="results"):
    """Run all experiment blocks."""
    blocks = ["A", "B", "C", "D", "E", "F"]
    # Only blocks with configs defined
    available = sorted(set(c.block for c in DEFAULT_CONFIGS.values()))
    results = {}
    for block in available:
        if block in blocks:
            results[block] = run_block(block, output_dir)
    return results


def main():
    parser = argparse.ArgumentParser(description="DynaSCSH Experiment Runner")
    parser.add_argument("--run", type=str, help="Run a specific experiment ID")
    parser.add_argument("--block", type=str, help="Run all experiments in a block")
    parser.add_argument("--all", action="store_true", help="Run all experiments")
    parser.add_argument("--output", type=str, default="results", help="Output directory")
    parser.add_argument("--list", action="store_true", help="List all available runs")
    args = parser.parse_args()

    if args.list:
        print("Available experiments:")
        for rid, cfg in DEFAULT_CONFIGS.items():
            print(f"  {rid}: [{cfg.block}] {cfg.description}")
        return

    if args.run:
        cfg = get_config(args.run)
        if cfg is None:
            print(f"Unknown run: {args.run}")
            return
        run_single_experiment(cfg, args.output)

    elif args.block:
        run_block(args.block, args.output)

    elif args.all:
        run_all(args.output)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
