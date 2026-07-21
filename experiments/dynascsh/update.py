"""DynaSCSH: incremental community update with cached internal support."""
from collections import defaultdict, deque

from .mt_index import MetaPathTriangleIndex
from .truss import community_search_greedy


class DynaSCSHUpdater:
    """Delta-based maintenance for size-constrained community search in HINs.

    The implementation preserves the original query node across all fallback
    recomputations, keeps a small exact internal support cache for the current
    community, and validates localized repairs before returning them.
    """

    def __init__(self, hin, meta_path, k, size_bound, hop_limit=2):
        self.hin = hin
        self.meta_path = tuple(meta_path)
        self.k = k
        self.size_bound = size_bound
        self.hop_limit = hop_limit
        self.source_type = meta_path[0]

        self.mt_index = MetaPathTriangleIndex(hin, meta_path)
        self.current_community = None
        self.query_node = None
        self.community_score = 0
        self.internal_support = {}
        self.full_recompute_count = 0
        self.total_update_count = 0
        self.local_repair_count = 0

    def initialize_community(self, query_node):
        """Compute the initial community and build the internal support cache."""
        self.query_node = query_node
        community, score, _ = community_search_greedy(
            self.hin, self.meta_path, query_node, self.k, self.size_bound
        )
        self.current_community = community
        self.community_score = score
        if community:
            self._build_internal_support()
        return community

    def _build_internal_support(self):
        """Rebuild exact internal supports for the maintained community."""
        self.internal_support = {}
        if not self.current_community:
            return
        self.internal_support, _ = self._internal_support_map(self.current_community)

    def _get_violating_edges_fast(self):
        """Return community edges whose cached internal support is below k."""
        return {
            (u, v)
            for (u, v), support in self.internal_support.items()
            if support < self.k
        }

    def _score_community(self, community):
        """Use the same score formula as the greedy static baseline."""
        if not community or len(community) <= 1:
            return 0

        nodes = list(community)
        edges = 0
        total_support = 0
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                u, v = nodes[i], nodes[j]
                if self.hin.has_edge(u, v):
                    edges += 1
                    total_support += self.mt_index.query_edge_support(u, v)

        density = 2 * edges / (len(community) * (len(community) - 1))
        avg_support = total_support / max(edges, 1)
        return density + 0.01 * avg_support

    def _refresh_current_score(self):
        self.community_score = self._score_community(self.current_community)

    def _internal_support_map(self, community):
        """Compute internal support and triangle witnesses for a node set."""
        support = {}
        witnesses = {}
        if not community:
            return support, witnesses

        comm_set = set(community)
        nodes = list(comm_set)
        graph_edges = set(self.hin.edges)

        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                u, v = nodes[i], nodes[j]
                if not self.hin.has_edge(u, v):
                    continue

                valid_w = set()
                for te in self.mt_index.find_co_triangle_edges(u, v, graph_edges):
                    w = te[0] if te[0] not in (u, v) else te[1]
                    if w in comm_set:
                        valid_w.add(w)

                ekey = tuple(sorted([u, v]))
                support[ekey] = len(valid_w)
                witnesses[ekey] = valid_w

        return support, witnesses

    def _has_triangle_connectivity(self, community, support=None, witnesses=None):
        """Check edge connectivity through shared internal triangles."""
        if support is None or witnesses is None:
            support, witnesses = self._internal_support_map(community)

        valid_edges = {edge for edge, sup in support.items() if sup >= self.k}
        if not valid_edges:
            return False

        edge_adj = defaultdict(set)
        for edge in valid_edges:
            u, v = edge
            for w in witnesses.get(edge, set()):
                e1 = tuple(sorted([u, w]))
                e2 = tuple(sorted([v, w]))
                triangle_edges = [e for e in (edge, e1, e2) if e in valid_edges]
                for a in triangle_edges:
                    for b in triangle_edges:
                        if a != b:
                            edge_adj[a].add(b)

        start = next(iter(valid_edges))
        seen = {start}
        queue = deque([start])
        while queue:
            edge = queue.popleft()
            for nb in edge_adj.get(edge, set()):
                if nb not in seen:
                    seen.add(nb)
                    queue.append(nb)
        return seen == valid_edges

    def _community_is_valid(self, community, exact_size=True):
        """Validate size, query containment, internal support, and connectivity."""
        if not community:
            return False
        community = set(community)
        if exact_size and len(community) != self.size_bound:
            return False
        if self.query_node is not None and self.query_node not in community:
            return False
        if any(self.hin.node_types.get(n) != self.source_type for n in community):
            return False

        support, witnesses = self._internal_support_map(community)
        if not support:
            return False
        if any(sup < self.k for sup in support.values()):
            return False

        active_nodes = set()
        for u, v in support:
            active_nodes.add(u)
            active_nodes.add(v)
        if not community.issubset(active_nodes):
            return False

        return self._has_triangle_connectivity(community, support, witnesses)

    def validate_current_community(self):
        """Diagnostic used by smoke tests and artifact verification."""
        return self._community_is_valid(self.current_community, exact_size=True)

    def handle_edge_insertion(self, u, v):
        """Handle edge insertion. Insertions cannot reduce current validity."""
        self.total_update_count += 1
        self.mt_index.add_edge(u, v)

        if self.current_community is None:
            self.full_recompute_count += 1
            return self._full_recompute(), "emerged_from_insertion"

        if u in self.current_community and v in self.current_community:
            self._build_internal_support()
            self._refresh_current_score()

        return self.current_community, "valid_unchanged"

    def handle_edge_deletion(self, u, v):
        """Handle edge deletion with exact small-community validation."""
        self.total_update_count += 1
        self.mt_index.remove_edge(u, v)

        if self.current_community is None:
            return None, "no_community"

        if u not in self.current_community or v not in self.current_community:
            return self.current_community, "unchanged"

        self._build_internal_support()
        violating = self._get_violating_edges_fast()
        if not violating and self._has_triangle_connectivity(self.current_community):
            self._refresh_current_score()
            return self.current_community, "valid_unchanged"

        repaired = self._localized_repair_fast({u, v}, violating)
        if repaired is not None and len(repaired) == self.size_bound:
            self.local_repair_count += 1
            self.current_community = repaired
            self._build_internal_support()
            self._refresh_current_score()
            return repaired, "locally_repaired"

        self.full_recompute_count += 1
        return self._full_recompute(), "full_recomputed"

    def _localized_repair_fast(self, affected_nodes, violating_edges):
        """Try one-node localized repair and validate before returning."""
        if not self.current_community:
            return None

        community = set(self.current_community)
        node_violation_count = defaultdict(int)
        for u, v in violating_edges:
            node_violation_count[u] += 1
            node_violation_count[v] += 1
        if not node_violation_count:
            for node in affected_nodes:
                node_violation_count[node] += 1

        sorted_nodes = sorted(node_violation_count.items(), key=lambda x: -x[1])
        for node, _ in sorted_nodes:
            if node not in community or node == self.query_node:
                continue

            trial = set(community)
            trial.discard(node)
            replacement = self._find_best_replacement(trial, affected_nodes | {node})
            if replacement is None:
                continue

            trial.add(replacement)
            if self._community_is_valid(trial, exact_size=True):
                return trial

        return None

    def _candidate_nodes_within_hops(self, affected_nodes):
        """Enumerate source-type candidates inside the configured hop radius."""
        if self.hop_limit is None or self.hop_limit == float("inf"):
            return {
                n
                for n, t in self.hin.node_types.items()
                if t == self.source_type
            }

        limit = max(0, int(self.hop_limit))
        visited = set(affected_nodes)
        queue = deque((node, 0) for node in affected_nodes)
        candidates = set()

        while queue:
            node, depth = queue.popleft()
            if depth >= limit:
                continue
            for nb in self.hin.neighbors(node):
                if nb in visited:
                    continue
                visited.add(nb)
                next_depth = depth + 1
                if self.hin.node_types.get(nb) == self.source_type:
                    candidates.add(nb)
                queue.append((nb, next_depth))

        return candidates

    def _find_best_replacement(self, community, affected_nodes):
        """Find the best valid replacement within hop_limit of the affected area."""
        community = set(community)
        candidates = self._candidate_nodes_within_hops(affected_nodes)

        candidates = {
            n
            for n in candidates
            if n not in community and n != self.query_node
        }
        if not candidates:
            return None

        valid = []
        for candidate in candidates:
            trial = set(community)
            trial.add(candidate)
            if self._community_is_valid(trial, exact_size=True):
                valid.append(candidate)

        if not valid:
            return None

        return max(
            valid,
            key=lambda n: (
                sum(1 for nb in self.hin.neighbors(n) if nb in community),
                self.mt_index.query_node_support(n),
            ),
        )

    def _full_recompute(self):
        """Full recomputation using the original query node."""
        query_node = self.query_node
        if query_node is None:
            if self.current_community is None:
                return None
            query_node = next(iter(self.current_community))

        community, score, _ = community_search_greedy(
            self.hin, self.meta_path, query_node, self.k, self.size_bound
        )
        self.current_community = community
        self.community_score = score
        if community:
            self._build_internal_support()
        return community

    def get_stats(self):
        return {
            "total_updates": self.total_update_count,
            "full_recomputes": self.full_recompute_count,
            "local_repairs": self.local_repair_count,
            "recompute_rate": self.full_recompute_count / max(self.total_update_count, 1),
            "repair_rate": self.local_repair_count / max(self.total_update_count, 1),
            "community_size": len(self.current_community) if self.current_community else 0,
            "cached_support_entries": len(self.internal_support),
            "query_node": self.query_node,
            "valid_current": self.validate_current_community()
            if self.current_community else False,
        }
