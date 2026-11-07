"""Closed JSON grammar. No eval, imports, SMT text or executable formulas."""

import json
import re
from fractions import Fraction

from .diagnostics import ErrorCode, FormalError
from .limits import Budget
from .model import Allowed, Completion, Domain, Expectation, Request, SubjectModel

# A deliberately small, exact, multiplicative unit registry. No offsets/aliases.
UNITS = {
    "1": ("dimensionless", Fraction(1)),
    "s": ("time", Fraction(1)),
    "ms": ("time", Fraction(1, 1000)),
    "min": ("time", Fraction(60)),
    "m": ("length", Fraction(1)),
    "cm": ("length", Fraction(1, 100)),
    "mm": ("length", Fraction(1, 1000)),
    "kg": ("mass", Fraction(1)),
    "g": ("mass", Fraction(1, 1000)),
}
DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z", re.ASCII)


def fail(rule: str, code: ErrorCode = ErrorCode.INVALID_INPUT):
    raise FormalError(code, rule)


def _object(value, required: set[str], optional: set[str] = frozenset()):
    if type(value) is not dict:
        fail("object_required")
    if set(value) - required - optional:
        fail("unknown_field", ErrorCode.UNSUPPORTED_INPUT)
    if required - set(value):
        fail("missing_field")
    return value


def _text(value) -> str:
    if type(value) is not str or not value.strip() or len(value) > 256:
        fail("nonempty_bounded_string_required")
    return value


def _list(value) -> list:
    if type(value) is not list:
        fail("array_required")
    if len(value) > 4096:
        fail("collection_size", ErrorCode.RESOURCE_LIMIT)
    return value


def _strings(value, *, allow_empty=False) -> tuple[str, ...]:
    result = tuple(_text(item) for item in _list(value))
    if len(set(result)) != len(result):
        fail("duplicate_member")
    if not result and not allow_empty:
        fail("empty_set", ErrorCode.INVALID_FORMALIZATION)
    return result


def _number(value) -> Fraction:
    if type(value) is int:
        value = str(value)
    if type(value) is not str or len(value) > 64 or not DECIMAL.fullmatch(value):
        fail("exact_decimal_required")
    return Fraction(value)


def _unit(value) -> tuple[str, Fraction]:
    _text(value)
    if value not in UNITS:
        fail("unsupported_unit", ErrorCode.UNSUPPORTED_INPUT)
    return UNITS[value]


def _allowed(value, domain: Domain | None = None) -> Allowed:
    if type(value) is not dict or "kind" not in value:
        fail("constraint_required")
    kind = value["kind"]
    if type(kind) is not str or kind not in {"boolean", "enum", "interval"}:
        fail("constraint_kind", ErrorCode.UNSUPPORTED_INPUT)
    if domain is not None and kind != domain.values.kind:
        fail("constraint_domain_kind", ErrorCode.INVALID_FORMALIZATION)
    if kind == "interval":
        _object(value, {"kind", "lower", "upper", "unit"})
        dimension, scale = _unit(value["unit"])
        if domain is not None and domain.dimension != dimension:
            fail("unit_dimension_mismatch", ErrorCode.INVALID_FORMALIZATION)
        lower, upper = (_number(value[k]) * scale for k in ("lower", "upper"))
        if lower > upper:
            fail("reversed_interval", ErrorCode.INVALID_FORMALIZATION)
        if domain is not None and (lower < domain.values.lower or upper > domain.values.upper):
            fail("outside_parameter_domain", ErrorCode.INVALID_FORMALIZATION)
        return Allowed(kind, lower=lower, upper=upper)
    _object(value, {"kind", "allowed"})
    items = _list(value["allowed"])
    if kind == "boolean":
        if any(type(item) is not bool for item in items):
            fail("boolean_required")
        members = frozenset(items)
    else:
        members = frozenset(_strings(items))
    if not members:
        fail("empty_set", ErrorCode.INVALID_FORMALIZATION)
    if len(members) != len(items):
        fail("duplicate_member")
    if domain is not None and not members <= domain.values.members:
        fail("outside_parameter_domain", ErrorCode.INVALID_FORMALIZATION)
    return Allowed(kind, members)


def _domain(value) -> Domain:
    if type(value) is not dict or "kind" not in value:
        fail("domain_required")
    if value["kind"] == "interval":
        _object(value, {"kind", "lower", "upper", "unit", "dimension"})
        dimension = _text(value["dimension"])
        if _unit(value["unit"])[0] != dimension:
            fail("unit_dimension_mismatch", ErrorCode.INVALID_FORMALIZATION)
        return Domain(_allowed({k: v for k, v in value.items() if k != "dimension"}), dimension)
    allowed = _allowed(value)
    if allowed.kind == "boolean" and allowed.members != frozenset({False, True}):
        fail("boolean_domain_must_include_both", ErrorCode.INVALID_FORMALIZATION)
    return Domain(allowed)


def _conditions(value, model: SubjectModel) -> frozenset[str]:
    conditions = frozenset(_strings(value))
    if not conditions <= set(model.situations):
        fail("outside_situation_domain", ErrorCode.INVALID_FORMALIZATION)
    return conditions


def _expectation(value, model: SubjectModel) -> Expectation:
    _object(value, {"object_id", "parameter_id", "basis", "conditions", "values"})
    obj, parameter = _text(value["object_id"]), _text(value["parameter_id"])
    if obj != model.object_id:
        fail("different_objects", ErrorCode.NOT_COMPARABLE)
    if parameter != model.parameter_id:
        fail("different_parameters", ErrorCode.NOT_COMPARABLE)
    return Expectation(
        obj,
        parameter,
        _text(value["basis"]),
        None if value["conditions"] is None else _conditions(value["conditions"], model),
        None if value["values"] is None else _allowed(value["values"], model.domain),
    )


def _completion(value, original: Expectation, model: SubjectModel) -> Completion:
    _object(value, {"conditions", "values"})
    conditions = _conditions(value["conditions"], model)
    values = _allowed(value["values"], model.domain)
    if (original.conditions is not None and original.conditions != conditions) or (
        original.values is not None and original.values != values
    ):
        fail("refinement_changes_known_data", ErrorCode.INVALID_FORMALIZATION)
    return Completion(conditions, values)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            fail("duplicate_json_key")
        result[key] = value
    return result


def _constant(_):
    fail("nonfinite_number")


def _walk(value, budget: Budget, depth=0, count=None):
    # Preflight also covers Python callers: cycles, huge trees, custom objects.
    if count is None:
        count = [0]
    budget.remaining_ms()
    count[0] += 1
    if depth > 24 or count[0] > 50_000:
        fail("json_complexity", ErrorCode.RESOURCE_LIMIT)
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                fail("json_key_type")
            _walk(key, budget, depth + 1, count)
            _walk(child, budget, depth + 1, count)
    elif type(value) is list:
        for child in value:
            _walk(child, budget, depth + 1, count)
    elif type(value) is str:
        if len(value) > budget.limits.max_input_bytes:
            fail("input_bytes", ErrorCode.RESOURCE_LIMIT)
    elif value is not None and type(value) not in {bool, int}:
        fail("json_value_type")


def decode(value, budget: Budget) -> dict:
    if type(value) in {str, bytes}:
        try:
            raw = value.encode("utf-8") if type(value) is str else value
            if len(raw) > budget.limits.max_input_bytes:
                fail("input_bytes", ErrorCode.RESOURCE_LIMIT)
            value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
        except (ValueError, UnicodeError, RecursionError):
            fail("json_decode")
    _walk(value, budget)
    try:
        size = len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
    except (ValueError, UnicodeError):
        fail("json_encoding")
    if size > budget.limits.max_input_bytes:
        fail("input_bytes", ErrorCode.RESOURCE_LIMIT)
    if type(value) is not dict:
        fail("object_required")
    return value


def parse_request(value, budget: Budget) -> Request:
    value = decode(value, budget)
    _object(value, {"format_version", "model", "left", "right"}, {"omega"})
    if type(value["format_version"]) is not str or value["format_version"] != "1":
        fail("format_version", ErrorCode.UNSUPPORTED_INPUT)
    data = _object(value["model"], {"object_id", "parameter_id", "situations", "domain"})
    model = SubjectModel(
        _text(data["object_id"]),
        _text(data["parameter_id"]),
        _strings(data["situations"]),
        _domain(data["domain"]),
    )
    left, right = (_expectation(value[key], model) for key in ("left", "right"))
    if "omega" not in value:
        if any(e.conditions is None or e.values is None for e in (left, right)):
            fail("unknown_requires_omega", ErrorCode.INCOMPLETE_OMEGA)
        variants = (
            (Completion(left.conditions, left.values), Completion(right.conditions, right.values)),
        )
        complete = True
    else:
        omega = _object(value["omega"], {"complete", "variants"})
        if type(omega["complete"]) is not bool:
            fail("boolean_required")
        items = _list(omega["variants"])
        if not items:
            fail("empty_omega", ErrorCode.INVALID_FORMALIZATION)
        if len(items) > budget.limits.max_variants:
            fail("variant_limit", ErrorCode.RESOURCE_LIMIT)
        variants = []
        for item in items:
            budget.remaining_ms()
            _object(item, {"left", "right"})
            variants.append(
                (_completion(item["left"], left, model), _completion(item["right"], right, model))
            )
        variants = tuple(variants)
        complete = omega["complete"]
    return Request(model, left, right, variants, complete)
