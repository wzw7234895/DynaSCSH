"""Meta-Path Triangle Index (MT-Index) for DynaSCSH.

Stores edge support as integer counts (not explicit triangle tuples)
to achieve O(|E|) memory. Triangle structures are computed on-demand
during cascading truss collapse.
"""
from collections import defaultdict
from itertools import combinations


class MetaPathTriangleIndex:
    """Index tracking meta-path triangle support per edge.

    Memory: O(|E|) — stores integer support counts, not triangle tuples.
    Cascading collapse resolves triangle structures on-demand.
    """

    def __init__(self, hin, meta_path):
        self.hin = hin
        self.meta_path = tuple(meta_path)
        self.edge_support = defaultdict(int)
        self.node_support = defaultdict(int)
        self._build()

    def _build(self):
        """Build index storing only support counts (not full triangles)."""
        self.edge_support.clear()
        self.node_support.clear()
        source_type = self.meta_path[0]
        sources = [n for n, t in self.hin.node_types.items() if t == source_type]
        processed = set()

        for src in sources:
            neighbors = self.hin.get_meta_path_neighbors(src, self.meta_path)
            src_type_neighbors = set()
            for nb in neighbors:
                if self.hin.node_types.get(nb) == source_type:
                    src_type_neighbors.add(nb)

            for u in src_type_neighbors:
                for v in src_type_neighbors:
                    if u <= v:
                        continue
                    # Triangle closure: all three pairs must be connected
                    if not self.hin.has_edge(u, v):
                        continue
                    if not self.hin.has_edge(src, u) or not self.hin.has_edge(src, v):
                        continue
                    # Triangle found: (src, u, v)
                    key = tuple(sorted([src, u, v]))
                    if key in processed:
                        continue
                    processed.add(key)
                    # Count each undirected edge exactly ONCE per triangle
                    for e in [(src, u), (src, v), (u, v)]:
                        e_sorted = tuple(sorted(e))
                        self.edge_support[e_sorted] += 1
                    for node in [src, u, v]:
                        self.node_support[node] += 1

    def query_edge_support(self, u, v):
        """Get meta-path triangle support count for edge (u,v)."""
        return self.edge_support.get(tuple(sorted([u, v])), 0)

    def query_node_support(self, node):
        """Get number of meta-path triangles a node participates in."""
        return self.node_support.get(node, 0)

    def rebuild(self):
        """Rebuild the index from the current graph.

        This is the exact fallback for raw HIN relation updates that may alter
        many projected source-type edges at once. The incremental add/remove
        routines below are exact for projected source-type edge updates, which
        are the update model used by the experiments.
        """
        self._build()

    def _is_source_pair(self, u, v):
        source_type = self.meta_path[0]
        return (
            self.hin.node_types.get(u) == source_type
            and self.hin.node_types.get(v) == source_type
        )

    def _triangle_witnesses_for_source_edge(self, u, v):
        """Return source-type nodes w forming a meta-path triangle with (u,v).

        The caller must invoke this while (u,v) is present in the graph. The
        method mirrors the construction logic and is used to update all three
        edge supports affected by a projected source-edge insertion/deletion.
        """
        if not self._is_source_pair(u, v) or not self.hin.has_edge(u, v):
            return set()

        neigh_u = set(self.hin.get_meta_path_neighbors(u, self.meta_path))
        neigh_v = set(self.hin.get_meta_path_neighbors(v, self.meta_path))
        common = neigh_u & neigh_v
        witnesses = set()
        source_type = self.meta_path[0]

        for w in common:
            if w in (u, v):
                continue
            if self.hin.node_types.get(w) != source_type:
                continue
            if self.hin.has_edge(u, w) and self.hin.has_edge(v, w):
                witnesses.add(w)
        return witnesses

    def _increment_triangle(self, u, v, w):
        for e in [(u, v), (u, w), (v, w)]:
            self.edge_support[tuple(sorted(e))] += 1
        for node in (u, v, w):
            self.node_support[node] += 1

    def _decrement_triangle(self, u, v, w):
        for e in [(u, v), (u, w), (v, w)]:
            key = tuple(sorted(e))
            if key in self.edge_support:
                self.edge_support[key] -= 1
                if self.edge_support[key] <= 0:
                    del self.edge_support[key]
        for node in (u, v, w):
            if node in self.node_support:
                self.node_support[node] -= 1
                if self.node_support[node] <= 0:
                    del self.node_support[node]

    def add_edge(self, u, v):
        """Update index after projected source-edge insertion."""
        if self.hin.has_edge(u, v):
            return 0

        self.hin.add_edge(u, v)
        if not self._is_source_pair(u, v):
            return 0

        witnesses = self._triangle_witnesses_for_source_edge(u, v)
        for w in witnesses:
            self._increment_triangle(u, v, w)
        return len(witnesses)

    def remove_edge(self, u, v):
        """Update index after projected source-edge deletion."""
        if not self.hin.has_edge(u, v):
            return 0

        witnesses = self._triangle_witnesses_for_source_edge(u, v)
        for w in witnesses:
            self._decrement_triangle(u, v, w)
        self.hin.remove_edge(u, v)
        return len(witnesses)

    def get_affected_nodes(self, edge):
        """Get nodes within 2 hops of edge for localized update checking."""
        u, v = edge
        affected = {u, v}
        for nb in self.hin.neighbors(u):
            affected.add(nb)
        for nb in self.hin.neighbors(v):
            affected.add(nb)
        return affected

    def find_co_triangle_edges(self, u, v, graph_edges_set):
        """Find edges in graph_edges_set that share a triangle with (u,v).
        Computed on-demand to avoid storing triangle structures."""
        co_edges = set()
        if not self._is_source_pair(u, v):
            return co_edges

        neigh_u = set(self.hin.get_meta_path_neighbors(u, self.meta_path))
        neigh_v = set(self.hin.get_meta_path_neighbors(v, self.meta_path))
        common = neigh_u & neigh_v

        for w in common:
            if w == u or w == v:
                continue
            if not self.hin.has_edge(u, w) or not self.hin.has_edge(v, w):
                continue
            for te in [(u, w), (w, u), (v, w), (w, v)]:
                if te in graph_edges_set:
                    co_edges.add(te)
        return co_edges

    @property
    def total_triangles(self):
        """Estimated unique triangle count (from node support)."""
        total_support = sum(self.node_support.values())
        return total_support // 3

    @property
    def memory_estimate(self):
        """Memory estimate in bytes (O(|E|) storage)."""
        return len(self.edge_support) * 80 + len(self.node_support) * 40
