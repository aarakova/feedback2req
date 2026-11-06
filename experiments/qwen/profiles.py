"""Explicit prompt profiles; no edits to either source prompt."""

from ai.group_findings.prompt import PROMPT_VERSION as PRODUCT_VERSION
from ai.group_findings.prompt import SYSTEM_PROMPT as PRODUCT_PROMPT

from .prompt import PROMPT_VERSION, SYSTEM_PROMPT


def prompt_profile(cfg):
    name = cfg.get("prompt_profile", "experimental")
    if name == "product":
        return name, PRODUCT_VERSION, PRODUCT_PROMPT
    if name == "experimental":
        return name, PROMPT_VERSION, SYSTEM_PROMPT
    raise ValueError("unknown_prompt_profile")
