# Program Structure Tree (PST)

Python implementation of the Johnson-Pearson-Pingali algorithm for
computing canonical single-entry/single-exit (SESE) regions and building
the Program Structure Tree (PST) for directed graphs. The implementation
adds a super-entry and super-exit when the input has multiple entries or
exits, and provides Graphviz DOT exporters for visualization.

![CFG regions](cfg_regions.png)

## What is included

- `sese/pst.py` core PST construction (`compute_pst`) using cycle equivalence
  in linear time.
- `sese/visualize.py` DOT exporters for the CFG, PST, and CFG-with-regions.
- `sese/tests/` unit tests with a brute-force oracle on small graphs.

## Quick start

```bash
python3 - <<'PY'
from sese.pst import compute_pst
from sese.visualize import cfg_with_regions_to_dot

adj = {
    "S": {"out": ["A"], "in": []},
    "A": {"out": ["B", "C"], "in": ["S"]},
    "B": {"out": ["D"], "in": ["A"]},
    "C": {"out": ["D"], "in": ["A"]},
    "D": {"out": ["T"], "in": ["B", "C"]},
    "T": {"out": [], "in": ["D"]},
}

result = compute_pst(adj)
open("cfg_regions.dot", "w").write(cfg_with_regions_to_dot(result))
print("wrote cfg_regions.dot")
PY
```

Render the DOT file if you have Graphviz installed:

```bash
dot -Tpng cfg_regions.dot -o cfg_regions.png
```

Run tests:

```bash
python3 -m unittest discover -s sese/tests
```
