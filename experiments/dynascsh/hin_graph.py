"""Heterogeneous Information Network graph with meta-path support."""
import networkx as nx
from itertools import combinations
from collections import defaultdict
import numpy as np


class HINGraph:
    """HIN with typed nodes/edges and meta-path computation."""

    def __init__(self):
        self.graph = nx.Graph()
        self.node_types = {}
        self.edge_types = {}

    def add_node(self, node_id, node_type):
        self.graph.add_node(node_id)
        self.node_types[node_id] = node_type

    def add_edge(self, u, v, edge_type=None):
        self.graph.add_edge(u, v)
        if edge_type:
            self.edge_types[(u, v)] = edge_type
            self.edge_types[(v, u)] = edge_type

    def remove_edge(self, u, v):
        self.graph.remove_edge(u, v)
        self.edge_types.pop((u, v), None)
        self.edge_types.pop((v, u), None)

    def has_edge(self, u, v):
        return self.graph.has_edge(u, v)

    def neighbors(self, node):
        return list(self.graph.neighbors(node))

    @property
    def nodes(self):
        return self.graph.nodes

    @property
    def edges(self):
        return self.graph.edges

    def number_of_nodes(self):
        return self.graph.number_of_nodes()

    def number_of_edges(self):
        return self.graph.number_of_edges()

    def get_meta_path_instances(self, source, meta_path):
        """Find all meta-path instances starting from source following the type sequence.
        meta_path: list of node types, e.g. ['A','P','A'] for Author-Paper-Author.
        Returns list of node sequences (paths) that satisfy the type pattern.
        """
        if not meta_path:
            return []
        if self.node_types.get(source) != meta_path[0]:
            return []
        instances = []
        stack = [(source, [source], 0)]
        while stack:
            current, path, depth = stack.pop()
            if depth == len(meta_path) - 1:
                if len(path) == len(meta_path):
                    instances.append(tuple(path))
                continue
            next_type = meta_path[depth + 1]
            for nb in self.graph.neighbors(current):
                if self.node_types.get(nb) == next_type and nb not in path:
                    stack.append((nb, path + [nb], depth + 1))
        return instances

    def get_meta_path_neighbors(self, node, meta_path):
        """Get all nodes reachable via the given meta-path pattern."""
        instances = self.get_meta_path_instances(node, meta_path)
        return set(inst[-1] for inst in instances)

    def compute_meta_path_triangles(self, meta_path):
        """Find all meta-path-based triangles in the HIN.
        A meta-path triangle for path P = (T1,T2,...,Tk,T1) is formed by
        three meta-path instances that close a triangle structure.
        For symmetric meta-paths like APA: two authors u,w co-author with same author v.
        """
        triangles = defaultdict(int)
        if len(meta_path) < 3:
            return triangles
        source_type = meta_path[0]
        sources = [n for n, t in self.node_types.items() if t == source_type]
        for src in sources:
            neighbors_set = self.get_meta_path_neighbors(src, meta_path)
            for nb in neighbors_set:
                if nb <= src:
                    continue
                common = self.get_meta_path_neighbors(nb, meta_path)
                for cn in common:
                    if cn != src:
                        key = tuple(sorted([src, nb, cn]))
                        triangles[key] += 1
        return dict(triangles)

    def get_edge_meta_path_triangles(self, edge, meta_path):
        """Get all meta-path triangles that include the given edge."""
        u, v = edge
        triangles = []
        all_triangles = self.compute_meta_path_triangles(meta_path)
        for (a, b, c), count in all_triangles.items():
            if (u in (a, b, c) and v in (a, b, c)):
                triangles.append(((a, b, c), count))
        return triangles

    def subgraph_by_types(self, node_types_set):
        """Return subgraph induced by nodes of given types."""
        nodes = [n for n, t in self.node_types.items() if t in node_types_set]
        return self.graph.subgraph(nodes)

    def copy(self):
        """Deep copy the HIN."""
        g = HINGraph()
        for n, t in self.node_types.items():
            g.add_node(n, t)
        for u, v in self.graph.edges:
            et = self.edge_types.get((u, v))
            g.add_edge(u, v, et)
        return g
