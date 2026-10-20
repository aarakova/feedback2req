# API

Status: TEMPLATE for the external application API; no external payloads or
endpoint contracts are approved. DEC-006 selects HTTP API as part of the stack.
Approval record/revision: TODO; see [DECISIONS.md](DECISIONS.md).

Проект HTTP API первого текстового сценария находится в
[FIRST_TEXT_SLICE.md](FIRST_TEXT_SLICE.md#4-предлагаемый-http-api).
Он имеет статус PROPOSED, ревизия 1 от 2026-10-21; DEC-006 его не утверждает.

## API principles

TODO: Derive principles from approved requirements and architecture.

## Approved contracts

None yet. TODO: Record approved contracts, requirement references, and revisions.

## Error semantics

TODO: Define failures and client-visible behavior after design approval.

## Versioning considerations

TODO: Clarify compatibility and versioning needs; no strategy is selected.

## Unresolved endpoints/contracts

Первое предложение endpoints, payloads, ошибок и предусловий см. по ссылке выше.
После согласования соответствующие контракты переносятся сюда с записью ревизии.

## Граница внутренних AI-контрактов

Внутренние AI-контракты утверждены DEC-005 и специфицированы только в
[AI_CONTRACTS.md](AI_CONTRACTS.md). Они не являются HTTP API и не заполняют
этот шаблон внешними endpoints или транспортными решениями.
