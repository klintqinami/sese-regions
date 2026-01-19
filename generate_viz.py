#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys


def _load_modules():
    script_dir = Path(__file__).resolve().parent
    parent_dir = script_dir.parent
    for path in (script_dir, parent_dir):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
    try:
        from sese.pst import compute_pst
        from sese.visualize import cfg_with_regions_to_dot
    except ModuleNotFoundError:
        from pst import compute_pst
        from visualize import cfg_with_regions_to_dot
    return compute_pst, cfg_with_regions_to_dot


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


def write_cfg(
    compute_pst,
    cfg_with_regions_to_dot,
    prefix,
    adj,
    out_dir,
    *,
    show_labels=True,
):
    result = compute_pst(adj)
    dot = cfg_with_regions_to_dot(
        result,
        include_super=True,
        show_edge_labels=show_labels,
    )
    path = out_dir / f"{prefix}.dot"
    path.write_text(dot)
    edge_count = sum(len(info["out"]) for info in adj.values())
    print(
        f"{prefix}: nodes={len(adj)} edges={edge_count} "
        f"regions={len(result.regions)} wrote {path}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate SESE region DOT/SVG visualizations."
    )
    parser.add_argument(
        "out_dir",
        nargs="?",
        default=str(Path(__file__).resolve().parent / "images"),
        help="Output directory (default: images/).",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    compute_pst, cfg_with_regions_to_dot = _load_modules()

    names = []

    edges_small = [
        ("S", "A"),
        ("A", "B"),
        ("A", "C"),
        ("B", "D"),
        ("C", "D"),
        ("D", "T"),
    ]
    adj_small = build_adj(edges_small)
    write_cfg(
        compute_pst,
        cfg_with_regions_to_dot,
        "cfg_regions",
        adj_small,
        out_dir,
    )
    names.append("cfg_regions")

    edges_paper = [
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
    adj_paper = build_adj(edges_paper)
    write_cfg(
        compute_pst,
        cfg_with_regions_to_dot,
        "cfg_regions_paper",
        adj_paper,
        out_dir,
        show_labels=False,
    )
    names.append("cfg_regions_paper")

    dot = shutil.which("dot")
    if dot:
        for name in names:
            dot_path = out_dir / f"{name}.dot"
            svg_path = out_dir / f"{name}.svg"
            subprocess.run(
                [dot, "-Tsvg", str(dot_path), "-o", str(svg_path)],
                check=True,
            )
            try:
                dot_path.unlink()
            except FileNotFoundError:
                pass
        print(f"SVGs written to {out_dir}")
    else:
        print("Graphviz 'dot' not found; install with: brew install graphviz")
        print(f"DOT files are in {out_dir}")


if __name__ == "__main__":
    main()
