"""Token accounting and cost estimation.

RegForge reports what every extraction cost, because the whole business model
rests on one number: marginal cost per part approaching zero as the corpus
grows. If that number is invisible it will drift, so it gets printed on every
run and stored in each record's provenance.
"""

from __future__ import annotations

from dataclasses import dataclass

# USD per million tokens, Anthropic first-party API rates.
# Cache multipliers are the standard published ones: reads bill at 0.1x the
# base input rate, 5-minute writes at 1.25x.
_CACHE_READ_MULT = 0.10
_CACHE_WRITE_MULT = 1.25


@dataclass(frozen=True)
class ModelPricing:
    model_id: str
    input_per_mtok: float
    output_per_mtok: float


PRICING: dict[str, ModelPricing] = {
    "claude-haiku-4-5": ModelPricing("claude-haiku-4-5", 1.00, 5.00),
    "claude-sonnet-5": ModelPricing("claude-sonnet-5", 2.00, 10.00),
    "claude-opus-5": ModelPricing("claude-opus-5", 5.00, 25.00),
}

# What RegForge uses by default, and why.
#   locate  - cheap triage over candidate pages; Haiku is plenty.
#   extract - the accuracy-critical pass that reads register tables.
DEFAULT_LOCATE_MODEL = "claude-haiku-4-5"
DEFAULT_EXTRACT_MODEL = "claude-sonnet-5"


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
        )

    @classmethod
    def from_response(cls, usage) -> "Usage":
        """Build from an SDK response's `usage` object, tolerating absent fields."""
        return cls(
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        )


def cost_usd(usage: Usage, model: str) -> float:
    """Dollar cost of one model's usage. Unknown models cost 0 rather than crash."""
    pricing = PRICING.get(model)
    if pricing is None:
        return 0.0
    m = 1_000_000
    return (
        usage.input_tokens / m * pricing.input_per_mtok
        + usage.output_tokens / m * pricing.output_per_mtok
        + usage.cache_read_tokens / m * pricing.input_per_mtok * _CACHE_READ_MULT
        + usage.cache_write_tokens / m * pricing.input_per_mtok * _CACHE_WRITE_MULT
    )


@dataclass
class CostLedger:
    """Accumulates usage across the several calls one extraction makes."""

    entries: list[tuple[str, str, Usage]] = None  # (stage, model, usage)

    def __post_init__(self) -> None:
        if self.entries is None:
            self.entries = []

    def add(self, stage: str, model: str, usage: Usage) -> None:
        self.entries.append((stage, model, usage))

    @property
    def total(self) -> Usage:
        acc = Usage()
        for _, _, u in self.entries:
            acc = acc + u
        return acc

    @property
    def total_usd(self) -> float:
        return sum(cost_usd(u, model) for _, model, u in self.entries)

    def report(self) -> str:
        if not self.entries:
            return "no model calls"
        lines = []
        for stage, model, u in self.entries:
            lines.append(
                f"  {stage:<10} {model:<18} "
                f"in={u.input_tokens:>7,} out={u.output_tokens:>6,} "
                f"cached={u.cache_read_tokens:>7,}  ${cost_usd(u, model):.4f}"
            )
        lines.append(f"  {'TOTAL':<10} {'':<18} {'':>27}  ${self.total_usd:.4f}")
        return "\n".join(lines)


__all__ = [
    "PRICING",
    "DEFAULT_LOCATE_MODEL",
    "DEFAULT_EXTRACT_MODEL",
    "ModelPricing",
    "Usage",
    "CostLedger",
    "cost_usd",
]
