# Изолированные проверки frontend F1

Эти файлы не импортируются приложением и не входят в Vite production entry.
Нужны настоящий API текущего checkout, отдельная PostgreSQL БД
`feedback2req_processing_f1_test` и отдельный worker. Использовать рабочие
контейнеры/volumes и внешние AI-модели для этих тестов нельзя.

## Подготовка

1. Создать собственную Docker-сеть и PostgreSQL 17 с отдельным временным volume/tmpfs,
   без общих портов и данных. Применить миграции через обычный runtime backend.
   Для пагинационных сценариев API настроить `F2R_PAGE_SIZE=2`; для dev Origin —
   `F2R_ALLOWED_ORIGIN=http://localhost:5173`, `F2R_LOCAL_HTTP=true`.
2. До запуска worker подготовить исторические состояния и ошибки в checks-образе
   с backend test dependencies (seed использует тестовый Synthetic helper):
   `PYTHONPATH=/workspace/backend:/workspace F2R_DATABASE_URL=<own-test-db-url>
   F1_TEST_API=http://<own-api>:8000 python /workspace/frontend/tests/support/seed_cases.py`.
   Checkout смонтирован в `/workspace`, запись разрешена только для собственного
   ignored `.local/frontend-f1/seed-manifest.json`. Скрипт проверяет имя БД;
   не применять его к чужому стенду, даже если имя БД совпало.
   Только этот fixture изменяет источник напрямую через ORM и создаёт терминальные
   причины. Это подготовка состояний UI, не воспроизведение настоящего истечения
   lease/deadline. Положительные браузерные сценарии используют реальный worker.
3. Запустить `synthetic_provider.py` отдельным тестовым процессом (порт 11434).
   Это локальный HTTP double Ollama, не языковая модель. Worker получает
   `F2R_PROCESSING_TEST_MODE=true`, `F2R_AI_TRANSFER_ENABLED=true`,
   `F2R_AI_PROVIDER_URL=http://<own-provider>:11434/api/chat`,
   `F2R_AI_MODEL=synthetic-test-only` и собственную БД.
   Команда worker: `python -m feedback2req.processing.worker`.
   Worker/provider находятся в собственной `--internal` сети; выхода к внешней
   модели нет. Обычный production worker с этим провайдером не запускать.
4. В браузерном контейнере с Node/Chromium и checkout выполнить:

   ```sh
   F2R_E2E_API_EXTERNAL=true F2R_API_PROXY_TARGET=http://<own-api>:8000 npm run test:e2e -- --reporter=line
   ```

   `processing-units.spec.ts` импортирует функции через Vite, поэтому в built-режиме
   его не запускать. Остальные сценарии F1 проверяют настоящие API/PG/worker;
   отдельные потерянные ответы, поздние чтения и 503 вводятся Playwright route.
   При сохранении прежних QA-экспортов можно смонтировать собственные scratch-каталоги
   поверх `docs/qa/observer-v3` и `docs/qa/observer-overview`; golden snapshots
   при этом читаются из настоящего checkout.

## Отсутствующий провайдер и production Nginx

После завершения положительных заданий остановить **только собственный** worker.
Запустить второй worker с той же тестовой БД, без provider URL/model и с
`F2R_AI_TRANSFER_ENABLED=false`, `F2R_PROCESSING_TEST_MODE=false`.
Выполнить `F2R_E2E_NO_PROVIDER=true ... npm run test:e2e -- processing.spec.ts
--grep 'unconfigured provider'`. Затем остановить этот worker и вернуть тестовый.
Положительный и отрицательный режимы нельзя смешивать конкурентно.

Для production-проверки собрать обычный frontend Dockerfile. Отдельный API использует
Origin `http://localhost:18080`, frontend обращается к нему по Docker alias `backend`.
Браузер получает `F2R_E2E_MODE=built`, `F2R_E2E_TUNNEL=<own-nginx>:80`;
TCP relay из репозитория сохраняет настоящие заголовки/Origin/cookies.
Fixtures и unit-импорты исходников в этом режиме недоступны и не подменяются.

## Снимки

`processing-visual.spec.ts` проверяет четыре экрана на 1440/1280/390/320 px.
`visual.css` скрывает только UUID/время/тестовую учётную запись для golden-сравнения.
Обычные снимки в `docs/qa/frontend-text-processing` не маскируются.
Обновлять эталоны можно только после просмотра фактических различий.
