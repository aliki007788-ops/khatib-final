"""
Model pricing table for cost estimation/tracking.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ModelPrice:
    input_per_1k_usd: float
    output_per_1k_usd: float


MODEL_PRICING: dict[str, ModelPrice] = {
    "gpt-4o-mini": ModelPrice(input_per_1k_usd=0.00015, output_per_1k_usd=0.0006),
    "gpt-4o": ModelPrice(input_per_1k_usd=0.005, output_per_1k_usd=0.015),
    "whisper-1": ModelPrice(input_per_1k_usd=0.0, output_per_1k_usd=0.0),
    "llama-3.1-8b-instant": ModelPrice(input_per_1k_usd=0.00005, output_per_1k_usd=0.00008),
    "llama-3.1-70b-versatile": ModelPrice(input_per_1k_usd=0.00059, output_per_1k_usd=0.00079),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal | None:
    price = MODEL_PRICING.get(model)
    if price is None:
        return None
    cost = (
        (input_tokens / 1000) * price.input_per_1k_usd
        + (output_tokens / 1000) * price.output_per_1k_usd
    )
    return Decimal(str(round(cost, 8)))
