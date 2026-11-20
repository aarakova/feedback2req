# Готовность публичного запуска группировки — 2026-11-21

Задача: продолжить F2/F3, проверить пакет A и существующие согласования;
подготовить окончательный контракт до отдельного утверждения, не включать
несогласованный POST. Пользователь отдельно запретил push, merge в main и
внешние AI-вызовы. Этот отчёт не расширяет согласования.

## База и уже выполненная работа

Проверены ветки и рабочие деревья; preview/workspace a866b4e не содержит полного
интеграционного результата и не используется для новой работы.
Проверенные удалённые SHA (read-only ls-remote, 2026-11-21):

| Ветка | SHA | Назначение |
|---|---|---|
| main | 410b936e451629a53ca1eb0fb15a4908961155b6 | Общая AI foundation, не полный Observer workflow |
| integration/full-workflow-ui | 600065626be5e671223c8a8afd696a14bb4c20e5 | Согласованная INT база с F1/F2/F3 и чтением групп |
| feat/backend-grouping-orchestration | be328080cbeb484b3e2b77866709775627884d98 | Готовые internal enqueue/worker и предложение POST A.1 |

Новая локальная ветка feat/backend-grouping-public-contract и отдельное worktree
созданы **от 6000656**, без переноса чужих незакоммиченных изменений. Исходные
ветки/рабочие деревья, контейнеры и БД не изменялись. Удалённых изменений нет.
Для создания своей git ref/worktree использовано обычное tool approval, поскольку
sandbox не разрешил запись в .git; защиты/политики не отключались.

DEC-016 разрешил F2 storage/read/приём, поправка от 2026-11-06 — annotations
на явно переданные previous_groups. DEC-017 разрешил внутреннюю очередь F3.
INT-2026-11-06 разрешил интеграцию готовых компонентов и **явно не утвердил**
POST group_findings. Пакет A в integration HEAD по-прежнему PROPOSED. Другого
утверждения публичного запуска в проверенном журнале нет.

## Выполнено в этой ветке

- Пакет A сверен с кодом интеграционной базы и оформлен как
  [окончательная редакция 2](grouping-run-api-proposed.md), всё ещё PROPOSED.
- Уточнены closed DTO/types/bounds, snapshot 202/COMMIT, default arrays, UUID/
  order canonicalization, replay после смены states и привязка к initiator.
- Зафиксирован transaction-aware стык с уже проверенным Actor/Tx: нельзя открывать
  вложенную сессию с повторной auth, когда внешняя транзакция обновляет last_seen.
  Это риск, выявленный статически; PG-воспроизведение в этой работе не выполнялось.
- [Frontend handoff](../proposals/grouping-launch-frontend.md) содержит точные
  ошибки, pending/same-key recovery, терминальные states и 27 сценариев приёмки.
- [JSON-примеры](../proposals/grouping-launch-examples.json) показывают request,
  queued Run, completed без групп с questions/ungrouped/coverage, provider failure
  и безопасный envelope неизвестного исхода. Все UUID и данные синтетические.
- Пакет A/B/C ссылается на A.2; части B/C сохранены без изменений.

Runtime handler/DTO и storage/queue не реализовывались заново. После отдельного
утверждения A.2 требуется только HTTP-стык с существующей подготовкой, не новый
Run lifecycle, endpoint чтения или provider. Current POST остаётся F1-only.

## Проверки этой подготовки

PASS, 2026-11-21, встроенные read-only команды PowerShell/Git, собственные fixtures:

- JSON синтаксис, UUID записей, точность selected states в queued input,
  coverage/input mapping и ungrouped refs в completed без групп.
- Точная previous-group ссылка вопроса, synthetic/ai_performed, отсутствие
  принятого coverage при provider_not_configured и согласованность X-Request-ID.
- 27 отдельных строк сценариев A01–A27 и 12 локальных Markdown targets.
- Публичный Start.operation в проверенном исходнике по-прежнему F1-only.
  Это статическая проверка source gate, не выполненный HTTP-тест.
- Части B/C сравнены с 6000656 и побайтно совпадают после нормализации CRLF/LF.
- git diff --check; runtime/backend/frontend/AI contracts не изменены.

Эти проверки подтверждают согласованность подготовленных артефактов, не работу
будущего POST. Политики запуска скриптов не отключались; отдельный ps1 checker
не включён в результат. Данные примеров не относятся к существующей базе.

NOT RUN: PostgreSQL/API/worker/browser приёмка нового POST (A01–A27) и регрессии
F1/F2/F3 в этой итерации. Контракт ещё не утверждён, runtime не менялся; прежние
прогоны F3/интеграции не объявляются новыми результатами. В текущем окружении
Docker CLI не найден, root .venv ссылается на отсутствующий Python312 другого
пользователя. Зависимости, execution policy и чужие тестовые стенды не изменялись.
Независимое ревью и реальные AI-вызовы NOT RUN.

## Зависимости и следующий шаг

Для реализации нужно одно явное решение: утверждение пакета A редакции 2,
включая HTTP shape/types/limits, transaction snapshot, deferred provider failure
и отсутствие TTL/retry/cancel. Для synthetic приёмки не нужны B/C, генерация
требований или реальная модель. Не решённые B/C не являются разрешением их менять.

После утверждения: transaction-aware reuse enqueue → discriminated POST DTO с
сохранением F1 → изолированные PG/HTTP проверки матрицы и неизвестного COMMIT →
handoff для отдельного подключения frontend. Synthetic отмечается явно;
Qwen/model/передача данных требуют собственного решения. Push/merge по-прежнему
запрещены текущим заданием.
