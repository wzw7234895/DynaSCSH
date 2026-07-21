"""Experiment configuration."""
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class RunConfig:
    run_id: str
    block: str  # A, B, C, D, E, F
    description: str
    dataset: str
    meta_path: tuple
    k: int
    size_bound: int
    num_updates: int
    update_type: str  # "insertion", "deletion", "mixed"
    num_queries: int = 100
    hop_limit: int = 2
    seed: int = 42
    period: int = 10  # for periodic baseline


DEFAULT_CONFIGS = {
    "A1": RunConfig("A1", "A", "DBLP + random insertions", "dblp",
                     ("A", "P", "A"), 3, 10, 1000, "insertion"),
    "A2": RunConfig("A2", "A", "DBLP + random deletions", "dblp",
                     ("A", "P", "A"), 3, 10, 1000, "deletion"),
    "A3": RunConfig("A3", "A", "DBLP + mixed insert/delete", "dblp",
                     ("A", "P", "A"), 3, 10, 1000, "mixed"),
    "A4": RunConfig("A4", "A", "Amazon + random insertions", "amazon",
                     ("U", "B", "U"), 4, 15, 1000, "insertion"),
    "A5": RunConfig("A5", "A", "Amazon + random deletions", "amazon",
                     ("U", "B", "U"), 4, 15, 1000, "deletion"),
    "A6": RunConfig("A6", "A", "Freebase + mixed", "freebase",
                     ("E", "T", "E"), 5, 20, 500, "mixed"),
    "A7_s5": RunConfig("A7_s5", "A", "DBLP s=5", "dblp",
                        ("A", "P", "A"), 3, 5, 500, "insertion"),
    "A7_s10": RunConfig("A7_s10", "A", "DBLP s=10", "dblp",
                         ("A", "P", "A"), 3, 10, 500, "insertion"),
    "A7_s15": RunConfig("A7_s15", "A", "DBLP s=15", "dblp",
                         ("A", "P", "A"), 3, 15, 500, "insertion"),
    "A7_s20": RunConfig("A7_s20", "A", "DBLP s=20", "dblp",
                         ("A", "P", "A"), 3, 20, 500, "insertion"),
    "A8_k3": RunConfig("A8_k3", "A", "DBLP k=3", "dblp",
                        ("A", "P", "A"), 3, 10, 500, "insertion"),
    "A8_k4": RunConfig("A8_k4", "A", "DBLP k=4", "dblp",
                        ("A", "P", "A"), 4, 10, 500, "insertion"),
    "A8_k5": RunConfig("A8_k5", "A", "DBLP k=5", "dblp",
                        ("A", "P", "A"), 5, 10, 500, "insertion"),
    "A8_k6": RunConfig("A8_k6", "A", "DBLP k=6", "dblp",
                        ("A", "P", "A"), 6, 10, 500, "insertion"),
    "B1": RunConfig("B1", "B", "DBLP insert Jaccard tracking", "dblp",
                     ("A", "P", "A"), 3, 10, 1000, "insertion"),
    "B2": RunConfig("B2", "B", "DBLP delete Jaccard tracking", "dblp",
                     ("A", "P", "A"), 3, 10, 1000, "deletion"),
    "C1_full": RunConfig("C1_full", "C", "Full DynaSCSH", "dblp",
                          ("A", "P", "A"), 3, 10, 500, "insertion"),
    "C2_index_only": RunConfig("C2_index_only", "C", "MT-Index only (no repair)", "dblp",
                                ("A", "P", "A"), 3, 10, 500, "insertion"),
    "C3_no_index": RunConfig("C3_no_index", "C", "No index", "dblp",
                              ("A", "P", "A"), 3, 10, 500, "insertion"),
    "C4_h1": RunConfig("C4_h1", "C", "h=1 hop limit", "dblp",
                        ("A", "P", "A"), 3, 10, 500, "insertion"),
    "C5_h2": RunConfig("C5_h2", "C", "h=2 hop limit", "dblp",
                        ("A", "P", "A"), 3, 10, 500, "insertion"),
    "C6_h3": RunConfig("C6_h3", "C", "h=3 hop limit", "dblp",
                        ("A", "P", "A"), 3, 10, 500, "insertion"),
    "C7_hinf": RunConfig("C7_hinf", "C", "h=inf (no hop limit)", "dblp",
                          ("A", "P", "A"), 3, 10, 500, "insertion"),
    "D1": RunConfig("D1", "D", "Truss-breaking deletions", "dblp",
                     ("A", "P", "A"), 3, 10, 500, "deletion"),
    "D2": RunConfig("D2", "D", "Burst updates", "dblp",
                     ("A", "P", "A"), 3, 10, 500, "mixed"),
}


def get_config(run_id):
    if run_id in DEFAULT_CONFIGS:
        return DEFAULT_CONFIGS[run_id]
    return DEFAULT_CONFIGS.get(run_id.split("_")[0])


def save_configs(path="experiments/configs.json"):
    configs = {k: asdict(v) for k, v in DEFAULT_CONFIGS.items()}
    with open(path, "w") as f:
        json.dump(configs, f, indent=2)
