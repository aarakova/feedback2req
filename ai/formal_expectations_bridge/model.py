"""Local adapter types. These are not approved backend or AI-contract DTOs."""

import hashlib
import json
from dataclasses import asdict, dataclass


def fingerprint(value: dict) -> str:
    """Integrity binding, never a substitute for application identity or permission."""
    raw = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


class BridgeError(Exception):
    def __init__(self, code: str, rule: str):
        self.code, self.rule = code, rule
        super().__init__(code + ":" + rule)


@dataclass(frozen=True)
class Verification:
    """Created by trusted code supplied as a callable, never parsed from input.

    All confirmations cover the exact packet hash, including original evidence,
    versions, mappings, omissions, uncertainty and the actual Ω list.
    """

    packet_sha256: str
    verifier_id: str
    justification: str
    basis_verified: bool
    formalization_confirmed: bool
    comparability_confirmed: bool
    contexts_confirmed: bool
    omega_complete_confirmed: bool


@dataclass(frozen=True)
class Preparation:
    status: str
    packet: dict | None
    diagnostic: dict | None


@dataclass(frozen=True)
class BridgeResult:
    status: str
    packet_sha256: str | None
    preparation: dict | None
    verification: Verification | None
    formal_result: dict | None
    solver: dict | None
    diagnostic: dict | None
    # No result asserts an unconditional meaning or resolves a human decision.
    interpretation: str = "conditional_on_supplied_model_and_verified_formalization"
    expert_evaluation: str = "separate_not_computed"

    def to_dict(self) -> dict:
        return asdict(self)
