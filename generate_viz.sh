python3 - <<'PY'
from sese.pst import compute_pst
from sese.visualize import cfg_with_regions_to_dot


def build_adj(edges):
    nodes = []
    seen_nodes = set()
    seen_edges = set()
    out = {}
    inc = {}

    def add_node(node):
        if node not in seen_nodes:
            seen_nodes.add(node)
            nodes.append(node)

    for u, v in edges:
        if (u, v) in seen_edges:
            continue
        seen_edges.add((u, v))
        add_node(u)
        add_node(v)
        out.setdefault(u, []).append(v)
        inc.setdefault(v, []).append(u)

    for n in nodes:
        out.setdefault(n, [])
        inc.setdefault(n, [])

    return {n: {"out": out[n], "in": inc[n]} for n in nodes}


def write_cfg(prefix, adj, *, show_labels=True):
    result = compute_pst(adj)
    dot = cfg_with_regions_to_dot(result, show_edge_labels=show_labels)
    path = f"{prefix}.dot"
    open(path, "w").write(dot)
    edge_count = sum(len(info["out"]) for info in adj.values())
    print(
        f"{prefix}: nodes={len(adj)} edges={edge_count} "
        f"regions={len(result.regions)} wrote {path}"
    )


edges_small = [
    ("S", "A"),
    ("A", "B"),
    ("A", "C"),
    ("B", "D"),
    ("C", "D"),
    ("D", "T"),
]
adj_small = build_adj(edges_small)
write_cfg("cfg_regions", adj_small)


def make_large_edges(stages=16, branches=3):
    edges = []
    prev = "S"
    for i in range(stages):
        branch_nodes = [f"B{i}{chr(97 + j)}" for j in range(branches)]
        merge = f"M{i}"
        for b in branch_nodes:
            edges.append((prev, b))
            edges.append((b, merge))
        if branches >= 2:
            edges.append((branch_nodes[0], branch_nodes[1]))
        if branches >= 3:
            edges.append((branch_nodes[1], branch_nodes[2]))
        if i >= 2:
            edges.append((merge, f"M{i-2}"))
        if i >= 1 and i % 3 == 0:
            edges.append((merge, f"B{i-1}a"))
        prev = merge
    edges.append((prev, "T"))
    for i in range(0, stages - 3, 4):
        edges.append((f"M{i}", f"B{i+2}b"))
    return edges


adj_large = build_adj(make_large_edges(stages=16, branches=3))
write_cfg("cfg_regions_large", adj_large, show_labels=False)
PY
