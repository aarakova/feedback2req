"""Autonomous, explicitly verified group_findings → formal expectations bridge."""

from .model import BridgeResult, Preparation, Verification, fingerprint
from .service import check_pair
from .validation import prepare

__all__ = ["BridgeResult", "Preparation", "Verification", "check_pair", "fingerprint", "prepare"]
