"""Load real DBLP and Amazon HIN datasets."""
import numpy as np
import scipy.sparse as sp
from collections import defaultdict
from dynascsh.hin_graph import HINGraph


def load_dblp_real(data_dir="data/DBLP_processed"):
    """Load real DBLP HIN from gammagl format."""
    node_types = np.load(f"{data_dir}/node_types.npy")
    adj = sp.load_npz(f"{data_dir}/adjM.npz")
    type_names = {0: 'A', 1: 'P', 2: 'T', 3: 'C'}

    hin = HINGraph()
    for i in range(len(node_types)):
        hin.add_node(f"N{i}", type_names.get(node_types[i], '?'))

    rows, cols = adj.nonzero()
    for r, c in zip(rows, cols):
        if r < c:
            hin.add_edge(f"N{r}", f"N{c}")
        else:
            hin.add_edge(f"N{r}", f"N{c}")

    # Add co-authorship edges (A-A via shared papers)
    authors = [i for i, t in enumerate(node_types) if type_names.get(t) == 'A']
    papers = [i for i, t in enumerate(node_types) if type_names.get(t) == 'P']

    # Author -> Papers mapping
    author_papers = defaultdict(set)
    for r, c in zip(rows, cols):
        tr = type_names.get(node_types[r])
        tc = type_names.get(node_types[c])
        if tr == 'A' and tc == 'P':
            author_papers[f"N{r}"].add(f"N{c}")
        elif tr == 'P' and tc == 'A':
            author_papers[f"N{c}"].add(f"N{r}")

    # Co-authorship: A-A edges via shared papers
    author_list = list(author_papers.keys())
    coauthor_count = defaultdict(int)
    for i in range(len(author_list)):
        for j in range(i + 1, len(author_list)):
            shared = author_papers[author_list[i]] & author_papers[author_list[j]]
            if shared:
                coauthor_count[(author_list[i], author_list[j])] = len(shared)

    for (u, v), count in coauthor_count.items():
        if count >= 1:
            hin.add_edge(u, v, "coauthor")

    return hin


def load_amazon_real(path="data/com-amazon.tar.bz2"):
    """Load Amazon from KONECT."""
    import tarfile
    hin = HINGraph()

    with tarfile.open(path, 'r:bz2') as tarf:
        for member in tarf.getmembers():
            if 'out.' in member.name:
                f = tarf.extractfile(member)
                if f:
                    for line in f.read().decode().strip().split('\n'):
                        line = line.strip()
                        if not line or line.startswith('%'):
                            continue
                        parts = line.split()
                        if len(parts) >= 2:
                            u, v = f"P{parts[0]}", f"P{parts[1]}"
                            if u not in hin.graph:
                                hin.add_node(u, "P")
                            if v not in hin.graph:
                                hin.add_node(v, "P")
                            hin.add_edge(u, v, "copurchase")

    # Sample to manageable size if needed
    nodes = hin.number_of_nodes()
    if nodes > 50000:
        import networkx as nx
        largest_cc = max(nx.connected_components(hin.graph), key=len)
        core = set(list(largest_cc)[:30000])
        hin.graph = hin.graph.subgraph(core)

    return hin


if __name__ == "__main__":
    print("Loading DBLP...")
    hin = load_dblp_real()
    print(f"DBLP: {hin.number_of_nodes()} nodes, {hin.number_of_edges()} edges")
    counts = defaultdict(int)
    for n, t in hin.node_types.items():
        counts[t] += 1
    for t, c in sorted(counts.items()):
        print(f"  {t}: {c}")

    # Count A-A edges
    aa = sum(1 for u, v in hin.edges
             if hin.node_types.get(u) == 'A' and hin.node_types.get(v) == 'A')
    print(f"  A-A coauthor edges: {aa}")

    print("\nLoading Amazon...")
    try:
        hin_a = load_amazon_real()
        print(f"Amazon: {hin_a.number_of_nodes()} nodes, {hin_a.number_of_edges()} edges")
    except Exception as e:
        print(f"Amazon error: {e}")
