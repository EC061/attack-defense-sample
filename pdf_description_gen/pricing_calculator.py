#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Custom pricing calculator for OpenAI API costs with service tier support.
"""

from typing import Optional, Dict
from dataclasses import dataclass


@dataclass
class PricingTier:
    """Pricing information for a specific service tier."""

    input_per_1m: float  # Price per 1M input tokens
    cached_input_per_1m: float  # Price per 1M cached input tokens
    output_per_1m: float  # Price per 1M output tokens


# Pricing definitions for different models and service tiers
# Prices are in USD per 1M tokens
PRICING_TABLE: Dict[str, Dict[str, PricingTier]] = {
    "gpt-5": {
        "default": PricingTier(
            input_per_1m=1.25, cached_input_per_1m=0.125, output_per_1m=10.00
        ),
        "flex": PricingTier(
            input_per_1m=0.625, cached_input_per_1m=0.0625, output_per_1m=5.00
        ),
    },
    "gpt-5.1": {
        "default": PricingTier(
            input_per_1m=1.25, cached_input_per_1m=0.125, output_per_1m=10.00
        ),
        "flex": PricingTier(
            input_per_1m=0.625, cached_input_per_1m=0.0625, output_per_1m=5.00
        ),
    },
    # Add fallback for other model names
    "default": {
        "default": PricingTier(
            input_per_1m=1.25, cached_input_per_1m=0.125, output_per_1m=10.00
        ),
        "flex": PricingTier(
            input_per_1m=0.625, cached_input_per_1m=0.0625, output_per_1m=5.00
        ),
    },
}


def calculate_cost(
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
    service_tier: Optional[str] = None,
) -> Dict[str, float]:
    """
    Calculate the cost of an API request based on token usage and service tier.

    Args:
        model_name: Name of the model (e.g., 'gpt-5', 'gpt-5.1')
        prompt_tokens: Number of prompt tokens (uncached)
        completion_tokens: Number of completion tokens
        cached_tokens: Number of cached prompt tokens
        service_tier: Service tier ('default', 'flex', etc.). Defaults to 'default' if None.

    Returns:
        Dictionary with 'input_cost', 'output_cost', and 'total_cost' in USD
    """
    # Normalize model name to match pricing table keys
    model_key = model_name.lower()
    if model_key not in PRICING_TABLE:
        # Try to extract base model name (e.g., 'gpt-5' from 'gpt-5-turbo')
        if model_key.startswith("gpt-5.1"):
            model_key = "gpt-5.1"
        elif model_key.startswith("gpt-5"):
            model_key = "gpt-5"
        else:
            model_key = "default"

    # Normalize service tier (default to 'standard' if not specified)
    tier_key = (service_tier or "default").lower()

    # Get pricing information
    if tier_key not in PRICING_TABLE[model_key]:
        # Fallback to standard tier if specified tier not found
        tier_key = "default"

    pricing = PRICING_TABLE[model_key][tier_key]

    # Calculate costs (convert from per-1M to actual cost)
    uncached_tokens = prompt_tokens - cached_tokens
    if uncached_tokens < 0:
        # If cached_tokens > prompt_tokens, assume all are cached
        uncached_tokens = 0
        cached_tokens = prompt_tokens

    input_cost_uncached = (uncached_tokens / 1_000_000) * pricing.input_per_1m
    input_cost_cached = (cached_tokens / 1_000_000) * pricing.cached_input_per_1m
    output_cost = (completion_tokens / 1_000_000) * pricing.output_per_1m

    total_input_cost = input_cost_uncached + input_cost_cached
    total_cost = total_input_cost + output_cost

    return {
        "input_cost": total_input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
        # Additional breakdown for debugging
        "input_cost_uncached": input_cost_uncached,
        "input_cost_cached": input_cost_cached,
    }


def get_pricing_info(
    model_name: str, service_tier: Optional[str] = None
) -> PricingTier:
    """
    Get pricing information for a specific model and service tier.

    Args:
        model_name: Name of the model
        service_tier: Service tier. Defaults to 'standard' if None.

    Returns:
        PricingTier object with pricing information
    """
    # Normalize model name
    model_key = model_name.lower()
    if model_key not in PRICING_TABLE:
        if model_key.startswith("gpt-5.1"):
            model_key = "gpt-5.1"
        elif model_key.startswith("gpt-5"):
            model_key = "gpt-5"
        else:
            model_key = "default"

    # Normalize service tier
    tier_key = (service_tier or "default").lower()
    if tier_key not in PRICING_TABLE[model_key]:
        tier_key = "default"

    return PRICING_TABLE[model_key][tier_key]
