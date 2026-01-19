from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple

from .pst import PSTResult


def _dot_escape_id(value: object) -> str:
    text = str(value)
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _dot_escape_label(value: object) -> str:
    text = str(value)
    return text.replace('"', '\\"')


def _edge_label(edge_id: int, class_id: int, kind: str) -> str:
    label = f"{edge_id}:{class_id}"
    if kind != "orig":
        label = f"{label}\\n{kind}"
    return label


def cfg_to_dot(result: PSTResult, *, include_back: bool = False) -> str:
    nodes: set[object] = set()
    for edge in result.edges.values():
        if edge.kind == "back" and not include_back:
            continue
        nodes.add(edge.src)
        nodes.add(edge.dst)

    lines = ["digraph CFG {", "  rankdir=LR;"]
    for node in sorted(nodes, key=lambda n: str(n)):
        attrs: list[str] = []
        if node == result.super_entry or node == result.super_exit:
            attrs.append("shape=doublecircle")
        label = _dot_escape_id(node)
        if attrs:
            lines.append(f'  "{label}" [{", ".join(attrs)}];')
        else:
            lines.append(f'  "{label}";')

    for edge in result.edges.values():
        if edge.kind == "back" and not include_back:
            continue
        attrs: list[str] = []
        if edge.kind == "back":
            attrs.append("style=dotted")
        elif edge.kind in ("super_entry", "super_exit"):
            attrs.append("style=dashed")
        label = _edge_label(edge.id, edge.class_id, edge.kind)
        attrs.append(f'label="{_dot_escape_label(label)}"')
        attrs_text = ", ".join(attrs)
        src = _dot_escape_id(edge.src)
        dst = _dot_escape_id(edge.dst)
        lines.append(f'  "{src}" -> "{dst}" [{attrs_text}];')

    lines.append("}")
    return "\n".join(lines) + "\n"


def pst_to_dot(result: PSTResult) -> str:
    lines = ["digraph PST {", "  node [shape=box];"]

    for region_id in sorted(result.regions):
        region = result.regions[region_id]
        if region_id == result.root:
            label = "root"
        else:
            entry = result.edges[region.entry_edge]
            exit = result.edges[region.exit_edge]
            entry_label = f"{entry.src}->{entry.dst}"
            exit_label = f"{exit.src}->{exit.dst}"
            label = f"R{region_id}\\n{entry_label}\\n{exit_label}"
        lines.append(f'  "R{region_id}" [label="{_dot_escape_label(label)}"];')

    for region_id in sorted(result.regions):
        region = result.regions[region_id]
        for child in region.children:
            lines.append(f'  "R{region_id}" -> "R{child}";')

    lines.append("}")
    return "\n".join(lines) + "\n"


def _dominators(total: int, start: int, preds: List[List[int]]) -> List[Set[int]]:
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


def _edge_split_graph(
    result: PSTResult,
) -> Tuple[List[object], Dict[object, int], Dict[int, int], List[Set[int]], List[Set[int]]]:
    edges = [edge for _, edge in sorted(result.edges.items()) if edge.kind != "back"]
    nodes: List[object] = []
    node_index: Dict[object, int] = {}

    def add_node(n: object) -> None:
        if n not in node_index:
            node_index[n] = len(nodes)
            nodes.append(n)

    for edge in edges:
        add_node(edge.src)
        add_node(edge.dst)

    edge_node_index: Dict[int, int] = {}
    for edge in edges:
        edge_node_index[edge.id] = len(nodes) + len(edge_node_index)

    total = len(nodes) + len(edge_node_index)
    preds: List[List[int]] = [[] for _ in range(total)]
    succs: List[List[int]] = [[] for _ in range(total)]

    for edge in edges:
        u_idx = node_index[edge.src]
        v_idx = node_index[edge.dst]
        e_idx = edge_node_index[edge.id]
        succs[u_idx].append(e_idx)
        preds[e_idx].append(u_idx)
        succs[e_idx].append(v_idx)
        preds[v_idx].append(e_idx)

    start = node_index[result.super_entry]
    end = node_index[result.super_exit]
    dom = _dominators(total, start, preds)
    postdom = _dominators(total, end, succs)

    return nodes, node_index, edge_node_index, dom, postdom


def _region_node_sets(
    result: PSTResult, *, include_super: bool
) -> Dict[int, Set[object]]:
    nodes, node_index, edge_node_index, dom, postdom = _edge_split_graph(result)
    region_nodes: Dict[int, Set[object]] = {region_id: set() for region_id in result.regions}

    for region_id, region in result.regions.items():
        if region_id == result.root:
            continue
        if region.entry_edge is None or region.exit_edge is None:
            continue
        entry_idx = edge_node_index.get(region.entry_edge)
        exit_idx = edge_node_index.get(region.exit_edge)
        if entry_idx is None or exit_idx is None:
            continue
        for node in nodes:
            if not include_super and node in (result.super_entry, result.super_exit):
                continue
            idx = node_index[node]
            if entry_idx in dom[idx] and exit_idx in postdom[idx]:
                region_nodes[region_id].add(node)

    return region_nodes


def cfg_with_regions_to_dot(
    result: PSTResult,
    *,
    include_super: bool = False,
    include_root: bool = False,
    include_back: bool = False,
) -> str:
    region_nodes = _region_node_sets(result, include_super=include_super)

    depth: Dict[int, int] = {result.root: 0}
    stack = [result.root]
    while stack:
        region_id = stack.pop()
        for child in result.regions[region_id].children:
            depth[child] = depth[region_id] + 1
            stack.append(child)

    assigned: Dict[object, int] = {}
    regions_by_depth = sorted(
        [rid for rid in result.regions if rid != result.root],
        key=lambda rid: depth.get(rid, 0),
        reverse=True,
    )
    for region_id in regions_by_depth:
        for node in region_nodes.get(region_id, set()):
            if node not in assigned:
                assigned[node] = region_id

    assigned_nodes: Dict[int, List[object]] = {rid: [] for rid in result.regions}
    for node, region_id in assigned.items():
        assigned_nodes[region_id].append(node)

    def emit_node(lines: List[str], node: object, indent: str) -> None:
        attrs: list[str] = []
        if node == result.super_entry or node == result.super_exit:
            attrs.append("shape=doublecircle")
        label = _dot_escape_id(node)
        if attrs:
            lines.append(f'{indent}"{label}" [{", ".join(attrs)}];')
        else:
            lines.append(f'{indent}"{label}";')

    def emit_region(lines: List[str], region_id: int, indent: str) -> None:
        region = result.regions[region_id]
        if region_id != result.root or include_root:
            lines.append(f"{indent}subgraph cluster_R{region_id} {{")
            next_indent = f"{indent}  "
            if region_id == result.root:
                label = "root"
            else:
                entry = result.edges[region.entry_edge]
                exit = result.edges[region.exit_edge]
                label = f"R{region_id}\\n{entry.src}->{entry.dst}\\n{exit.src}->{exit.dst}"
            lines.append(f'{next_indent}label="{_dot_escape_label(label)}";')
            lines.append(f"{next_indent}style=rounded;")
        else:
            next_indent = indent

        for child in region.children:
            emit_region(lines, child, next_indent)

        for node in sorted(assigned_nodes.get(region_id, []), key=lambda n: str(n)):
            emit_node(lines, node, next_indent)

        if region_id != result.root or include_root:
            lines.append(f"{indent}}}")

    lines = ["digraph CFG {", "  rankdir=LR;"]

    if include_root:
        emit_region(lines, result.root, "  ")
    else:
        for child in result.regions[result.root].children:
            emit_region(lines, child, "  ")

    emitted_nodes = set(assigned.keys())
    for edge in result.edges.values():
        if edge.kind == "back" and not include_back:
            continue
        for node in (edge.src, edge.dst):
            if node in emitted_nodes:
                continue
            if not include_super and node in (result.super_entry, result.super_exit):
                continue
            emit_node(lines, node, "  ")
            emitted_nodes.add(node)

    for edge in result.edges.values():
        if edge.kind == "back" and not include_back:
            continue
        attrs: list[str] = []
        if edge.kind == "back":
            attrs.append("style=dotted")
        elif edge.kind in ("super_entry", "super_exit"):
            attrs.append("style=dashed")
        label = _edge_label(edge.id, edge.class_id, edge.kind)
        attrs.append(f'label="{_dot_escape_label(label)}"')
        attrs_text = ", ".join(attrs)
        src = _dot_escape_id(edge.src)
        dst = _dot_escape_id(edge.dst)
        lines.append(f'  "{src}" -> "{dst}" [{attrs_text}];')

    lines.append("}")
    return "\n".join(lines) + "\n"
