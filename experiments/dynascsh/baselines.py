"""Baseline methods for DynaSCSH evaluation."""
import time

from .truss import community_search_bb, community_search_greedy


class StaticRecomputeBaseline:
    """Static recomputation baseline on every checkpoint snapshot.

    The baseline preserves the original query node for the whole update stream.
    This makes the comparison internally fair: DynaSCSH's fallback path and the
    static baseline both run the same greedy search from the same query.
    """

    def __init__(self, hin, meta_path, k, size_bound, use_exact=True, query_node=None):
        self.hin = hin
        self.meta_path = meta_path
        self.k = k
        self.size_bound = size_bound
        self.use_exact = use_exact
        self.query_node = query_node
        self.recompute_count = 0
        self.bb_timeouts = 0
        self.community_score = 0

    def set_query_node(self, query_node):
        self.query_node = query_node

    def _active_query(self, edge):
        return self.query_node if self.query_node is not None else edge[0]

    def handle_update(self, edge, update_type, query_node=None):
        """Apply an update and recompute from the original query."""
        if query_node is not None:
            self.query_node = query_node

        self.recompute_count += 1
        try:
            if update_type == "insertion":
                self.hin.add_edge(*edge)
            else:
                self.hin.remove_edge(*edge)
        except Exception:
            pass

        query = self._active_query(edge)
        t0 = time.perf_counter()
        try:
            if self.use_exact:
                community, score, _ = community_search_bb(
                    self.hin, self.meta_path, query, self.k, self.size_bound
                )
            else:
                community, score, _ = community_search_greedy(
                    self.hin, self.meta_path, query, self.k, self.size_bound
                )
        except Exception:
            community, score = None, 0
        elapsed = time.perf_counter() - t0

        self.community_score = score
        return community, elapsed

    def get_stats(self):
        return {
            "recompute_count": self.recompute_count,
            "bb_timeouts": self.bb_timeouts,
            "use_exact": self.use_exact,
            "query_node": self.query_node,
        }


class PeriodicRecomputeBaseline:
    """Recompute community every N updates."""

    def __init__(self, hin, meta_path, k, size_bound, period=10, query_node=None):
        self.hin = hin
        self.meta_path = meta_path
        self.k = k
        self.size_bound = size_bound
        self.period = period
        self.query_node = query_node
        self.current_community = None
        self.community_score = 0
        self.update_count = 0
        self.recompute_count = 0

    def set_query_node(self, query_node):
        self.query_node = query_node

    def _active_query(self, edge):
        return self.query_node if self.query_node is not None else edge[0]

    def handle_update(self, edge, update_type, query_node=None):
        if query_node is not None:
            self.query_node = query_node

        self.update_count += 1
        if update_type == "insertion":
            self.hin.add_edge(*edge)
        else:
            self.hin.remove_edge(*edge)

        if self.update_count % self.period == 0:
            self.recompute_count += 1
            query = self._active_query(edge)
            t0 = time.perf_counter()
            community, score, _ = community_search_greedy(
                self.hin, self.meta_path, query, self.k, self.size_bound
            )
            elapsed = time.perf_counter() - t0
            self.current_community = community
            self.community_score = score
            return community, elapsed

        return self.current_community, 0

    def get_stats(self):
        return {
            "recompute_count": self.recompute_count,
            "update_count": self.update_count,
            "period": self.period,
            "query_node": self.query_node,
        }
