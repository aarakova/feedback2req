"""Trusted preparation gate around the unchanged formal classifier."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict
from importlib.metadata import version

import z3

from ai.formal_expectations import Limits, analyze

from .model import BridgeResult, Verification, fingerprint
from .validation import prepare


def check_pair(
    data: dict | str | bytes,
    *,
    verify: Callable[[dict], Verification] | None,
    limits: Limits | None = None,
) -> BridgeResult:
    prepared = prepare(data, limits=limits)
    packet = prepared.packet
    digest = fingerprint(packet) if packet is not None else None

    def result(status, diagnostic=None, receipt=None, formal=None, solver=None):
        return BridgeResult(status, digest, deepcopy(packet), receipt, formal, solver, diagnostic)

    if prepared.status != "prepared":
        return result(prepared.status, prepared.diagnostic)
    if verify is None:
        return result(
            "verification_required",
            {"code": "verification_required", "rule": "trusted_verifier_required"},
        )
    try:
        receipt = verify(deepcopy(packet))
    except Exception:  # noqa: BLE001 -- trusted adapters may include source text in errors.
        return result(
            "blocked", {"code": "verification_failed", "rule": "trusted_verifier_failure"}
        )
    if type(receipt) is not Verification or receipt.packet_sha256 != digest:
        return result(
            "blocked", {"code": "verification_failed", "rule": "receipt_snapshot_mismatch"}
        )
    confirmations = (
        "basis_verified",
        "formalization_confirmed",
        "comparability_confirmed",
        "contexts_confirmed",
        "omega_complete_confirmed",
    )
    if (
        any(type(getattr(receipt, k)) is not bool for k in confirmations)
        or type(receipt.verifier_id) is not str
        or not receipt.verifier_id.strip()
        or type(receipt.justification) is not str
        or not receipt.justification.strip()
    ):
        return result("blocked", {"code": "verification_failed", "rule": "invalid_receipt"})
    for field in confirmations[:-1]:
        if not getattr(receipt, field):
            return result(
                "blocked", {"code": "verification_failed", "rule": field}, receipt=receipt
            )
    formal_input = packet["formal_input"]
    # A bare AI declaration complete=true is insufficient even for a singleton list.
    if "omega" in formal_input and not receipt.omega_complete_confirmed:
        return result(
            "blocked",
            {"code": "omega_unconfirmed", "rule": "trusted_completeness_required"},
            receipt=receipt,
        )
    config = limits or Limits()
    formal = analyze(deepcopy(formal_input), limits=config)
    solver = {
        "bridge_format_version": "1",
        "component_base": "cc8c62a9dc620092b2579597fbaab99d751abd88",
        "z3_solver_version": version("z3-solver"),
        "native_z3_version": z3.get_full_version(),
        "random_seed": 0,
        "limits": asdict(config),
    }
    return result(
        "checked" if formal.complete else "formal_failure",
        receipt=receipt,
        formal=formal.to_dict(),
        solver=solver,
    )
