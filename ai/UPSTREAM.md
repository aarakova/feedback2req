# Происхождение компонента

Runtime Python-файлы `ai/group_findings/`, `ai/__init__.py`, зависимости и
автономные тесты перенесены без изменения из коммита
`f5ffa486ccaee7ebefe169e7cca2430edda221c8`, ветка `feat/ai-group-findings`.
[Исходная инструкция](https://github.com/aarakova/feedback2req/blob/f5ffa486ccaee7ebefe169e7cca2430edda221c8/ai/group_findings/README.md).

Из того же снимка перенесены только необходимые тестам build_cases.py и
JSON-фикстуры в `evals/ai/grouping/`. Общий оценочный контур и модели не
импортированы. Алгоритм, prompt и валидатор компонента не переписывались.

Backend-подключение описано в
[FINDING_GROUPS_API](../docs/FINDING_GROUPS_API.md). Компонент требует
`docs/contracts/ai/v1/` относительно корня своего runtime-каталога. Docker
сохраняет этот путь отдельно от уже используемого F1 пути `/docs/`.

Все интеграционные проверки используют явный synthetic provider. Готовность
хранилища и структурная корректность не доказывают смысловое качество модели.
Внешний provider не выбирается автоматически и не включается этой интеграцией.

## Интеграция полного workflow, 2026-11-07

Автономные generate_requirements/verify_requirement, их tests/evals и handoff
перенесены выборочно из ab34793a06db660e158f3320f36533467d35bf66.
Общий grouping не импортируется повторно: единственная дельта provider из этой
ветки — переопределяемые system_prompt/response_schema для наследующих адаптеров;
алгоритм, grouping prompt и validation сохранены. README/MODEL_SELECTION и
synthetic replay взяты из той же версии.

formal_expectations/bridge и experiments/qwen_z3 с тестами/примером/предложениями
перенесены из a963d8ebb778d80eac2e2cbcadb33d57924a12b7; experiments/qwen —
из e2158ad0611b9693bc5c2490fe08c6a865b158d8. Это автономные инструменты.
Docker production копирует только ai/group_findings и не устанавливает Z3;
дополнительный ai-checks image изолирован и запускается с network_mode=none.
Реальный inference, provider/model и доверенный F2 exchange не утверждаются.
AI JSON Schema 1.0, DOMAIN и REQUIREMENTS этим переносом не меняются.
