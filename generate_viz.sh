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
