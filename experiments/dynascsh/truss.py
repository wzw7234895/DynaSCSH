"""(k,P)-truss community model with B&B and greedy search methods."""
from collections import defaultdict, deque
from itertools import combinations


class KPTruss:
    """(k,P)-truss community model for HINs."""

    def __init__(self, hin, meta_path, k):
        self.hin = hin
        self.meta_path = tuple(meta_path)
        self.k = k
        self.mt_index = None
        self.source_type = meta_path[0]

    def set_mt_index(self, mt_index):
        self.mt_index = mt_index

    def compute_edge_support(self):
        """Compute meta-path triangle support for all edges."""
        support = {}
        if self.mt_index:
            for u, v in self.hin.edges:
                support[(u, v)] = self.mt_index.query_edge_support(u, v)
                support[(v, u)] = support[(u, v)]
        else:
            from .mt_index import MetaPathTriangleIndex
            idx = MetaPathTriangleIndex(self.hin, self.meta_path)
            self.mt_index = idx
            for u, v in self.hin.edges:
                support[(u, v)] = idx.query_edge_support(u, v)
                support[(v, u)] = support[(u, v)]
        return support

    def peel_to_k_truss(self):
        """Iteratively remove edges with support < k (cascading collapse)."""
        support = self.compute_edge_support()
        remaining = set()
        for e in self.hin.edges:
            remaining.add(e)
            remaining.add((e[1], e[0]))

        queue = deque()
        for e in self.hin.edges:
            if support.get(e, 0) < self.k:
                queue.append(e)

        while queue:
            e = queue.popleft()
            if e not in remaining:
                continue
            remaining.discard(e)
            remaining.discard((e[1], e[0]))

            # Find co-triangle edges on-demand (not pre-stored)
            for co_e in self.mt_index.find_co_triangle_edges(e[0], e[1], remaining):
                if co_e in remaining:
                    try:
                        support[co_e] = max(0, support.get(co_e, 0) - 1)
                        if support[co_e] == self.k - 1:
                            queue.append(co_e)
                    except KeyError:
                        pass

        return {(u, v) for u, v in remaining if u < v}

    def search_community_bb(self, query_node, size_bound):
        """Branch & Bound exact community search with full connected component."""
        k_truss_edges = self.peel_to_k_truss()
        if not k_truss_edges:
            return None, 0

        # Build adjacency from peeled k-truss
        adj = defaultdict(set)
        for u, v in k_truss_edges:
            adj[u].add(v)
            adj[v].add(u)

        if query_node not in adj:
            return None, 0

        # BFS to extract FULL connected component (guarantees exactness)
        visited = {query_node}
        queue = deque([query_node])
        while queue:
            curr = queue.popleft()
            for nb in adj[curr]:
                if nb not in visited:
                    visited.add(nb)
                    queue.append(nb)

        candidate_list = [n for n in visited
                         if self.hin.node_types.get(n) == self.source_type
                         and n != query_node]
        candidate_list.sort(key=lambda n: self.mt_index.query_node_support(n), reverse=True)

        # Greedy lower bound
        greedy_comm = self._greedy_expand(query_node, size_bound)
        best_comm = greedy_comm
        best_score = self._score_community(greedy_comm)

        # B&B: explore subsets of candidates
        def bb_search(idx, current_comm):
            nonlocal best_comm, best_score

            if len(current_comm) == size_bound:
                score = self._score_community(current_comm)
                if score > best_score:
                    best_score = score
                    best_comm = set(current_comm)
                return

            if idx >= len(candidate_list):
                return

            remaining = size_bound - len(current_comm)
            if len(candidate_list) - idx < remaining:
                return

            # Safe upper bound: max density contribution + max support contribution
            max_possible_support = sum(
                self.mt_index.query_node_support(candidate_list[k])
                for k in range(idx, min(idx + remaining, len(candidate_list)))
            )
            max_add = remaining * 1.0 + 0.01 * max_possible_support
            if best_score > 0 and self._score_community(current_comm) + max_add <= best_score:
                return

            # Branch: include candidate
            node = candidate_list[idx]
            current_comm.add(node)
            bb_search(idx + 1, current_comm)
            current_comm.discard(node)

            # Branch: skip candidate
            bb_search(idx + 1, current_comm)

        bb_search(0, {query_node})
        return best_comm, best_score

    def search_community_greedy(self, query_node, size_bound):
        """Greedy community search (heuristic, labeled as such in comparisons)."""
        k_truss_edges = self.peel_to_k_truss()
        if not k_truss_edges:
            return None, 0

        community = self._greedy_expand(query_node, size_bound)
        score = self._score_community(community)
        return community, score

    def _greedy_expand(self, query_node, size_bound):
        """Greedy expansion ensuring k-truss validity at each step."""
        community = {query_node}
        candidates = set()
        for nb in self.hin.neighbors(query_node):
            if self.hin.node_types.get(nb) == self.source_type:
                candidates.add(nb)

        while len(community) < size_bound and candidates:
            valid = [n for n in candidates
                    if self._maintains_ktruss(community, n)]
            if not valid:
                break

            best = max(valid, key=lambda n: (
                sum(1 for m in self.hin.neighbors(n) if m in community),
                self.mt_index.query_node_support(n)
            ))
            community.add(best)
            candidates.remove(best)
            for nb in self.hin.neighbors(best):
                if nb not in community and self.hin.node_types.get(nb) == self.source_type:
                    candidates.add(nb)

        # Fill remaining slots if size < size_bound
        if len(community) < size_bound:
            remaining = [n for n in candidates
                        if n not in community
                        and self.hin.node_types.get(n) == self.source_type]
            remaining.sort(key=lambda n: self.mt_index.query_node_support(n), reverse=True)
            for n in remaining:
                if len(community) >= size_bound:
                    break
                community.add(n)

        return community

    def _maintains_ktruss(self, community, new_node):
        """Check if adding new_node maintains k-truss on existing edges."""
        for member in community:
            if self.hin.has_edge(new_node, member):
                if self.mt_index.query_edge_support(new_node, member) < self.k:
                    return False
        return True

    def _score_community(self, community):
        """Score by internal edge density and average support."""
        if len(community) <= 1:
            return 0
        edges = 0
        total_support = 0
        nodes_list = list(community)
        for i in range(len(nodes_list)):
            for j in range(i + 1, len(nodes_list)):
                u, v = nodes_list[i], nodes_list[j]
                if self.hin.has_edge(u, v):
                    edges += 1
                    total_support += self.mt_index.query_edge_support(u, v)

        density = 2 * edges / (len(community) * (len(community) - 1))
        avg_support = total_support / max(edges, 1)
        return density + 0.01 * avg_support


def community_search_bb(hin, meta_path, query_node, k, size_bound):
    """B&B community search (Zhang et al. style exact baseline)."""
    kp = KPTruss(hin, meta_path, k)
    community, score = kp.search_community_bb(query_node, size_bound)
    return community, score, kp


def community_search_greedy(hin, meta_path, query_node, k, size_bound):
    """Greedy heuristic community search (fast, approximate)."""
    kp = KPTruss(hin, meta_path, k)
    community, score = kp.search_community_greedy(query_node, size_bound)
    return community, score, kp
