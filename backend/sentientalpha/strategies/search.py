"""Bounded seeded/random and exhaustively bounded small Cartesian rule grids."""

import random
from collections.abc import Iterator
from itertools import combinations, product
from typing import Any, Literal, cast

from sentientalpha.strategies.contracts import Definition, DiscoveryError, Request, Rule
from sentientalpha.strategies.grammar import identity, normalized


def generate(request: Request, fold: int = 0) -> tuple[list[Definition], dict[str, Any]]:
    atoms: list[Rule] = []
    for axis in request.space.axes:
        atoms.extend(
            Rule(feature=axis.feature, operator=axis.operator, threshold=t) for t in axis.thresholds
        )
        atoms.extend(
            Rule(feature=axis.feature, operator=axis.operator, other_feature=f)
            for f in axis.other_features
        )
    # Normalize input axes, so serialization order cannot make repeated atoms distinct.
    atoms = list({identity(Definition(entry=r)): r for r in atoms}.values())
    if len(atoms) > 120:
        raise DiscoveryError("Atomic rule space exceeds120 comparisons")
    rng = random.Random(request.seed + fold)
    strategies, seen = [], set()
    duplicates = attempts = 0
    iterator: Iterator[Definition]
    if request.algorithm == "grid":
        choices = []
        for size in range(1, request.space.maximum_conditions + 1):
            for subset in combinations(atoms, size):
                for join in request.space.joins if size > 1 else ["all"]:
                    choices.append(
                        subset[0]
                        if size == 1
                        else Rule(kind=cast(Literal["all", "any"], join), children=list(subset))
                    )
                    if (
                        len(choices) * len(request.space.holdings) * len(request.space.schedules)
                        > request.candidates
                    ):
                        raise DiscoveryError("Entire grid exceeds declared candidate budget")
        iterator = (
            Definition(entry=r, exposure=request.space.exposure, holding_sessions=h, rebalance=s)
            for r, h, s in product(choices, request.space.holdings, request.space.schedules)
        )
    else:

        def samples() -> Iterator[Definition]:
            for _ in range(request.candidates * 20):
                count = rng.randint(1, min(request.space.maximum_conditions, len(atoms)))
                chosen = rng.sample(atoms, count)
                rule = (
                    chosen[0]
                    if count == 1
                    else Rule(kind=rng.choice(request.space.joins), children=chosen)
                )
                exit_rule = (
                    rng.choice(atoms) if request.space.include_exit and rng.random() < 0.3 else None
                )
                yield Definition(
                    entry=rule,
                    exit=exit_rule,
                    exposure=request.space.exposure,
                    holding_sessions=rng.choice(request.space.holdings),
                    rebalance=rng.choice(request.space.schedules),
                )

        iterator = samples()
    for strategy in iterator:
        attempts += 1
        key = identity(strategy)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        strategies.append(Definition.model_validate(normalized(strategy)))
        if len(strategies) == request.candidates:
            break
    return strategies, {
        "attempts": attempts,
        "unique": len(strategies),
        "duplicates": duplicates,
        "duplicate_rate": duplicates / attempts if attempts else 0,
        "seed": request.seed + fold,
        "algorithm": request.algorithm,
        "exhausted": len(strategies) < request.candidates,
        "requested": request.candidates,
    }
