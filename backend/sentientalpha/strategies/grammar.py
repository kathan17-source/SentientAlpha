"""Canonical restricted rules and three-valued logic; never execute supplied code."""

from collections.abc import Callable
from typing import Any

from sentientalpha.backtesting.storage import digest
from sentientalpha.strategies.contracts import Definition, DiscoveryError, Rule


def canonical(rule: Rule) -> dict[str, Any]:
    if rule.kind == "compare":
        return {
            "kind": "compare",
            "feature": rule.feature,
            "operator": rule.operator,
            "threshold": rule.threshold,
            "other_feature": rule.other_feature,
        }
    children: list[dict[str, Any]] = []
    for child in rule.children:
        value = canonical(child)
        children.extend(value["children"] if value["kind"] == rule.kind else [value])
    unique = {digest(c): c for c in children}
    ordered = [unique[k] for k in sorted(unique)]
    if len(ordered) == 1:
        return ordered[0]
    if len(ordered) > 4:
        ordered = [*ordered[:3], {"kind": rule.kind, "children": ordered[3:]}]
    return {"kind": rule.kind, "children": ordered}


def normalized(strategy: Definition) -> dict[str, Any]:
    return {
        **strategy.model_dump(mode="json"),
        "entry": canonical(strategy.entry),
        "exit": canonical(strategy.exit) if strategy.exit else None,
    }


def identity(strategy: Definition) -> str:
    return digest(normalized(strategy))


def requirements(strategy: Definition) -> set[str]:
    return strategy.entry.features() | (strategy.exit.features() if strategy.exit else set())


def complexity(strategy: Definition) -> dict[str, float | int]:
    leaves = strategy.entry.leaves() + (strategy.exit.leaves() if strategy.exit else 0)
    features = len(requirements(strategy))
    depth = max(strategy.entry.depth(), strategy.exit.depth() if strategy.exit else 1)
    triggers = 1 + int(strategy.exit is not None) + int(strategy.holding_sessions is not None)
    # Fixed documented numeric scale, maximum8 leaves,16 references,depth3,3 triggers.
    score = (leaves / 8 + features / 16 + (depth - 1) / 2 + triggers / 3) / 4
    return {
        "conditions": leaves,
        "features": features,
        "depth": depth,
        "parameters": leaves + triggers + 1,
        "triggers": triggers,
        "normalized": score,
    }


def validate(strategy: Definition, available: set[str]) -> None:
    if requirements(strategy) - available:
        raise DiscoveryError("Strategy references an unavailable or unregistered input")


def compare(
    rule: Rule, resolve: Callable[[str], float | None]
) -> tuple[bool | None, dict[str, Any]]:
    if rule.kind == "compare":
        assert rule.feature is not None
        left = resolve(rule.feature)
        right = resolve(rule.other_feature) if rule.other_feature else rule.threshold
        if left is None or right is None:
            value = None
        else:
            value = bool(
                {
                    "lt": lambda: left < right,
                    "le": lambda: left <= right,
                    "gt": lambda: left > right,
                    "ge": lambda: left >= right,
                    "eq": lambda: left == right,
                }[str(rule.operator)]()
            )
        return value, {"rule": canonical(rule), "left": left, "right": right, "satisfied": value}
    parts = [compare(child, resolve) for child in rule.children]
    values = [v for v, _ in parts]
    if rule.kind == "all":
        value = False if False in values else None if None in values else True
    else:
        value = True if True in values else None if None in values else False
    return value, {"kind": rule.kind, "satisfied": value, "children": [d for _, d in parts]}


def describe(rule: Rule) -> str:
    if rule.kind == "compare":
        operator = {"lt": "<", "le": "<=", "gt": ">", "ge": ">=", "eq": "=="}[str(rule.operator)]
        return f"{rule.feature} {operator} {rule.other_feature or rule.threshold}"
    return (
        "("
        + (" AND " if rule.kind == "all" else " OR ").join(describe(c) for c in rule.children)
        + ")"
    )
