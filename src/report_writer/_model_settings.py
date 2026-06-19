"""Shared model-settings boilerplate for the decomposed writer agents.

Keeps the four-line settings dance (base_url / litellm usage / endpoint
reasoning_effort+verbosity) in one place so outline.py and chapters.py stay
focused on their prompts.
"""

from __future__ import annotations

from agents.models import get_default_model_settings

from ..agents.utils import (
    adjust_model_settings_for_base_url,
    apply_endpoint_model_settings,
    enable_usage_for_litellm,
    extract_model_name,
    resolve_model,
)


def build_model(model_spec):
    """Resolve a model spec into (model, model_settings) like the other agents."""
    model = resolve_model(model_spec)
    model_settings = get_default_model_settings(extract_model_name(model_spec))
    adjust_model_settings_for_base_url(model_spec, model_settings)
    enable_usage_for_litellm(model_spec, model_settings)
    apply_endpoint_model_settings(model_spec, model_settings)
    return model, model_settings
