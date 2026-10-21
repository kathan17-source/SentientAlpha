"""Interpretable entity relevance; unresolved multi-entity sentiment is excluded."""

import re
from dataclasses import dataclass

from sentientalpha.data.contracts import ticker_symbol


@dataclass(frozen=True)
class Entity:
    ticker: str
    name: str
    sector: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class Relevance:
    ticker: str
    weight: float
    reason: str
    context: str | None
    status: str


def resolve(text: str, tags: tuple[str, ...], entities: list[Entity]) -> list[Relevance]:
    matched: dict[str, list[str]] = {}
    protected = re.sub(r"\b(Inc|Corp|Ltd|Co)\.", lambda m: m.group(0).replace(".", "\ue000"), text)
    sentences = [
        sentence.replace("\ue000", ".") for sentence in re.split(r"(?<=[.!?])\s+|\n+", protected)
    ]
    names: dict[str, list[str]] = {}
    for entity in entities:
        aliases = [
            a for a in (entity.name, *entity.aliases) if len(a) > 3 and a.upper() != entity.ticker
        ]
        financial = bool(
            re.search(
                r"\b(profit|loss|earnings|revenue|shares|stock|outperforms?|guidance|dividend|company)\b",
                text,
                re.I,
            )
        )
        aliases = [
            a
            for a in aliases
            if a.casefold() not in {"apple", "meta", "block", "target", "gap"}
            or entity.ticker in tags
            or financial
        ]
        patterns = [rf"(?<!\w){re.escape(a)}(?!\w)" for a in aliases]
        patterns.append(rf"\${re.escape(entity.ticker)}\b")
        names[entity.ticker] = patterns
        found = [s for s in sentences if any(re.search(p, s, re.I) for p in patterns)]
        if found:
            matched[entity.ticker] = found
    tagged = {ticker_symbol(t) for t in tags}
    candidates = sorted(tagged | set(matched))
    result = []
    for ticker in candidates:
        context = matched.get(ticker, [])
        unique = [
            s
            for s in context
            if not any(
                other != ticker and any(re.search(p, s, re.I) for p in patterns)
                for other, patterns in names.items()
            )
        ]
        if len(candidates) == 1:
            result.append(
                Relevance(
                    ticker,
                    1.0 if context else 0.8,
                    "company_alias" if context else "single_provider_tag",
                    text,
                    "resolved",
                )
            )
        elif unique:
            result.append(
                Relevance(ticker, 0.9, "isolated_company_sentence", " ".join(unique), "resolved")
            )
        else:
            result.append(
                Relevance(ticker, 0.0, "multi_entity_or_ambiguous_context", None, "unresolved")
            )
    return result
