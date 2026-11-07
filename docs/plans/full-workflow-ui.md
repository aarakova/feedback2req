# Интеграция Observer: рабочий план

Основание: поручение пользователя от 2026-11-06 во вложении. Это план работы,
не утверждение новых контрактов. Отдельный worktree `.local/worktrees/full-workflow-ui`,
ветка `integration/full-workflow-ui`, база `origin/main` cfb96f45ecbe2ef8487c1dd145cb081f3a90aec9.

## Исходники после git fetch origin

| Ветка | Точный SHA | План переноса |
|---|---|---|
| feat/frontend-text-processing | ae6dd06ebfc8f92847f4a70e57d6888257b4cd0d | merge F1, затем исправление CI |
| feat/backend-grouping-orchestration | be328080cbeb484b3e2b77866709775627884d98 | merge F2/F3 с сохранением main/F1 |
| feat/ai-verify-requirement | ab34793a06db660e158f3320f36533467d35bf66 | выборочный перенос автономных модулей/tests/evals |
| experiment/qwen-live-evaluation | e2158ad0611b9693bc5c2490fe08c6a865b158d8 | выборочный перенос experiments; без live inference |
| experiment/qwen-z3-expectations | a963d8ebb778d80eac2e2cbcadb33d57924a12b7 | выборочный перенос Z3/bridge/experiments и записей разрешений |

SHA совпадают с заданием. Merge-base main/frontend и main/AI/Qwen/Z3 — cfb96f45;
main/backend — 1713498cf67f44c860adfa73d93642240c74daf6. Backend уже содержит
grouping из f5ffa48; AI/Qwen/Z3 наследуют 410b936/88ca281. Повторный импорт
общего grouping исключается; отличия provider проверяются отдельно.
Пересечения: docs/ARCHITECTURE, DECISIONS, TESTING; AI/grouping, evals/grouping,
README. Историю утверждений сохраняем, новые PROPOSED контракты не реализуем.

## Этапы

- [x] Fetch, история/diff/merge-base, отдельные ветка/worktree; импорт F1.
- [x] Воспроизвести CI 42263266660; исправить стенд/часы; build и полный Nginx F1.
- [x] Интеграция F2/F3, PG/API/migration tests, worker synthetic checks.
- [x] React read-only groups/conflicts/exact states и интеграционные browser tests.
- [x] Автономные generation/verification/Z3/bridge/Qwen, unit/eval проверки.
- [x] Конкретные пакеты согласования: grouping POST; Requirement/Revision/checks;
      доверенный обмен формализации. Ожидание решения для зависимых частей.
- [ ] Полный прогон, снимки синтетического backend, инструкция запуска,
      логические коммиты, публикация интеграционной ветки и CI.

## Установленная причина CI

GitHub job 128048460848: 81 passed / 59 skipped / 10 failed. Положительные
extract-тесты получили provider_not_configured; исторические fixtures не подготовлены
(ENOENT seed-manifest.json). Отдельно clock.pauseAt(new Date()) иногда перемещает
установленные browser-часы назад. В CI не было подготовки описанного F1 test support.
Эталоны и assertions не ослабляются; production provider не включается.

## Проверки и ограничения

Отдельный Compose project/сети/PG volume; рабочие данные и чужие worktrees не трогаем.
Никакого удаления volumes. Synthetic HTTP double маркирован; внешнего AI/скачивания
весов нет. DOMAIN, REQUIREMENTS, AI Schema 1.0 неизменны. Проверяем build, строгие
Playwright Nginx/Vite, PG/API/миграции/recovery, автономные tests/evals, CI.
Невыполненные проверки и ограничения фиксируются по факту.

## Выполненные проверки, 2026-11-06/07

- F1 до интеграции новых этапов: воспроизведён failed вместо completed без
  провайдера; после исправления полного стенда **91 passed / 59 skipped / 0 failed**
  через Nginx (6.4 мин), без обновления эталонов. Clock также прошёл.
- Сборки tsc/Vite и production Docker frontend/backend прошли.
- После F2/F3: новый browser набор **4 passed** — PG pagination, historical conflict,
  current vs exact state, no-group success, queued F3 реальным worker, 503,
  project isolation, ширины 1440/1280/390/320. Снимки явно synthetic.
- Автономные компоненты: **235 passed, 247 subtests passed** (258.53 с), network none.
  Grouping replay: 3 исходных + 8 controls; generation: 11 + 15; verification:
  18 + 22. Везде technical_diagnostics=0; semantic_quality=not_evaluated.
- AI contracts: 9 schemas, 88 refs, 38 positive/34 negative, 399 unknown-field
  mutations и 20 APP fixture pairs — PASS. DOMAIN/REQUIREMENTS/AI schemas не менялись.
- Первый полный backend запуск имел 17 failed / 196 passed из-за наследования
  браузерных page_size/Origin; отдельный конкурентный PG прогон также мешал
  проверке advisory lock. Исправлено окружение checks, сами assertions сохранены.
  Целевые grouping tests после исправления — **47 passed**. Последовательный
  полный прогон выполняется отдельно; неполные логи не являются PASS.
- Docker Engine остановился между turns; прерванные backend/AI результаты
  не заявлены успешными. После запуска Engine поднят только собственный стенд.
- Lint backend и нового seed_groups — PASS. Запуск общего lint на Windows bind
  показал EXE002 на прежнем script (mount execute bit); явное применение backend
  config ко всему корню также меняет isort root и не считается проверкой baseline.
  Существующие файлы/правила не переписывались для обхода этих различий окружения.

### Подтверждённые заключительные результаты

- Полный PG/API suite: **213 passed**, 639.89 с; JUnit errors=0/failures=0/skipped=0.
  Дополнительные два текущих F2/Qwen adapter tests — **2 passed**, 10.21 с,
  оба product/experimental профиля с synthetic transport. Исходный pinned
  reference suite не переписан и за live inference не выдаётся.
- Полный строгий Nginx browser прогон после изменений: **95 passed / 59 skipped /
  0 failed**, 6.0 мин. Дополнительно проверка позднего group response — **1 passed**.
  Skips — 55 fixture-only, 3 browser/Vite imports и отдельный no-provider сценарий.
- Полный строгий Vite browser прогон: **154 passed / 1 skipped / 0 failed**,
  8.5 мин. Включает пятый group test на поздний ответ и новые exact-state routes.
  Единственный skip — отдельный отрицательный provider сценарий.
- Отдельный Nginx сценарий с выключенным inference-разрешением — **1 passed**,
  32.1 с: failed/provider_not_configured, ai_performed=false, findings=[];
  положительные и отрицательные worker режимы не смешивались.
- Реальный stop API/worker → restart собственной PostgreSQL → start API:
  snapshot/verify точных source/finding/group/current/historical-state/Run данных
  — **PASS**, без удаления volume. Probe: scripts/check_workflow_restart.py.
- Повторный fetch 2026-11-07: все шесть origin SHA по-прежнему совпадают с таблицей.
- Ветка ещё не объединена в main. Независимое ревью не выполнено; собственный
  просмотр diff, реальные интеграционные тесты и ограничения зафиксированы явно.

## Границы результата

Сохранение материалов/документов и F1 → evidence работают из браузера через
настоящий API/PG/worker. F2/F3 сохранение/приём/очередь интегрированы, React читает
группы/conflicts/exact states и историю; public grouping start пока не утверждён.
Generation/verification и formal/bridge доступны автономно; в App не выдаются
за сохраняемые Requirement/Revision/VerificationResult. Qwen — исследовательский
комплект и synthetic transport, без реального inference/weights/GPU.

В БД добавлена только уже утверждённая M03 из backend-ветки; старые миграции
не менялись. Нового M04 нет: его проект в пакете B требует отдельного решения.
Formal exchange/storage и реальная модель/передача данных также не утверждены.
ASR/медиа, Firefox/Safari и TLS в этой интеграции не реализовывались/не проверялись.
Нет глобальных semantic KPI или фальшивых человеческих решений.

Инструкция: [WORKFLOW_INTEGRATION](../WORKFLOW_INTEGRATION.md),
снимки: [синтетическая галерея](../qa/full-workflow/index.html),
новые решения: [PROPOSED A/B/C](../proposals/workflow-contracts.md).
GitHub Actions запускаются публикацией только integration/full-workflow-ui;
фактический статус доступен по HEAD в Actions, не выводится из локальных тестов.
После локальных прогонов остановлены только сервисы feedback2req-workflow-test;
PostgreSQL volume, тестовые данные, исходные ветки и остальные окружения сохранены.

## Собственные коммиты до итогового UI

| SHA | Назначение |
|---|---|
| a36c11254a12e8eaab09a4f55a55f6d022886274 | merge исходного F1 |
| 7319b02192548c80e117741c201bb7ac5b1e5011 | исправление CI-стенда и часов |
| 539e6e061d9acf37cac4f7e34d3967f12596f695 | merge F2/F3 с сохранением решений обеих веток |
| 1b302df5d5838938fc2419eafca1f437763b7aa8 | выборочный автономный AI/Z3/Qwen import и offline CI |

## Визуальные изменения

Первый строгий visual запуск после read-only F2 закономерно обнаружил изменённую
панель групп и увеличение страницы finding. Просмотрены actual/diff desktop и
готовые 1440/320 group screenshots: изменения относятся к загруженным группам,
кнопке обновления, exact-state/позициям и тексту доступности стадий. Палитра,
навигация и бизнес-содержимое сохраняются. Разрешено обновление только связанных
findings/fragment/processing golden снимков, затем обязательный строгий прогон.
