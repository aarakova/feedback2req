# Интеграционная сборка Observer

Ветка `integration/full-workflow-ui`. Это отдельная тестовая сборка с настоящими
Nginx, API, PostgreSQL и worker. Положительные AI-ответы **синтетические**;
Ollama/Qwen, веса и внешние сервисы не запускаются. Не используйте реальные
пользовательские материалы. Обычный production Compose сохраняется отдельно.

## Запуск собственного стенда

Из корня интеграционного worktree, Docker Desktop с Linux containers и Compose:

```sh
docker compose -f compose.workflow-test.yaml build backend frontend browser
docker compose -f compose.workflow-test.yaml build checks
docker compose -f compose.workflow-test.yaml up -d --wait db backend frontend provider
docker compose -f compose.workflow-test.yaml run --rm checks python frontend/tests/support/seed_cases.py
docker compose -f compose.workflow-test.yaml run --rm checks python frontend/tests/support/seed_groups.py
docker compose -f compose.workflow-test.yaml up -d --wait worker
```

Открыть http://localhost:18080, зарегистрировать **новую тестовую** учётную запись,
создать проект, сохранить отзыв и документ. «Обработка» → выбрать сохранённый
отзыв → extract_feedback → «Создать задание». Inspect принимает и документы,
считает символы/байты и не создаёт находки. Сохранение материала не запускает AI.
Находка ведёт к точной цитате и состоянию исходного текста. Раздел «Обработка»
показывает историю и позволяет разрешённый ручной повтор F1. Provider/model,
synthetic, ai_performed и coverage отображаются раздельно.

Для чтения подготовленных групп и конфликтов тестовый login находится в
`.local/workflow/groups.json`; пароль — `frontend-test-only-2026`, только этот
изолированный стенд. Раздел «Находки» показывает сохранённые группы, отдельные
позиции, точные цитаты и исторические states. Seed оставляет F3 queued Run;
его завершает настоящий worker, после чего результат виден в общей истории.
Пример успешного ungrouped Run также указан в manifest. Исторический human state
подготовлен ORM fixture и не является поддержкой human-write API.
[Галерея](qa/full-workflow/index.html) содержит явно синтетические снимки.

Стенд имеет собственные `feedback2req-workflow-test` project/networks/volumes,
БД `feedback2req_processing_f1_test`, subnet `10.219.246.0/28` и порт 18080.
Проверьте, что эти имена/порт свободны и принадлежат этому checkout.
Не применяйте файл как overlay к рабочему project. Обе сети internal;
провайдер — локальный HTTP double без языковой модели. Seed допустим только
до запуска собственного worker; при повторной подготовке сначала остановите его.

Остановка с сохранением всей тестовой БД:

```sh
docker compose -f compose.workflow-test.yaml stop
```

Не используйте down --volumes, volume prune или reset рабочей БД. Для повторного
старта сохранённого стенда достаточно `up -d --wait db backend frontend provider worker`;
повторный seed для ручного использования не требуется.

## Воспроизводимые проверки

```sh
docker compose -f compose.workflow-test.yaml run --rm browser npm run test:e2e -- --reporter=line
docker compose -f compose.workflow-test.yaml run --rm checks python -m pytest backend/tests -q -W error
docker compose -f compose.workflow-test.yaml run --rm checks python scripts/validate_ai_contracts.py
docker compose -f compose.workflow-test.yaml build ai-checks
docker compose -f compose.workflow-test.yaml run --rm ai-checks
```

Browser запускается в отдельном контейнере, relay сохраняет настоящий localhost
Origin/cookies и проксирует байты через production Nginx. Production не раздаёт
fixtures/Vite unit imports: соответствующие skips ожидаемы, это не успешные тесты.
Полный Vite-прогон и отдельный отрицательный provider сценарий воспроизводятся
последовательно в [CI workflow](../.github/workflows/workflow-ui.yml).
Исторические terminal fixtures подготавливаются ORM; это проверка отображения,
а реальные lease/deadline/COMMIT гонки проверяются отдельными backend tests.

## Границы публичного цикла

Публичные F1 команды уже утверждены. Чтение F2 опирается на три существующих
GET [контракта групп](FINDING_GROUPS_API.md); новый публичный grouping POST
ещё требует решения. Requirement/Revision/VerificationResult и доверенный
обмен Z3 не добавляются под видом готовых контрактов.
[Пакет согласования](proposals/workflow-contracts.md) содержит независимые A/B/C.
Автономные компоненты и research replay не являются действиями пользователя
в приложении. Реальные модельные показатели и готовность Qwen не заявляются.

| Этап | Доступность |
|---|---|
| F1 | Browser/API/PG/worker: сохранение, inspect/extract, история/retry, находки/цитаты |
| F2/F3 | Browser читает реальные сохранённые группы/conflicts/exact states и историю; enqueue пока внутренний Python |
| Generation | Автономный [модуль](../ai/generate_requirements/README.md) и synthetic replay, без Requirement storage/UI сохранения |
| Verification | Автономный [модуль](../ai/verify_requirement/README.md); продуктовый запуск требует настоящей сохранённой Revision |
| Z3/bridge | Автономные [формальный checker](../ai/formal_expectations/README.md) и [trusted bridge](../ai/formal_expectations_bridge/README.md); нет product exporter/review/result API |
| Qwen | [Исследовательский комплект](../experiments/qwen/LIVE_EVALUATION.md) и synthetic transport; реальный inference не выполнен |

Например, автономная проверка подготовленного синтетического ограничения:

```sh
docker compose -f compose.workflow-test.yaml run --rm ai-checks python -m ai.formal_expectations ai/formal_expectations/examples/K.json
```

K/D/S/U относятся к переданной формальной модели; timeout/unknown/resource_limit
являются отдельной диагностикой. Bridge/эксперимент требуют доверенную проверку
формализации и полноты Ω. Этот CLI пример не подтверждает реальные отзывы.

Ход интеграции, точные исходные SHA и фактические результаты проверок —
[рабочий отчёт](plans/full-workflow-ui.md). Старые отчёты исходных веток описывают
свои состояния и не заменяют проверки интеграционной версии.
