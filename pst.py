from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Hashable, Iterable, List, Optional, Set

Node = Hashable
Adj = Dict[Node, Dict[str, Iterable[Node]]]


@dataclass
class EdgeInfo:
    id: int
    src: Node
    dst: Node
    kind: str
    class_id: int


@dataclass
class RegionInfo:
    id: int
    entry_edge: Optional[int]
    exit_edge: Optional[int]
    parent: Optional[int]
    children: List[int] = field(default_factory=list)


@dataclass
class PSTResult:
    root: int
    regions: Dict[int, RegionInfo]
    edges: Dict[int, EdgeInfo]
    super_entry: Node
    super_exit: Node


class _Edge:
    __slots__ = (
        "id",
        "u",
        "v",
        "kind",
        "class_id",
        "recent_size",
        "recent_class",
        "list_node",
    )

    def __init__(self, edge_id: int, u: int, v: int, kind: str) -> None:
        self.id = edge_id
        self.u = u
        self.v = v
        self.kind = kind
        self.class_id: Optional[int] = None
        self.recent_size: Optional[int] = None
        self.recent_class: Optional[int] = None
        self.list_node: Optional[_BracketNode] = None


class _BracketNode:
    __slots__ = ("edge", "prev", "next")

    def __init__(self, edge: _Edge) -> None:
        self.edge = edge
        self.prev: Optional[_BracketNode] = None
        self.next: Optional[_BracketNode] = None


class _BracketList:
    __slots__ = ("head", "tail", "size")

    def __init__(self) -> None:
        self.head: Optional[_BracketNode] = None
        self.tail: Optional[_BracketNode] = None
        self.size = 0

    def push(self, edge: _Edge) -> None:
        node = _BracketNode(edge)
        edge.list_node = node
        if self.tail is None:
            self.head = node
            self.tail = node
        else:
            node.prev = self.tail
            self.tail.next = node
            self.tail = node
        self.size += 1

    def delete(self, edge: _Edge) -> None:
        node = edge.list_node
        if node is None:
            return
        if node.prev is None:
            self.head = node.next
        else:
            node.prev.next = node.next
        if node.next is None:
            self.tail = node.prev
        else:
            node.next.prev = node.prev
        edge.list_node = None
        node.prev = None
        node.next = None
        self.size -= 1

    def top(self) -> Optional[_Edge]:
        return self.tail.edge if self.tail is not None else None


def _concat_blist(left: _BracketList, right: _BracketList) -> _BracketList:
    if left.size == 0:
        return right
    if right.size == 0:
        return left
    left.tail.next = right.head
    right.head.prev = left.tail
    left.tail = right.tail
    left.size += right.size
    return left


def _unique_label(base: str, existing: Iterable[Node]) -> str:
    used = set(existing)
    if base not in used:
        return base
    i = 1
    while True:
        candidate = f"{base}_{i}"
        if candidate not in used:
            return candidate
        i += 1


def _dfs_edge_order(
    directed_adj: List[List[int]],
    edges: List[_Edge],
    root: int,
) -> List[int]:
    visited = [False] * len(directed_adj)
    order: List[int] = []

    def walk(start: int) -> None:
        stack = [(start, iter(directed_adj[start]))]
        visited[start] = True
        while stack:
            node, it = stack[-1]
            try:
                edge_id = next(it)
            except StopIteration:
                stack.pop()
                continue
            order.append(edge_id)
            nxt = edges[edge_id].v
            if not visited[nxt]:
                visited[nxt] = True
                stack.append((nxt, iter(directed_adj[nxt])))

    walk(root)
    for n in range(len(directed_adj)):
        if not visited[n]:
            walk(n)

    return order


def _cycle_equivalence(
    node_count: int,
    edges: List[_Edge],
    undirected_adj: List[List[tuple[int, int]]],
    root: int,
) -> None:
    edge_count = len(edges)
    dfsnum = [0] * node_count
    parent = [-1] * node_count
    parent_edge = [-1] * node_count
    children: List[List[int]] = [[] for _ in range(node_count)]
    backedges_from: List[List[int]] = [[] for _ in range(node_count)]
    backedges_to: List[List[int]] = [[] for _ in range(node_count)]
    edge_upper = [-1] * edge_count
    edge_seen = [False] * edge_count
    postorder: List[int] = []

    time = 0

    def dfs(start: int) -> None:
        nonlocal time
        stack = [(start, iter(undirected_adj[start]))]
        time += 1
        dfsnum[start] = time
        while stack:
            node, it = stack[-1]
            try:
                edge_id, other = next(it)
            except StopIteration:
                postorder.append(node)
                stack.pop()
                continue
            if edge_seen[edge_id]:
                continue
            edge_seen[edge_id] = True
            if dfsnum[other] == 0:
                parent[other] = node
                parent_edge[other] = edge_id
                children[node].append(other)
                time += 1
                dfsnum[other] = time
                stack.append((other, iter(undirected_adj[other])))
            else:
                if dfsnum[other] < dfsnum[node]:
                    desc, anc = node, other
                else:
                    desc, anc = other, node
                backedges_from[desc].append(edge_id)
                backedges_to[anc].append(edge_id)
                edge_upper[edge_id] = anc

    dfs(root)
    for n in range(node_count):
        if dfsnum[n] == 0:
            dfs(n)

    node_by_dfsnum = [0] * (node_count + 1)
    for n in range(node_count):
        node_by_dfsnum[dfsnum[n]] = n

    capping_to: List[List[_Edge]] = [[] for _ in range(node_count)]
    blists: List[_BracketList] = [_BracketList() for _ in range(node_count)]
    hi = [node_count + 1] * node_count

    class_counter = 0

    def new_class() -> int:
        nonlocal class_counter
        class_counter += 1
        return class_counter

    for n in postorder:
        hi0 = node_count + 1
        for e_id in backedges_from[n]:
            anc = edge_upper[e_id]
            if anc != -1:
                anc_dfs = dfsnum[anc]
                if anc_dfs < hi0:
                    hi0 = anc_dfs

        hi1 = node_count + 1
        hi2 = node_count + 1
        for c in children[n]:
            val = hi[c]
            if val < hi1:
                hi2 = hi1
                hi1 = val
            elif val < hi2:
                hi2 = val

        hi[n] = hi0 if hi0 < hi1 else hi1

        bl = _BracketList()
        for c in children[n]:
            bl = _concat_blist(blists[c], bl)

        for cap in capping_to[n]:
            bl.delete(cap)

        for b_id in backedges_to[n]:
            b = edges[b_id]
            bl.delete(b)
            if b.class_id is None:
                b.class_id = new_class()

        for e_id in backedges_from[n]:
            bl.push(edges[e_id])

        if hi2 < hi0:
            upper = node_by_dfsnum[hi2]
            cap = _Edge(edge_count, n, upper, "capping")
            edge_count += 1
            bl.push(cap)
            capping_to[upper].append(cap)

        if parent[n] != -1:
            tree_edge = edges[parent_edge[n]]
            top = bl.top()
            if top is None:
                raise ValueError("empty bracket list; graph may not be strongly connected")
            if top.recent_size != bl.size:
                top.recent_size = bl.size
                top.recent_class = new_class()
            tree_edge.class_id = top.recent_class
            if top.recent_size == 1 and top.kind != "capping":
                top.class_id = tree_edge.class_id

        blists[n] = bl


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


def _edge_split_dominators(
    node_count: int,
    edges: List[_Edge],
    super_entry_idx: int,
    super_exit_idx: int,
) -> tuple[Dict[int, int], List[Set[int]], List[Set[int]]]:
    edge_node_index: Dict[int, int] = {}
    for edge in edges:
        if edge.kind in ("back", "capping"):
            continue
        edge_node_index[edge.id] = node_count + len(edge_node_index)

    total = node_count + len(edge_node_index)
    preds: List[List[int]] = [[] for _ in range(total)]
    succs: List[List[int]] = [[] for _ in range(total)]

    for edge in edges:
        if edge.kind in ("back", "capping"):
            continue
        e_idx = edge_node_index[edge.id]
        succs[edge.u].append(e_idx)
        preds[e_idx].append(edge.u)
        succs[e_idx].append(edge.v)
        preds[edge.v].append(e_idx)

    dom = _dominators(total, super_entry_idx, preds)
    postdom = _dominators(total, super_exit_idx, succs)
    return edge_node_index, dom, postdom


def compute_pst(adj: Adj, *, strict: bool = True) -> PSTResult:
    """
    Build the Program Structure Tree (PST) for a directed graph using the
    linear-time cycle-equivalence algorithm from Johnson-Pearson-Pingali.

    The input graph may have multiple entries/exits; super-entry and
    super-exit nodes are added automatically.
    """
    nodes_order: List[Node] = []
    node_seen: set[Node] = set()

    def add_node(n: Node) -> None:
        if n not in node_seen:
            node_seen.add(n)
            nodes_order.append(n)

    edges_spec: List[tuple[Node, Node, str]] = []

    for u, info in adj.items():
        add_node(u)
        for v in info.get("out", []):
            add_node(v)
            edges_spec.append((u, v, "orig"))
        for v in info.get("in", []):
            add_node(v)

    indeg = {n: 0 for n in node_seen}
    outdeg = {n: 0 for n in node_seen}
    for u, v, _ in edges_spec:
        outdeg[u] += 1
        indeg[v] += 1

    entry_nodes = [n for n in nodes_order if indeg[n] == 0]
    exit_nodes = [n for n in nodes_order if outdeg[n] == 0]
    if not entry_nodes:
        entry_nodes = nodes_order[:]
    if not exit_nodes:
        exit_nodes = nodes_order[:]

    super_entry = _unique_label("__super_entry__", node_seen)
    add_node(super_entry)
    super_exit = _unique_label("__super_exit__", node_seen)
    add_node(super_exit)

    for n in entry_nodes:
        edges_spec.append((super_entry, n, "super_entry"))
    for n in exit_nodes:
        edges_spec.append((n, super_exit, "super_exit"))

    edges_spec.append((super_exit, super_entry, "back"))

    node_index = {n: i for i, n in enumerate(nodes_order)}
    edges: List[_Edge] = []
    directed_adj: List[List[int]] = [[] for _ in range(len(nodes_order))]

    for u, v, kind in edges_spec:
        edge_id = len(edges)
        edge = _Edge(edge_id, node_index[u], node_index[v], kind)
        edges.append(edge)
        if kind != "back":
            directed_adj[edge.u].append(edge_id)

    undirected_adj: List[List[tuple[int, int]]] = [[] for _ in range(len(nodes_order))]
    for edge in edges:
        undirected_adj[edge.u].append((edge.id, edge.v))
        undirected_adj[edge.v].append((edge.id, edge.u))

    root = node_index[super_entry]
    _cycle_equivalence(len(nodes_order), edges, undirected_adj, root)

    edge_order = _dfs_edge_order(directed_adj, edges, root)

    regions: Dict[int, RegionInfo] = {}
    entry_map: Dict[int, int] = {}
    exit_map: Dict[int, int] = {}
    last_edge_by_class: Dict[int, int] = {}

    for edge_id in edge_order:
        cls = edges[edge_id].class_id
        if cls is None:
            continue
        prev = last_edge_by_class.get(cls)
        if prev is not None:
            region_id = len(regions) + 1
            region = RegionInfo(
                id=region_id,
                entry_edge=prev,
                exit_edge=edge_id,
                parent=None,
            )
            regions[region_id] = region
            entry_map[prev] = region_id
            exit_map[edge_id] = region_id
        last_edge_by_class[cls] = edge_id

    root_region = RegionInfo(id=0, entry_edge=None, exit_edge=None, parent=None)
    regions[0] = root_region

    edge_node_index, dom, postdom = _edge_split_dominators(
        len(nodes_order),
        edges,
        node_index[super_entry],
        node_index[super_exit],
    )

    for region in regions.values():
        region.children = []

    def contains(parent_id: int, child_id: int) -> bool:
        if parent_id == 0:
            return True
        parent = regions[parent_id]
        child = regions[child_id]
        if parent.entry_edge is None or parent.exit_edge is None:
            return False
        if child.entry_edge is None or child.exit_edge is None:
            return False
        p_entry = edge_node_index.get(parent.entry_edge)
        p_exit = edge_node_index.get(parent.exit_edge)
        c_entry = edge_node_index.get(child.entry_edge)
        c_exit = edge_node_index.get(child.exit_edge)
        if p_entry is None or p_exit is None or c_entry is None or c_exit is None:
            return False
        return p_entry in dom[c_entry] and p_exit in postdom[c_exit]

    for region_id in list(regions.keys()):
        if region_id == 0:
            continue
        parent_id = 0
        for candidate_id in regions:
            if candidate_id in (0, region_id):
                continue
            if contains(candidate_id, region_id):
                if parent_id == 0 or contains(parent_id, candidate_id):
                    parent_id = candidate_id
        regions[region_id].parent = parent_id
        regions[parent_id].children.append(region_id)

    edges_out: Dict[int, EdgeInfo] = {}
    for edge in edges:
        if edge.kind == "capping":
            continue
        edges_out[edge.id] = EdgeInfo(
            id=edge.id,
            src=nodes_order[edge.u],
            dst=nodes_order[edge.v],
            kind=edge.kind,
            class_id=edge.class_id if edge.class_id is not None else -1,
        )

    return PSTResult(
        root=0,
        regions=regions,
        edges=edges_out,
        super_entry=super_entry,
        super_exit=super_exit,
    )


if __name__ == "__main__":
    sample = {
        "A": {"out": ["B"], "in": []},
        "B": {"out": ["C"], "in": ["A"]},
        "C": {"out": [], "in": ["B"]},
    }
    result = compute_pst(sample)
    print("regions:", len(result.regions))
    print("root children:", result.regions[result.root].children)
