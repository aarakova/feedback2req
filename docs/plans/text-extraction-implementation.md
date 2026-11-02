# Первый сквозной extract_feedback

2026-10-26–2026-11-02. IMPLEMENTED / VALIDATION INCOMPLETE. Основание — поручение «первый сквозной
сценарий содержательной обработки» с самостоятельным проектированием необходимых
API/миграций/worker и логическими коммитами. Это заменяет прежние ограничения
на реализацию технического И2б в пределах нового сценария, но не утверждает rev3.

## План и границы

1. Сохранить аудит и зафиксировать разрешение/техническую дельту.
2. Добавить очередь, exact inputs, попытки, fragments/findings и атомарный приём.
3. Добавить API start/list/get/retry/results и O1.
4. Добавить сменный provider, программный приём AI 1.0, worker и Compose.
5. Выполнить unit/API/PostgreSQL и изолированные Docker/fault/restart проверки.
6. Зафиксировать контракты frontend, результаты и оставшиеся ограничения.

Не входят: группы, требования, человеческие правки, ASR, удаление, semantic
dashboard, изменение AI 1.0, merge/push, реальные внешние/платные AI-вызовы.
Для последних отдельно запрошены provider/model/условия. Тестовый provider
допустим только в тестовом окружении, результаты помечаются synthetic.

## Компактный контур вместо И2б rev3

Один run содержит 1–32 независимые units, каждая фиксирует целый source text
state как один атомарный сегмент extract (documents пока не передаются).
Отдельный inspect_text не является обязательным предшественником semantic
операции: он остаётся поддерживаемой технической операцией, без AI.
Каждая unit имеет одну попытку, retry создаёт новый run/unit, не переписывает
историю. Claim и publication сериализованы Project→unit→attempt. Failed только
ручной retry; queued переживает restart, потерянный running после expiry failed.

Worker-контейнер имеет один supervisor-процесс и не более одного дочернего
исполнителя. Весь проход БД/claim/provider/accept исполняется в дочернем процессе,
который supervisor ограничивает абсолютным wall-clock budget. Это даёт
ограничение зависшего client I/O независимо от GIL дочернего исполнителя.
Heartbeat отдельным коротким соединением продлевает lease только до абсолютного
deadline попытки; вычисление/HTTP не держат SQL транзакцию. Parent не пишет БД.
При потере COMMIT подтверждения child не пересчитывает/не повторяет публикацию:
завершается; committed completed читается как completed, иначе running истекает.
Это консервативное отличие от in-process reconciliation rev3, сохраняющее
однократную публикацию ценой ручного retry неопубликованной попытки.

Healthcheck отслеживает фиксированный срок очередного прохода supervisor.
Сигнал допустим только по целой записи под lock с проверенной PID/start identity
через pidfd; отсутствие/повреждение записи — unhealthy без небезопасного kill.
Временная недоступность БД сама по себе не разрешает сигнал: дочерний проход
завершается с безопасной ошибкой и следующий начинается с backoff.
Целевые условия: Linux containers, init=true, supervisor — прямой ребёнок PID1,
Python 3.12 и pidfd/flock. Нет shell-обёртки или remap аварийного exit в0.
После превышения опубликованного срока probe сигналит через pidfd только при
валидной полной записи, правильных PID/start/parent/entrypoint и удержанном flock.
Неисправный канал наблюдения остаётся unhealthy и может требовать оператора;
unhealthy сам по себе не перезапускает контейнер. Restart policy on-failure
не обещает автозапуск после перезапуска Engine; manual stop также подавляет restart.
Ранний отказ и start_period не разрешают опасный сигнал по отсутствующей записи.
Реальная цепочка probe→137→RestartCount пока не подтверждена.

SQL: connect 3 s, lock 2 s, statement 5 s, transaction 8 s; attempt deadline
120 s, lease 30 s, heartbeat 5 s; provider socket timeout ≤60 s;
supervisor pass ≤135 s. Socket timeout не общий wall-clock предел HTTP:
медленный поток дополнительно ограничен процессным сроком; deadline БД
в любом случае запрещает просроченную публикацию.
Таким образом короткий SQL budget не ограничивает нормальный AI-вызов 10 s.
Процессный hard limit не продлевается heartbeat. Нативный запуск без supervisor
не обещает принудительное восстановление зависшего дочернего процесса.

## Проверки

Имеющиеся 71 тест — baseline, не проверка новой функции. Новые проверки должны
покрывать ссылочную целостность, точный Unicode/quote/occurrence, AP-01–08/11/13,
empty success/invalid response, безопасные ошибки, idempotency/retry races,
expiry/revocation/stale inputs, runtime/provider failures, restart persistence.
26 октября Docker Engine 29.9.2 был доступен. Использовались только собственные
уникальные контейнеры/network/volume, без общих опубликованных портов/рабочей БД.

## Реализованная дельта и контракты

- Одна frozen Alembic m02b: шесть таблиц runs/units/attempts/fragments/findings/
  finding_evidence. Технические числа и accepted coverage/annotations хранятся
  в attempt вместо отдельной technical_results rev3. Старые миграции не менялись.
- Неизменяемые начальные findings/fragments: state_id=id; human write API
  не реализован. Поздний AI не может перезаписать правку человека; последующий
  human срез потребует явного механизма истории, а не UPDATE существующих строк.
- Реализованы [HTTP-контракты](../TEXT_PROCESSING_API.md): O1, start/list/get runs,
  retry units, list/detail findings, exact fragment states. Обычные cookie/Origin/
  CSRF и права сохранены. GET run/findings кратко блокируют Project для
  согласованного read без смешивания промежуточного принятия; это простое
  решение для MVP, возможен contention большого списка на проекте.
- O1 считает только заголовки одним SELECT, без текстов. Processing теперь
  available с latest_run_id; semantic_metrics относится к ещё не готовой полной
  аналитике, а реальные findings читаются отдельным API.
- Ollama adapter сменяется через provider interface extract(request), name,
  model, synthetic; worker по умолчанию использует Ollama, fake production
  fallback отсутствует. Полные approved JSON Schema используются локально при
  приёме и передаются провайдеру self-contained. Изменений AI-контрактов нет.
- Передача выключена до явного операционного разрешения. Не было реальных
  пользовательских или платных AI-вызовов. ai_performed допускает null для
  неподтверждённого выполнения. Все полученные в Docker-тестах находки synthetic.
- Логические коммиты: 1f88b09 — исходный scope/аудит; e300a76 — данные, приём,
  adapter/API/тесты; 93013bc — supervisor/Compose/CI и fault harness. Они локальные,
  push и merge не выполнялись. Отдельный diagnostic worker-check сохранён и
  явно сообщает, что сам задания не исполняет.

## Фактические проверки и ограничения

26 октября, Python3.12/PostgreSQL17/Docker29.9.2, собственные ресурсы
f2r-extract-20261026-* и Compose project f2r-extract-e2e-20261026:

| Проверка | Результат и граница |
|---|---|
| Исходные тесты после добавления m02b | 67 passed, 4 failed: старые ожидания набора таблиц/head и resource warning при аварии Alembic. Ожидания расширены до новой схемы, engine.dispose перенесён в finally без ослабления проверки rollback |
| Новый API/PG extract набор, ранний прогон | 15 passed; настоящий PostgreSQL, synthetic provider |
| Полный набор после адресных исправлений | 90 passed, -W error, 93.03 s. Это снимок 26 октября, до последних изменений end(token), nullable ai_performed и self-contained provider schema |
| Ruff backend | PASS 26 октября на предшествующем снимке; для окончательных изменений нужен повтор |
| AI validator | PASS: 9 схем, 38 positive/34 negative, 399 mutations, 20 offline pairs; не смысловая оценка AI |
| Сборка runtime image | PASS; последний тогда image53ee92d392a1, включает SQL end(token)/nullable ai_performed, до нового schema bundle/probe-integrity guard |
| Docker HTTP seed | PASS: реальный API→queue→worker→synthetic HTTP provider→validated fragments/findings в PG |
| Stop/start API/worker + restart PG | PASS: сессия, точный текст/ID/state_id, run, finding и exact evidence сохранены |
| Ошибка provider и ручной retry | PASS: provider_error, нет новых findings, replay одного ключа возвращает тот же retry |
| Нормальная compute 35 s | PASS: completed с heartbeat, RestartCount=0, worker healthy; десятисекундный SQL budget не применён к compute |
| Полный GitHub workflow | Не запускался удалённо; новый extraction job добавлен, не объявлен прошедшим |
| SIGSTOP/probe/restart и corruption guard | Инструментарий добавлен, но запуск не завершён. Первая попытка пересоздания своего стенда остановлена до любых изменений из-за ошибки quoting label template в PowerShell |

2 ноября при продолжении Docker Engine недоступен: pipe dockerDesktopLinuxEngine
отсутствует; native python — WindowsApps stub. Рабочие Docker/БД других агентов
не запускались/не останавливались. Пользователю сообщено, что для завершения
проверок нужен запущенный Engine. Новые локальные проверки без Engine:
Compose extraction config успешно разобран, общих host ports нет, synthetic
marker включён только в отдельном стенде; git diff --check и ссылки/JSON
контракта прошли. После восстановления Engine необходимы:

1. Ruff/format и полный pytest на окончательном снимке, включая новые provider
   gate/schema/JSON и malformed snapshot tests (они пока не выполнялись).
2. Новая disposable БД с окончательной frozen m02b; повторить seed/restart/failure/slow.
   Прежний тестовый стенд содержит более раннюю m02b и не доказывает её финальный DDL.
3. Реально выполнить corrupt/hang probe tests, проверить ненулевой exit/init,
   RestartCount/новую process identity/ready. Временную недоступность PG при
   живом worker, running/queued recovery после убийства и hard child timeout
   также проверить в Docker; сейчас полная эта матрица не подтверждена.
4. Native поддержка не заявляется; отдельный restart Engine/ранние startup
   сбои/сильные сетевые fault-injection и семантическое качество модели не проверены.

Независимое ревью текущего кода не выполнено. Исходная ревизия3 И2б не менялась.
Изолированные test containers/volumes пока не очищены: при недоступном Engine
невозможно подтвердить их текущее состояние. Очистка после проверки точных
labels/имён — только ресурсов перечисленных test проектов.

## Возобновление изолированных проверок

Из корня, после сборки feedback2req-backend и feedback2req-checks:

```text
docker compose -f compose.extraction-test.yaml -p <new-disposable-project> up -d --wait db api provider worker
docker compose -f compose.extraction-test.yaml -p <new-disposable-project> run --rm checks seed
docker compose -f compose.extraction-test.yaml -p <new-disposable-project> exec -T worker python /checks/probe.py corrupt
docker compose -f compose.extraction-test.yaml -p <new-disposable-project> exec -T worker python /checks/probe.py hang
```

Дождаться увеличения RestartCount и healthy, выполнить checks verify; затем
остановить api/worker, перезапустить только db этого проекта, поднять api/worker,
повторить checks verify, checks failure и checks slow. Полная последовательность
также записана в extraction job [workflow](../../.github/workflows/i1.yml).
Не использовать рабочий Compose project/volume или чужой Docker Engine для fault tests.
