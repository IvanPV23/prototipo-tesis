from typing import Literal
ClockRelation = Literal["before", "after", "equal", "concurrent"]
def compare(left: dict[str, int], right: dict[str, int]) -> ClockRelation:
    keys = set(left) | set(right)
    le = all(left.get(k, 0) <= right.get(k, 0) for k in keys)
    ge = all(left.get(k, 0) >= right.get(k, 0) for k in keys)
    if le and ge: return "equal"
    if le: return "before"
    if ge: return "after"
    return "concurrent"
def merge(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    return {k: max(left.get(k, 0), right.get(k, 0)) for k in set(left) | set(right)}
