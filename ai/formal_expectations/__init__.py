"""Deterministic pair classification, independent of LLMs and backend F2."""

from .diagnostics import ErrorCode
from .limits import Limits
from .model import Analysis, Classification
from .service import analyze

__all__ = ["Analysis", "Classification", "ErrorCode", "Limits", "analyze"]
