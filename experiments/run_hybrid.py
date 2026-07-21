"""Run key experiments on hybrid graph (real DBLP + planted communities)."""
import sys, time, json, random, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from collections import defaultdict
import numpy as np
from dynascsh.hin_graph import HINGraph
from dynascsh.mt_index import MetaPathTriangleIndex
from dynascsh.update import DynaSCSHUpdater
from dynascsh.baselines import StaticRecomputeBaseline
from data import generate_update_stream


def build_hybrid_graph():
    """Build real DBLP + planted dense communities."""
    import scipy.sparse as sp
    random.seed(42)

    node_types_raw = np.load('data/DBLP_processed/node_types.npy')
    adj = sp.load_npz('data/DBLP_processed/adjM.npz')
    type_names = {0: 'A', 1: 'P', 2: 'T', 3: 'C'}

    hin = HINGraph()
    for i in range(len(node_types_raw)):
        hin.add_node(f'N{i}', type_names.get(node_types_raw[i], '?'))

    rows, cols = adj.nonzero()
    for r, c in zip(rows, cols):
        hin.add_edge(f'N{r}', f'N{c}')

    # Add co-authorship edges
    author_papers = defaultdict(set)
    for r, c in zip(rows, cols):
        tr = type_names.get(node_types_raw[r])
        tc = type_names.get(node_types_raw[c])
        if tr == 'A' and tc == 'P':
            author_papers[f'N{r}'].add(f'N{c}')
        elif tr == 'P' and tc == 'A':
            author_papers[f'N{c}'].add(f'N{r}')

    authors_list = list(author_papers.keys())
    for i in range(len(authors_list)):
        for j in range(i + 1, len(authors_list)):
            shared = author_papers[authors_list[i]] & author_papers[authors_list[j]]
            if shared:
                hin.add_edge(authors_list[i], authors_list[j], 'coauthor')

    # Inject 40 planted dense communities
    all_authors = [n for n, t in hin.node_types.items() if t == 'A']
    num_planted = 40

    for g in range(num_planted):
        gsize = random.randint(6, 12)
        group = random.sample(all_authors, gsize)
        num_papers = random.randint(12, 25)
        for pi in range(num_papers):
            p = f'PLANTED_P{g}_{pi}'
            hin.add_node(p, 'P')
            paper_auths = random.sample(group, k=random.randint(3, min(7, gsize)))
            for a in paper_auths:
                hin.add_edge(a, p, 'writes_planted')
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                hin.add_edge(group[i], group[j], 'coauthor_planted')

    return hin


def jaccard_similarity(a, b):
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    return len(a & b) / len(a | b)


def run_experiment(hin, name, update_type, k=3, num_updates=500, num_queries=2):
    """Run a single experiment config on the hybrid graph."""
    import random
    random.seed(42)

    print(f'\n{"="*50}')
    print(f'[{name}] Hybrid graph, k={k}, s=10, {num_updates} {update_type}')
    print(f'{"="*50}')

    # Use authors from the first planted group as query nodes (guaranteed valid communities)
    # Authors connected to PLANTED papers will have valid communities
    planted_authors = set()
    for u, v in hin.edges:
        if u.startswith('PLANTED_P') and hin.node_types.get(v) == 'A':
            planted_authors.add(v)
        elif v.startswith('PLANTED_P') and hin.node_types.get(u) == 'A':
            planted_authors.add(u)
        if len(planted_authors) >= 50:  # Enough candidates
            break
    if not planted_authors:
        planted_authors = set(n for n, t in hin.node_types.items() if t == 'A')
    query_nodes = random.sample(list(planted_authors), min(num_queries, len(planted_authors)))

    results = {'dyn_times': [], 'static_times': [], 'jaccards': [], 'qratios': [],
               'repairs': 0, 'recomps': 0, 'queries_with_community': 0}

    for qi, qnode in enumerate(query_nodes):
        hin_q = build_hybrid_graph()
        hin_static = build_hybrid_graph()

        ups = generate_update_stream(
            hin_q, num_updates, update_type, 42 + qi,
            meta_path=('A', 'P', 'A')
        )

        up = DynaSCSHUpdater(hin_q, ('A', 'P', 'A'), k=k, size_bound=10, hop_limit=2)
        comm = up.initialize_community(qnode)
        if comm is None or len(comm) < 3:
            print(f'  Q{qi} {qnode}: no community, skipping')
            continue
        results['queries_with_community'] += 1

        sb = StaticRecomputeBaseline(
            hin_static, ('A', 'P', 'A'), k=k, size_bound=10,
            use_exact=False, query_node=qnode
        )
        checkpoint_interval = max(1, num_updates // 10)

        for ui, (edge, utype) in enumerate(ups):
            # DynaSCSH
            t0 = time.perf_counter()
            if utype == 'insertion':
                dyn_comm, dyn_status = up.handle_edge_insertion(*edge)
            else:
                dyn_comm, dyn_status = up.handle_edge_deletion(*edge)
            dyn_time = time.perf_counter() - t0

            if ui % checkpoint_interval == 0 or ui == len(ups) - 1:
                t0 = time.perf_counter()
                static_comm, _ = sb.handle_update(edge, utype, query_node=qnode)
                static_time = time.perf_counter() - t0

                jac = jaccard_similarity(set(dyn_comm or []), set(static_comm or []))
                qr = up.community_score / max(sb.community_score, 0.001)
                qr = min(qr, 10.0)  # Cap at 10x to avoid unreasonable outliers

                results['dyn_times'].append(dyn_time)
                results['static_times'].append(static_time)
                results['jaccards'].append(jac)
                results['qratios'].append(qr)
                print(f'    u={ui:4d}: dyn={dyn_time*1000:6.0f}ms static={static_time*1000:6.0f}ms '
                      f'jac={jac:.3f} qr={qr:.3f}', flush=True)

        stats = up.get_stats()
        results['repairs'] += stats['local_repairs']
        results['recomps'] += stats['full_recomputes']

    # Summary
    if results['dyn_times']:
        avg_dyn = sum(results['dyn_times']) / len(results['dyn_times'])
        avg_static = sum(results['static_times']) / len(results['static_times'])
        avg_jac = sum(results['jaccards']) / len(results['jaccards'])
        avg_qr = sum(results['qratios']) / len(results['qratios'])
        speedup = avg_static / max(avg_dyn, 1e-9)

        print(f'\n  RESULTS: speedup={speedup:.0f}x, jac={avg_jac:.3f}, qratio={avg_qr:.3f}')
        print(f'  repairs={results["repairs"]}, recomps={results["recomps"]}, '
              f'valid_queries={results["queries_with_community"]}')
        return results
    else:
        print(f'  No valid queries')
        return results


if __name__ == '__main__':
    print('Building hybrid graph (26K real DBLP + 40 planted communities)...')
    t0 = time.time()

    all_results = {}

    # Run key experiments
    for name, utype, k_val, n_updates in [
        ('HYB-A1', 'insertion', 2, 500),
        ('HYB-A2', 'deletion', 2, 500),
        ('HYB-D1', 'deletion', 3, 500),
        ('HYB-B1', 'insertion', 2, 500),
        ('HYB-B2', 'deletion', 2, 500),
    ]:
        r = run_experiment(build_hybrid_graph(), name, utype, k=k_val,
                          num_updates=n_updates, num_queries=2)
        all_results[name] = r

    total_time = time.time() - t0
    print(f'\n{"="*50}')
    print(f'All hybrid experiments complete in {total_time/60:.0f} min')
    print(f'{"="*50}')

    # Save summary
    summary = {}
    for name, r in all_results.items():
        if r.get('dyn_times'):
            avg_dyn = sum(r['dyn_times']) / len(r['dyn_times'])
            avg_static = sum(r['static_times']) / len(r['static_times'])
            avg_jac = sum(r['jaccards']) / len(r['jaccards'])
            avg_qr = sum(r['qratios']) / len(r['qratios'])
            speedup = avg_static / max(avg_dyn, 1e-9)
            summary[name] = {
                'speedup': speedup, 'jaccard': avg_jac, 'qratio': avg_qr,
                'dyn_ms': avg_dyn*1000, 'static_ms': avg_static*1000,
                'repairs': r['repairs'], 'recomps': r['recomps']
            }

    with open('results/hybrid_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    print('Saved to results/hybrid_summary.json')
