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
- [ ] Воспроизвести CI 42263266660; исправить стенд/часы; build и полный Nginx F1.
- [ ] Интеграция F2/F3, PG/API/migration tests, worker synthetic checks.
- [ ] React read-only groups/conflicts/exact states и интеграционные browser tests.
- [ ] Автономные generation/verification/Z3/bridge/Qwen, unit/eval проверки.
- [ ] Конкретные пакеты согласования: grouping POST; Requirement/Revision/checks;
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
