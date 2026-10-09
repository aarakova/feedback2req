# Product-agent architecture

Статус: ШАБЛОН для будущего проектирования архитектуры. Обязанности продуктовых
агентов ограничены утверждённой baseline [DOMAIN.md](DOMAIN.md) и
[REQUIREMENTS.md](REQUIREMENTS.md) от 2026-10-09; оркестрация и реализация
не определены. См. [DECISIONS.md](DECISIONS.md).
These are future application roles, not the Codex development agents in
`.codex/agents/`.

## Product-agent roles

User-stated responsibilities, not an implementation design:

- Feedback Analysis Agent: выявляет и группирует проблемы, пожелания, наблюдения
  и потребности из обратной связи; различает прямые высказывания и интерпретации,
  сохраняет конфликтующие позиции и обозначает неопределённость.
- Requirements Generation Agent: преобразует находки, подтверждённые обратной
  связью, в проекты требований, сохраняя ссылки на `FeedbackFragment`.
  `ProductDocument` служит контекстом, а не достаточным основанием новой
  пользовательской потребности или `Requirement`.
- Requirements Verification Agent: проверяет противоречия, неподтверждённые
  выводы, неоднозначность, дубли, недостаток оснований и вопросы для человека.
  Критичные замечания показывает явно, не скрывает и не считает разрешёнными
  автоматически. `VerificationResult` не утверждает `Requirement`.

TODO: Clarify detailed responsibilities and obtain design approval.

## Inputs

TODO: Specify each role's approved input contract and evidence context.

## Outputs

TODO: Specify outputs and validation criteria without assuming schemas.

## Boundaries

Analysis, generation, and verification remain separate product responsibilities.
TODO: Define allowed actions and boundaries; logical role separation does not
select a deployment topology or framework.

## Handoffs

TODO: Design approved handoffs and orchestration; no protocol is selected.

## Failure/uncertainty handling

Неопределённые и неподтверждённые выводы обозначаются явно. Несовместимые
отзывы сохраняются как разные позиции. Неподтверждённый или спорный вывод не
становится утверждённым требованием автоматически; окончательное решение
принимает человек с соответствующим правом. Условия утверждения при
неразрешённом критичном замечании остаются открытыми.
TODO: Design failure handling and human clarification behavior.

## Traceability requirements

Для нового требования сохраняется связь через находки с подтверждающими
`FeedbackFragment`. `ProductDocument` помогает понять текущий продукт и
расхождение, но сам по себе не обосновывает новое `Requirement`. Исходный
материал, результат AI, правка человека и текущий результат различимы.
После удаления источника происхождение результата (provenance/lineage) и
доступность источника (source accessibility) различаются: удалённый материал
не показывается как доступный, а происхождение и авторство производных
результатов не стираются автоматически. Существенное изменение основания
требует повторной проверки зависимых результатов или явной отметки об их
необходимой актуализации; см. [инварианты AI](AI_VALIDATION.md#project-invariants).
TODO: Design the traceability mechanism after requirements approval.

## Open questions

TODO: Record unresolved role boundaries, contracts, and orchestration decisions.
