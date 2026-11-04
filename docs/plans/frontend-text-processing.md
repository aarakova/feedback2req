# Frontend F1 — реальный путь от текста к находке

Основание: поручение пользователя от 2026-11-04 во вложении, не новый HTTP/AI-контракт.

## Исходные линии и интеграция

- Указанный backend F1: 0b5f3e096d2c6db3e785577401bd01be2d6fccdc.
- Frontend: be3528efb2e365d49803d94dde2f70711c438a9f.
- Фактический origin/main после fetch: cfb96f45ecbe2ef8487c1dd145cb081f3a90aec9.
  Он уже содержит обе указанные линии; ancestry проверена. Повторного merge нет.
- В чистом текущем изолированном worktree создана feat/frontend-text-processing
  от origin/main с --no-track. main, feat/project-workspace и чужие worktree не меняются.
- Незавершённые F2/AI-ветки не интегрируются. Собственные логические коммиты разрешены;
  публикация новой ветки отдельно этим поручением не запрошена.

## План и границы

1. До нового функционала: build и прежние 128 Playwright на объединённой базе.
2. Отдельные точные transport DTO/адаптеры; Idempotency-Key в ApiClient.
3. Материалы → явный выбор операции/сохранённого state → start/retry; unknown
   outcome сохраняет неизменное намерение/ключ, без автоматического повторного POST.
4. Реальные Run/Unit/Attempt, история/пагинация, ограниченный polling с AbortController.
5. Findings list/detail → exact Fragment state → Source с проверкой state_id;
   синтетика, фактическое ai_performed, coverage/annotations показываются отдельно.
6. Overview O1 — второстепенные реальные counts/latest run, семантические KPI остаются —.
7. Тесты с собственными API/PG/worker/synthetic provider, unit/fault/visual проверки,
   регрессии, снимки, фактические результаты и логические коммиты.

Не меняются backend/worker/миграции/AI-контракты/домен/исходный прототип. Внешние
AI-вызовы запрещены; положительный путь только в явно синтетическом изолированном
стенде. Нет группировки F2, вымышленных связей/требований или глобальных итогов из страниц.

## Выявленные особенности контракта

- Start: 1–32 inputs {kind,id,state_id}; extract только source, inspect также document.
- POST runs/retry требует UUID ключа. 202 — принятие команды, не успех AI.
- Retry — failed unit с точным expected_attempt_id; преемник новый Run/Unit.
- Списки — UUID order/items/next_cursor, не единый snapshot и не created_at order.
- O1 даёт material_counts/latest_run_id; semantic_metrics=not_implemented.
- Findings immutable, freshness отдельно; fragment locator — [start,end) в code points.
- Публичного чтения полного исторического Source state нет в перечне F1: при переходе
  проверяется ожидаемый state, новый текущий текст не подменяет exact evidence.
- Существующие тесты предполагали отсутствие backend F1; после проверки исходной базы
  потребуются адресные изменения этих ожиданий с сохранением проверок неподключённых F2,
  прав, неизвестных результатов, семантических KPI и исходных регрессий.

## Проверки и ресурсы

Build объединённой базы прошёл. Исходный Playwright-прогон: **128 passed, 0 failed**
до изменений frontend, реальные API/PG, без обновления эталонов.
Ресурсы имеют собственные префиксы f2r-f1front-adf660ee / f2r-front-f1-adf660ee;
новая PostgreSQL test DB без host ports/чужих volumes. Старые QA-экспорты направлены
в собственный ignored scratch через bind mounts, golden snapshots читаются без изменения.

## Итог

Будет заполнен по фактической реализации/проверкам, включая SHA собственных коммитов,
API, файлы, снимки, ошибки, ограничения и зависимости следующего F2-шага.
