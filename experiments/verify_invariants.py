"""Post-fix invariant smoke checks for DynaSCSH.

Run from the project root:
  python code/experiments/verify_invariants.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from dynascsh.baselines import StaticRecomputeBaseline
from dynascsh.hin_graph import HINGraph
from dynascsh.mt_index import MetaPathTriangleIndex
from dynascsh.update import DynaSCSHUpdater


def build_tiny_author_graph():
    hin = HINGraph()
    for author in ("A0", "A1", "A2", "A3"):
        hin.add_node(author, "A")
    hin.add_node("P0", "P")
    for author in ("A0", "A1", "A2", "A3"):
        hin.add_edge(author, "P0", "writes")
    for edge in (("A0", "A1"), ("A0", "A2"), ("A1", "A2"), ("A0", "A3")):
        hin.add_edge(*edge, edge_type="coauthor")
    return hin


def check_mt_index_coedge_updates():
    hin = build_tiny_author_graph()
    idx = MetaPathTriangleIndex(hin, ("A", "P", "A"))

    assert idx.query_edge_support("A0", "A1") == 1
    added = idx.add_edge("A1", "A3")
    assert added == 1
    assert idx.query_edge_support("A0", "A1") == 2
    assert idx.query_edge_support("A0", "A3") == 1
    assert idx.query_edge_support("A1", "A3") == 1

    removed = idx.remove_edge("A1", "A3")
    assert removed == 1
    assert idx.query_edge_support("A0", "A1") == 1
    assert idx.query_edge_support("A1", "A3") == 0


def check_query_preservation_and_validation():
    hin = build_tiny_author_graph()
    updater = DynaSCSHUpdater(hin, ("A", "P", "A"), k=1, size_bound=3, hop_limit=2)
    community = updater.initialize_community("A0")
    assert community is not None
    assert updater.query_node == "A0"
    assert updater.validate_current_community()

    baseline = StaticRecomputeBaseline(
        hin.copy(), ("A", "P", "A"), k=1, size_bound=3,
        use_exact=False, query_node="A0"
    )
    baseline.handle_update(("A1", "A2"), "deletion")
    assert baseline.get_stats()["query_node"] == "A0"


def main():
    check_mt_index_coedge_updates()
    check_query_preservation_and_validation()
    print("Invariant smoke checks passed.")


if __name__ == "__main__":
    main()
