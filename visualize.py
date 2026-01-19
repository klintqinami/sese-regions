from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple

from .pst import PSTResult

_PRETTY_GRAPH_ATTRS = {
    "rankdir": "LR",
    "bgcolor": "transparent",
    "pad": "0.2",
    "nodesep": "0.35",
    "ranksep": "0.5",
    "splines": "true",
    "overlap": "false",
    "fontname": "Helvetica",
    "fontsize": "12",
}

_PRETTY_NODE_ATTRS = {
    "shape": "oval",
    "style": "filled",
    "color": "#455A64",
    "fillcolor": "white",
    "penwidth": "1.1",
    "fontname": "Helvetica",
    "fontsize": "11",
    "margin": "0.08,0.05",
}

_PRETTY_EDGE_ATTRS = {
    "color": "#546E7A",
    "fontcolor": "#455A64",
    "penwidth": "1.1",
    "arrowsize": "0.7",
    "fontname": "Helvetica",
    "fontsize": "9",
}

_REGION_PALETTE = [
    ("#E3F2FD", "#64B5F6"),
    ("#E8F5E9", "#81C784"),
    ("#FFF8E1", "#FFB74D"),
    ("#FBE9E7", "#FF8A65"),
    ("#E0F7FA", "#4DD0E1"),
    ("#ECEFF1", "#90A4AE"),
]
_REGION_LABEL_ALIGN = "LEFT"


def _dot_attrs(attrs: Dict[str, str]) -> str:
    return ", ".join(f'{key}="{value}"' for key, value in attrs.items())


def _region_colors(depth: int) -> Tuple[str, str]:
    fill, border = _REGION_PALETTE[depth % len(_REGION_PALETTE)]
    return fill, border


def _dot_escape_id(value: object) -> str:
    text = str(value)
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _dot_escape_label(value: object) -> str:
    text = str(value)
    return text.replace('"', '\\"')


def _html_escape(value: object) -> str:
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _display_node_label(node: object, result: PSTResult) -> str:
    if node == result.super_entry:
        return "Super entry"
    if node == result.super_exit:
        return "Super exit"
    return str(node)


def _edge_pair_label_html(src: object, dst: object, result: PSTResult) -> str:
    src_label = _html_escape(_display_node_label(src, result))
    dst_label = _html_escape(_display_node_label(dst, result))
    return f"{src_label} &#8594; {dst_label}"


def _region_label_table(lines: List[str], *, align: str = _REGION_LABEL_ALIGN) -> str:
    align = align.upper()
    rows = "".join(
        f'<TR><TD ALIGN="{align}">{line}</TD></TR>' for line in lines
    )
    return (
        f'<TABLE BORDER="0" CELLBORDER="0" CELLPADDING="0" ALIGN="{align}">'
        f"{rows}</TABLE>"
    )


def _edge_label(edge_id: int, class_id: int, kind: str) -> str:
    label = f"{edge_id}:{class_id}"
    if kind not in ("orig", "super_entry", "super_exit"):
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
        display_label = _display_node_label(node, result)
        if display_label != str(node):
            attrs.append(f'label="{_dot_escape_label(display_label)}"')
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
        src = _dot_escape_id(edge.src)
        dst = _dot_escape_id(edge.dst)
        if attrs:
            attrs_text = ", ".join(attrs)
            lines.append(f'  "{src}" -> "{dst}" [{attrs_text}];')
        else:
            lines.append(f'  "{src}" -> "{dst}";')

    lines.append("}")
    return "\n".join(lines) + "\n"


def pst_to_dot(result: PSTResult) -> str:
    lines = ["digraph PST {", "  node [shape=box];"]

    for region_id in sorted(result.regions):
        region = result.regions[region_id]
        if region_id == result.root:
            label = _region_label_table(["root"])
            lines.append(f'  "R{region_id}" [label=<{label}>];')
        else:
            entry = result.edges[region.entry_edge]
            exit = result.edges[region.exit_edge]
            entry_label = _edge_pair_label_html(entry.src, entry.dst, result)
            exit_label = _edge_pair_label_html(exit.src, exit.dst, result)
            label = _region_label_table(
                [f"<B>R{region_id}</B>", entry_label, exit_label]
            )
            lines.append(f'  "R{region_id}" [label=<{label}>];')

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
    show_edge_labels: bool = True,
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
            attrs.append('fillcolor="#ECEFF1"')
            attrs.append('color="#607D8B"')
            attrs.append('penwidth="1.4"')
        display_label = _display_node_label(node, result)
        if display_label != str(node):
            attrs.append(f'label="{_dot_escape_label(display_label)}"')
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
                label = _region_label_table(["root"])
                lines.append(f'{next_indent}label=<{label}>;')
            else:
                entry = result.edges[region.entry_edge]
                exit = result.edges[region.exit_edge]
                entry_label = _edge_pair_label_html(entry.src, entry.dst, result)
                exit_label = _edge_pair_label_html(exit.src, exit.dst, result)
                label = _region_label_table(
                    [f"<B>R{region_id}</B>", entry_label, exit_label]
                )
                lines.append(f'{next_indent}label=<{label}>;')
            lines.append(f'{next_indent}labelloc="t";')
            lines.append(f'{next_indent}labeljust="l";')
            fill, border = _region_colors(depth.get(region_id, 0))
            lines.append(f'{next_indent}style="rounded,filled";')
            lines.append(f'{next_indent}color="{border}";')
            lines.append(f'{next_indent}fillcolor="{fill}";')
            lines.append(f'{next_indent}fontcolor="#37474F";')
            lines.append(f'{next_indent}fontsize="11";')
            lines.append(f'{next_indent}fontname="Helvetica";')
            lines.append(f'{next_indent}penwidth="1.2";')
        else:
            next_indent = indent

        for child in region.children:
            emit_region(lines, child, next_indent)

        for node in sorted(assigned_nodes.get(region_id, []), key=lambda n: str(n)):
            emit_node(lines, node, next_indent)

        if region_id != result.root or include_root:
            lines.append(f"{indent}}}")

    lines = [
        "digraph CFG {",
        f"  graph [{_dot_attrs(_PRETTY_GRAPH_ATTRS)}];",
        f"  node [{_dot_attrs(_PRETTY_NODE_ATTRS)}];",
        f"  edge [{_dot_attrs(_PRETTY_EDGE_ATTRS)}];",
    ]

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
            if node in (result.super_entry, result.super_exit):
                emit_node(lines, node, "  ")
                emitted_nodes.add(node)
                continue
            emit_node(lines, node, "  ")
            emitted_nodes.add(node)

    for edge in result.edges.values():
        if edge.kind == "back" and not include_back:
            continue
        attrs: list[str] = []
        if edge.kind == "back":
            attrs.append('style="dotted"')
            attrs.append('color="#90A4AE"')
            attrs.append('fontcolor="#90A4AE"')
            attrs.append("constraint=false")
        elif edge.kind in ("super_entry", "super_exit"):
            attrs.append('style="dashed"')
            attrs.append('color="#78909C"')
            attrs.append('fontcolor="#78909C"')
        if show_edge_labels:
            label = _edge_label(edge.id, edge.class_id, edge.kind)
            attrs.append(f'label="{_dot_escape_label(label)}"')
        src = _dot_escape_id(edge.src)
        dst = _dot_escape_id(edge.dst)
        if attrs:
            attrs_text = ", ".join(attrs)
            lines.append(f'  "{src}" -> "{dst}" [{attrs_text}];')
        else:
            lines.append(f'  "{src}" -> "{dst}";')

    lines.append("}")
    return "\n".join(lines) + "\n"
