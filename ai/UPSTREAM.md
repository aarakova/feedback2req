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
