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

## Реализованный путь и соответствие Observer

| Часть | До F1 | После подключения | Источник данных / граница |
| --- | --- | --- | --- |
| Материалы | Создание/чтение, запуск недоступен | Отдельные действия создания и обработки; переход с точным state | Существующие sources/documents; создание не вызывает Run |
| Обработка | Четыре будущих этапа | Выбор операции/1–32 входов, start, история, Run/Unit/Attempt, retry | Реальные runs/units; inspect_text отделён от извлечения |
| Статусы | Только изолированные UI-fixtures | queued/running/completed/failed/cancelled/partial, даты и причины | Серверные состояния без процентов и ложного завершения AI |
| Неизвестный POST | Не было команды F1 | Неизменный UUID/intent, блокировка нового действия, ручной same-key replay | sessionStorage без текста/credentials; GET-история независима |
| Находки | Структура Observer, unavailable | Пагинация, detail, типы, direct/inferred, freshness, provenance, coverage/annotations | F1 findings; группы/связи требований не создаются |
| Свидетельства | Тестовые представления | Finding → exact Fragment state → ожидаемый Source state | Точные ссылки и code points; новый текст не подменяет исторический |
| Обзор | Четыре неизвестных семантических KPI | Та же композиция; вторичный блок количества материалов/последнего Run | O1, без вычислений по страницам и замены KPI |
| Будущие стадии | Каркас четырёх этапов | Сохранён ниже действующих F1-команд | F2/генерация/проверка по-прежнему не подключены |

Палитра, sidebar/header, шесть разделов, 4 KPI, пары основных панелей обзора,
два вида материалов и встроенные состояния Observer сохранены. Убрана отметка
«Позже» только у уже подключённых находок/обработки. Находки имеют отдельную
прямую страницу и страницу точного фрагмента; существующие маршруты сохранены.

### Реальные API

Все пути ниже относительно `/api/v1/projects/{project_id}`:

- `GET overview` — авторитетные counts/latest Run, semantic metrics unavailable.
- `POST runs`, `GET runs`, `GET runs/{id}` — явный запуск и наблюдение.
- `POST units/{id}/retries` — failed Unit и точный expected_attempt_id.
- `GET findings[?attempt_id=…]`, `GET findings/{id}` — список и detail.
- `GET fragments/{id}/states/{state_id}` — сохранённая цитата и locator.
- Существующие `GET sources/documents[/{id}]` — выбор входов, проверка текущего
  состояния перед retry и переход к материалу. Формы создания сохранены.

Transport DTO отделены от локальных view models. Команды ожидают именно 202;
потерянный/5xx/неопределённый ответ не разрешает новый автоматический POST.
GET активного Run выполняется каждые 2 секунды, максимум 60 успешных чтений;
при временной ошибке — не более трёх последовательных ошибок с задержками
5/10 секунд. Затем доступно ручное обновление. AbortController отменяет
наблюдение при смене проекта/страницы, а не серверное выполнение.

### Изменённые компоненты и файлы

- [App](../../frontend/src/App.tsx), [routes](../../frontend/src/routes.ts),
  [ProjectLayout](../../frontend/src/ProjectLayout.tsx),
  [ProjectNavigation](../../frontend/src/ProjectNavigation.tsx),
  [ProjectOverview](../../frontend/src/ProjectOverview.tsx),
  [Materials](../../frontend/src/Materials.tsx), [main](../../frontend/src/main.tsx).
- [ApiClient](../../frontend/src/api.ts): опциональные Idempotency-Key/expectedStatus;
  прежние cookie/Origin/CSRF/session сохранены.
- [Модули F1](../../frontend/src/processing/): dto, adapters, pending, commands,
  reads, polling, ResultDetails, ProjectProcessing, ProjectFindings,
  ProjectOverviewData и scoped processing.css.
- [Findings](../../frontend/src/observer/Findings.tsx),
  [Processing](../../frontend/src/observer/Processing.tsx),
  [ui](../../frontend/src/observer/ui.tsx),
  [viewModels](../../frontend/src/observer/viewModels.ts): расширения существующих
  представлений и явная недоступность групп/отношений F2.
- Новые processing.spec, processing-faults.spec, processing-units.spec,
  processing-visual.spec и [test support](../../frontend/tests/support/README.md).
  Адресные изменения прежних project-layout/overview/observer-visual проверок
  отражают наличие действующего F1; запреты неподдержанного F2 сохранены.
- 16 новых golden-снимков F1; 14 прежних эталонов изменились по ожидаемой причине:
  overview — блок O1, findings — реальные список/состояния, processing — команды
  и история, mobile materials — ссылка явного запуска. Пороги сравнения не менялись.
  Остальные прежние эталоны сохранены. Маскирование новых снимков скрывает только
  изменчивые ID/время/тестовую учётную запись, не бизнес-состояния/числа/цитаты.
- DEC-017, адресное описание в ARCHITECTURE/TESTING и этот отчёт;
  [галерея](../qa/frontend-text-processing/index.html), 16 немаскированных снимков.

### Ограничения и следующий шаг

- Положительный путь подтверждается только синтетическим provider в отдельной
  internal Docker-сети. Внешняя модель не вызывалась; качество реального AI не
  проверялось. Маркер synthetic виден на Run, находке и exact Fragment странице.
- У API нет полного исторического Source state: сохранённая цитата остаётся
  доступна, но текущий полный текст скрывается при несовпадении state. Для
  полного исторического просмотра нужен отдельно утверждённый backend-контракт.
- История в серверном UUID-порядке, latest Run получен отдельно из O1. Страницы
  не образуют общего snapshot; загруженное количество не является total проекта.
- Ключ неизвестной команды восстанавливается в пределах вкладки/sessionStorage.
  При запрете хранилища остаётся предупреждение и ключ в памяти; закрытие вкладки,
  logout/401 или ручная очистка storage удаляют локальное восстановление. История
  по GET остаётся способом сверки; новый POST после reload автоматически не идёт.
- Группы, отношения требований, человеческие решения и семантические агрегаты
  ещё не подключены. Ни отсутствие API, ни пустая отдельная попытка не доказывают
  отсутствие групп/требований или полноту анализа проекта.
- Следующая небольшая итерация: после утверждённой интеграции backend F2 добавить
  transport DTO/адаптер групп, пагинированный список/detail состава, конфликтующие
  позиции и точные ссылки на F1 evidence. Критерий — состав/свежесть/неполнота
  из сервера, без frontend-группировки и фиктивных связей. Генерация требований —
  следующая отдельная итерация с утверждёнными командами, правами, редакциями и
  критериями проверки/человеческого решения; нынешний UI не вводит эти контракты.

### Фактическая проверка (2026-11-06)

- TypeScript/Vite production build — PASS, 45 модулей.
- Обычный frontend Dockerfile (production Nginx) — PASS.
- Backend F1: `pytest -q -p no:cacheprovider tests/test_processing.py
  tests/test_processing_provider.py` — **24 passed** (на собственной test DB,
  уникальные схемы, без внешних AI-вызовов).
- Первая полная проверка изменённого frontend выявила один прежний visual test:
  эталон overview не содержал нового O1-блока. Различия просмотрены, причины
  перечислены выше. Новый набор F1 из 16 изображений также просмотрен на
  представительных desktop/mobile экранах; строгий повтор выполняется без update.
- Целевые шесть проверок после обновления ожидаемых эталонов — **6 passed**:
  визуальные композиции/палитра прототипа, защита от F2/fixtures в App, 503/backoff
  и три модульных browser-теста адаптеров/metadata/routes.
- Полный Vite-прогон без обновления эталонов — **149 passed, 1 skipped, 0 failed**
  (8 минут); skip — отдельная проверка без провайдера.
- Заключительный просмотр уточнил нормализацию регистра UUID в query routes,
  удалил устаревшую screen-reader подсказку у активного запуска и связал обновление
  истории с повторным чтением O1 latest Run. Повторные целевые проверки —
  **5 passed, 1 skipped**: три модульных теста, прямой маршрут материалов/access и
  реальный provider_not_configured на отдельном worker без провайдера.
  Его ai_performed=false и отсутствие findings подтверждены настоящим API.
  Skip относится к положительному сценарию, который grep также выбрал по metadata,
  но который намеренно отключён в режиме без провайдера.
- Итоговый production/Nginx-прогон на исходниках `dfdea7e`, без update snapshots:
  **91 passed, 59 skipped, 0 failed** (4,7 минуты). Skips: 55 прежних fixture-only
  сценариев + 3 browser-unit с Vite imports + отдельно выполненный сценарий без
  провайдера. Настоящие Nginx/API/PG/worker; cookie/Origin/CSRF и прежние операции
  проверены браузером. Все действующие F1-сценарии и 16 новых golden-снимков прошли.
  Исходный прототип также прочитан существующим visual test: сравнение палитры,
  размеров основных элементов и адаптивных композиций не ослаблялось.

Обычные успешные/ошибочные задачи выполняются реальным worker через локальный
HTTP double. Смена исторического source state и терминальные lease/deadline/
execution/error reason fixtures подготовлены через backend service/ORM только
в собственной тестовой БД; это не воспроизведение всех настоящих аварий worker.
Потерянные ответы/поздние чтения/503 вводятся Playwright после/вокруг реальных API.
Docker Desktop был перезапущен вне этих команд; после возобновления подняты
только собственные контейнеры и заново подготовлена собственная tmpfs test DB.
По окончании остановлены только семь собственных активных контейнеров;
общие Docker-ресурсы, окружения других задач и рабочие БД не изменялись.

Воспроизводимые команды прогонов (в собственном browser-контейнере, `/workspace/frontend`):

```sh
F2R_E2E_API_EXTERNAL=true F2R_API_PROXY_TARGET=http://<own-api>:8000 npm run test:e2e -- --reporter=line,json
F2R_E2E_MODE=built F2R_E2E_TUNNEL=<own-nginx>:80 npm run test:e2e -- --reporter=line,json
```

Полная подготовка отдельного provider/worker, seed и отрицательного режима —
в [test support](../../frontend/tests/support/README.md). Прогоны последовательные,
эталоны в итоговых прогонах не обновлялись; retry тестового раннера отключён.

Полный backend suite/CI, внешняя модель, Firefox/Safari, TLS и независимое
ревью этой итерации не выполнялись. Backend/worker/миграции/AI-контракты не менялись.

### Коммиты

- `7bb37ac` — исходная база и утверждённые границы F1.
- `4cfeaa4` — transport DTO, адаптеры, безопасные команды/чтения/polling.
- `dfdea7e` — действующие F1-экраны, навигация, O1 и точные evidence-ссылки.
- Проверки/снимки/этот отчёт фиксируются отдельным заключительным коммитом;
  его SHA указан в итоговом сообщении. Main и исходная frontend-ветка не менялись.
