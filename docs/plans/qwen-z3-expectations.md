# Сохранённые предложения Qwen → экспертная проверка → Z3

Разрешено поручением пользователя 2026-11-06. База после fetch проверена:
`9f3a1a0b440535ae1513e2bd64a7c9d1c62d58ee`; собственные ветка
`experiment/qwen-z3-expectations` и worktree. F2 4c62684 и Qwen c03d343
изучаются read-only, без merge и inference. Прежнее formal ядро/bridge,
AI 1.0, backend/worker/frontend/миграции и PROPOSED-хранение не меняются.

## Технический план

1. [x] Проверить базу/ветки, изучить bridge, Qwen transport и F2 exact state DTO.
2. [x] Локальная закрытая схема предложения + конвертер; сохранённый raw ответ
   и хеши не исправляются, origin AI назначается доверенным кодом конвертера.
3. [x] Отдельные reference и expert-review формы, связанные с case/input/raw/
   packet hash; pending/rejected не разрешают Z3. Синтетическое подтверждение
   возможно только для внутреннего точного зарегистрированного эталона.
4. [x] CLI сохранённых ответов, подготовка review, запуск approved snapshot,
   отчёты с отдельными стадиями ошибок и без финальной семантической точности.
5. [x] 19 bridge cases + применимые S01–S14, coverage applicability; раздельные
   независимые предварительные references и saved-model proposals.
6. [x] Документация handoff Qwen и F2 mapping/missing-fields, тесты/регрессии,
   Ruff, independent review при доступности; commit и push только своей ветки.

Экспертная разметка прежних evals предварительная, не утверждённый semantic gold.
Технические reference-структуры не становятся подтверждённым смыслом отзывов.
Готовность принять реальные сохранённые ответы не означает проведённый inference.

Проверки завершены: 125 тестов PASS, Ruff check/format PASS; независимое ревью
завершено, замечание лимита collect устранено. Отчёт —
[VALIDATION](../../experiments/qwen_z3/VALIDATION.md). Commit и push выполняются
только в собственной экспериментальной ветке; main и другие ветки не объединяются.
