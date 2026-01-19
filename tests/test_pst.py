import unittest

try:
    from sese.pst import compute_pst
    from sese.visualize import cfg_to_dot, pst_to_dot
except ModuleNotFoundError:
    from pst import compute_pst
    from visualize import cfg_to_dot, pst_to_dot


def _make_adj(edges):
    nodes = set()
    for u, v in edges:
        nodes.add(u)
        nodes.add(v)

    adj = {n: {"out": [], "in": []} for n in sorted(nodes)}
    for u, v in edges:
        adj[u]["out"].append(v)
        adj[v]["in"].append(u)
    for n in adj:
        adj[n]["out"] = sorted(adj[n]["out"])
        adj[n]["in"] = sorted(adj[n]["in"])
    return adj


def _unique_label(base, existing):
    used = set(existing)
    if base not in used:
        return base
    i = 1
    while True:
        candidate = f"{base}_{i}"
        if candidate not in used:
            return candidate
        i += 1


def _augment_graph(adj):
    nodes = []
    seen = set()

    def add_node(n):
        if n not in seen:
            seen.add(n)
            nodes.append(n)

    edges = []
    for u, info in adj.items():
        add_node(u)
        for v in info.get("out", []):
            add_node(v)
            edges.append((u, v, "orig"))
        for v in info.get("in", []):
            add_node(v)

    indeg = {n: 0 for n in nodes}
    outdeg = {n: 0 for n in nodes}
    for u, v, _ in edges:
        outdeg[u] += 1
        indeg[v] += 1

    entry_nodes = [n for n in nodes if indeg[n] == 0]
    exit_nodes = [n for n in nodes if outdeg[n] == 0]
    if not entry_nodes:
        entry_nodes = nodes[:]
    if not exit_nodes:
        exit_nodes = nodes[:]

    super_entry = _unique_label("__super_entry__", seen)
    add_node(super_entry)
    super_exit = _unique_label("__super_exit__", seen)
    add_node(super_exit)

    for n in entry_nodes:
        edges.append((super_entry, n, "super_entry"))
    for n in exit_nodes:
        edges.append((n, super_exit, "super_exit"))

    edges.append((super_exit, super_entry, "back"))

    return nodes, edges, super_entry, super_exit


def _enumerate_cycles(nodes, edges):
    node_index = {n: i for i, n in enumerate(nodes)}
    undirected = [[] for _ in nodes]
    for edge_id, (u, v, _) in enumerate(edges):
        ui = node_index[u]
        vi = node_index[v]
        undirected[ui].append((edge_id, vi))
        undirected[vi].append((edge_id, ui))

    cycles = set()
    for start in range(len(nodes)):
        stack = [(start, -1, [start], [])]
        while stack:
            node, parent, path_nodes, path_edges = stack.pop()
            for edge_id, nb in undirected[node]:
                if nb == parent:
                    continue
                if nb == start:
                    if path_edges:
                        cycles.add(frozenset(path_edges + [edge_id]))
                    continue
                if nb in path_nodes:
                    continue
                if nb < start:
                    continue
                stack.append((nb, node, path_nodes + [nb], path_edges + [edge_id]))
    return list(cycles)


def _edge_cycle_sets(edge_count, cycles):
    edge_cycles = [set() for _ in range(edge_count)]
    for idx, cycle in enumerate(cycles):
        for edge_id in cycle:
            edge_cycles[edge_id].add(idx)
    return [frozenset(s) for s in edge_cycles]


def _dominators(total, start, preds):
    dom = [set(range(total)) for _ in range(total)]
    dom[start] = {start}
    changed = True
    while changed:
        changed = False
        for n in range(total):
            if n == start:
                continue
            if not preds[n]:
                new_dom = {n}
            else:
                inter = set(range(total))
                for p in preds[n]:
                    inter &= dom[p]
                new_dom = inter | {n}
            if new_dom != dom[n]:
                dom[n] = new_dom
                changed = True
    return dom


def _dominance_data(nodes, edges, super_entry, super_exit):
    node_index = {n: i for i, n in enumerate(nodes)}
    edge_node_index = {}
    edge_nodes = []
    for edge_id, (_, _, kind) in enumerate(edges):
        if kind == "back":
            continue
        edge_node_index[edge_id] = len(nodes) + len(edge_nodes)
        edge_nodes.append(edge_id)

    total = len(nodes) + len(edge_nodes)
    succs = [[] for _ in range(total)]
    preds = [[] for _ in range(total)]

    for edge_id in edge_nodes:
        u, v, _ = edges[edge_id]
        u_idx = node_index[u]
        v_idx = node_index[v]
        e_idx = edge_node_index[edge_id]
        succs[u_idx].append(e_idx)
        preds[e_idx].append(u_idx)
        succs[e_idx].append(v_idx)
        preds[v_idx].append(e_idx)

    dom = _dominators(total, node_index[super_entry], preds)
    postdom = _dominators(total, node_index[super_exit], succs)
    return dom, postdom, edge_node_index


def _canonical_pairs(adj):
    nodes, edges, super_entry, super_exit = _augment_graph(adj)
    cycles = _enumerate_cycles(nodes, edges)
    edge_cycles = _edge_cycle_sets(len(edges), cycles)
    dom, postdom, edge_node_index = _dominance_data(
        nodes, edges, super_entry, super_exit
    )

    sese = []
    for a in range(len(edges)):
        if edges[a][2] == "back":
            continue
        for b in range(len(edges)):
            if a == b or edges[b][2] == "back":
                continue
            if edge_cycles[a] != edge_cycles[b]:
                continue
            if edge_node_index[a] not in dom[edge_node_index[b]]:
                continue
            if edge_node_index[b] not in postdom[edge_node_index[a]]:
                continue
            sese.append((a, b))

    by_entry = {}
    by_exit = {}
    for a, b in sese:
        by_entry.setdefault(a, []).append(b)
        by_exit.setdefault(b, []).append(a)

    canonical = set()
    for a, bs in by_entry.items():
        for b in bs:
            if all(edge_node_index[b] in dom[edge_node_index[x]] for x in bs):
                canonical.add((a, b))

    filtered = set()
    for b, a_list in by_exit.items():
        for a in a_list:
            if all(
                edge_node_index[a] in postdom[edge_node_index[x]] for x in a_list
            ):
                if (a, b) in canonical:
                    filtered.add((a, b))

    def edge_tuple(edge_id):
        u, v, kind = edges[edge_id]
        return (u, v, kind)

    return {(edge_tuple(a), edge_tuple(b)) for a, b in filtered}


def _pst_pairs(result):
    pairs = set()
    for region in result.regions.values():
        if region.id == result.root:
            continue
        entry = result.edges[region.entry_edge]
        exit = result.edges[region.exit_edge]
        if entry.kind == "back" or exit.kind == "back":
            continue
        pairs.add(((entry.src, entry.dst, entry.kind), (exit.src, exit.dst, exit.kind)))
    return pairs


def _region_map(result):
    mapping = {}
    for region in result.regions.values():
        if region.id == result.root:
            continue
        entry = result.edges[region.entry_edge]
        exit = result.edges[region.exit_edge]
        key = ((entry.src, entry.dst, entry.kind), (exit.src, exit.dst, exit.kind))
        mapping[key] = region.id
    return mapping


def _paper_figure_adj():
    # Figure 1(a) adjacency list from the PST paper.
    edges = [
        ("start", "n1"),
        ("n1", "n2"),
        ("n1", "n3"),
        ("n2", "n4"),
        ("n3", "n5"),
        ("n4", "n6"),
        ("n5", "n7"),
        ("n5", "n8"),
        ("n6", "n9"),
        ("n6", "n10"),
        ("n7", "n11"),
        ("n8", "n11"),
        ("n9", "n12"),
        ("n10", "n12"),
        ("n11", "n13"),
        ("n12", "n14"),
        ("n13", "n8"),
        ("n13", "n15"),
        ("n14", "n2"),
        ("n14", "n16"),
        ("n15", "n16"),
        ("n16", "end"),
    ]
    return _make_adj(edges)


class PSTTests(unittest.TestCase):
    def _assert_matches_naive(self, edges):
        adj = _make_adj(edges)
        result = compute_pst(adj)
        expected = _canonical_pairs(adj)
        actual = _pst_pairs(result)
        self.assertEqual(expected, actual)

    def test_linear_chain(self):
        self._assert_matches_naive([("A", "B"), ("B", "C")])

    def test_diamond(self):
        edges = [
            ("S", "A"),
            ("A", "B"),
            ("A", "C"),
            ("B", "D"),
            ("C", "D"),
            ("D", "T"),
        ]
        self._assert_matches_naive(edges)

    def test_loop(self):
        edges = [("S", "A"), ("A", "B"), ("B", "C"), ("C", "B"), ("C", "T")]
        self._assert_matches_naive(edges)

    def test_dot_outputs(self):
        adj = _make_adj([("A", "B"), ("B", "C")])
        result = compute_pst(adj)
        cfg_dot = cfg_to_dot(result)
        pst_dot = pst_to_dot(result)
        self.assertIn("digraph CFG", cfg_dot)
        self.assertIn("digraph PST", pst_dot)
        self.assertIn(str(result.super_entry), cfg_dot)

    def test_diamond_tree_nesting(self):
        edges = [
            ("S", "A"),
            ("A", "B"),
            ("A", "C"),
            ("B", "D"),
            ("C", "D"),
            ("D", "T"),
        ]
        result = compute_pst(_make_adj(edges))
        mapping = _region_map(result)
        r3 = mapping[(("S", "A", "orig"), ("D", "T", "orig"))]
        r2 = mapping[(("A", "B", "orig"), ("B", "D", "orig"))]
        r5 = mapping[(("A", "C", "orig"), ("C", "D", "orig"))]
        self.assertEqual(result.regions[r2].parent, r3)
        self.assertEqual(result.regions[r5].parent, r3)

    def test_paper_figure_matches_naive(self):
        result = compute_pst(_paper_figure_adj())
        actual = _pst_pairs(result)
        expected = _canonical_pairs(_paper_figure_adj())
        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
