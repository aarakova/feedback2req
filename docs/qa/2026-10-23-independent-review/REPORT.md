# Независимая проверка веток feedback2req

Дата: 2026-10-23. Проверка и новые тесты выполнены без изменения приложения,
моделей, миграций, AI-контрактов, существующих тестов и общих workflow.
Во время проверки ветки не объединялись; commit/push не выполнялись.
После проверки пользователь отдельно разрешил сохранить, закоммитить и
опубликовать результаты. Сведения о публикации приведены ниже; merge не выполнялся.

**Результат:** два новых MEDIUM-дефекта автономного валидатора evals;
новых дефектов реализованного Access не установлено. AUD-01/AUD-03 сохраняются;
AUD-02 сохраняется в workflow main/Access/И2б. Созданы 14 дополнительных обычных
тестов и 9 opt-in регрессий известных дефектов. Все обычные тесты прошли;
все 9 регрессий падают по проверяемой причине и не включены в обязательный набор.

## A. Проверенные версии и среда

Локальные HEAD и remote HEAD, прочитанные через GitHub API, совпали с заданием.
Исходные рабочие каталоги всех агентов были чистыми. Работа шла в отдельных
checkout зафиксированных SHA; исходные каталоги агентов не переключались.

| Ветка | SHA | Изменения от merge-base с main | Выполненные проверки | Результат |
|---|---|---|---|---|
| main | 6c01d8113a40eb514e180453ec8e4ae1d8679b6e | Проверенная baseline предыдущего аудита | Статическая сверка AUD, чтение текущего CI; прежний аудит того же SHA отдельно | READY WITH NOTES |
| agents/ai-feedback2req-testing-preparation | 800d9fb157a5e7109f1a0af2cdc0041f65ea6177 | merge-base 3ab6af02cb634fb3f8fae49ff4571ab61eff713c; 32 новых файла evals/ai, 22008 строк | 47 исходных + 8 новых unittest; 4 отдельные регрессии; CLI, 24 faults, генератор, Ruff, контрактный валидатор | FIXES REQUIRED |
| agents/pasted-text-processing-adf660ee | 9084a58aefb5c5efd9668bf5df36c12872aeb574 | merge-base main 6c01d811; 12 файлов, 902 вставки/14 удалений; DEC-012 Access | 40 исходных + 6 новых Playwright через Vite; 46 через Nginx; build/tsc; 11 API/PG; AUD-регрессии | READY WITH NOTES |
| agents/pasted-text-processing | 766ac01174ac44fda92f68d948f57e22c2666d5c | merge-base main 6c01d811; только I2B_SPEC.md, +479/-47, ревизия 3 | Статическая проверка границ, diff, трассировка будущих тестов; 44-строчная предварительная матрица | READY WITH NOTES — только документ |

Evals основана на **старой** версии приложения до DEC-011. Она не содержит
четырёхсервисного deployment и не является автоматически объединённой с main.
Содержательно новая часть ветки ограничена evals/ai. Access и И2б основаны на main.

Тестовые ветки и checkout:

- `test/ai-evals-review`: [тестовый коммит](https://github.com/aarakova/feedback2req/commit/7f9fca437b8c11b51b21d7f4452833a1adebf705), родитель 800d9fb.
- `test/frontend-access-review`: [тестовый коммит](https://github.com/aarakova/feedback2req/commit/8a904fa25a21691c4ecc234b8afaa89a2c51575d), родитель 9084a58.
- [И2б, исходная ревизия](https://github.com/aarakova/feedback2req/tree/766ac01174ac44fda92f68d948f57e22c2666d5c): detached review checkout 766ac01, без изменений.

Первоначально тесты и пояснения оставлены untracked/uncommitted согласно
объёму проверки. По следующей команде пользователя они сохранены в двух
указанных коммитах. Этот отчёт, план, предварительная матрица, CI-предложение
и диагностические replay-артефакты сохраняются отдельно в ветке
`test/independent-qa-results`, основанной на проверенном main 6c01d811.
Отслеживаемые файлы main и исходные ветки агентов не менялись.

Источники: AGENTS.md, PLANS.md, README; действующие DEC, REQUIREMENTS, DOMAIN,
ARCHITECTURE, DATA_MODEL, API, TESTING, AI_CONTRACTS, AI_VALIDATION; diff каждой
ветки; evals README/PLAN/REVIEW/VALIDATION, генератор/runner/checks/CLI/фикстуры;
DEC-012 и документация Access; вся ревизия 3 И2б. Неутверждённая разметка и
спецификация не использовались как новые утверждённые продуктовые контракты.

Среда проверки: существующие immutable образы, без изменения общих tags:

| Назначение | Image ID |
|---|---|
| Python checks | sha256:0c154beef3fd4f49181dafba8fabc4f4c3211aa2110e4c966bf686cdc23b9379 |
| Node/Playwright | sha256:e28af1eeac386eb41e655ccd9e5375badeb1db97701d87869e5921326494eeaa |
| PostgreSQL 17 | sha256:b8faeff7712663c2773a190181e1246e37e364b887611c04658c28b44e2408fe |
| Nginx runtime | sha256:0c0ac87751b92d771037fb54012fd1379e0600c136f64175d5533a040d2a4c78 |

Python 3.12.15/jsonschema 4.26.0/referencing 0.37.0/Ruff 0.17.1; Node 24.22.1,
Playwright 1.64.1, Chromium; Vite 8.3.5. PostgreSQL — только собственный временный
контейнер `f2r-qa-292c-pg`, данные в tmpfs, без host-портов и volumes. API и
браузер разделяли его изолированный network namespace. Миграции/тесты создавали
свои уникальные схемы в feedback2req_qa_test. Исходники монтировались read-only;
браузерные копии и кэши — в tmpfs. Изоляция evals дополнительно network=none.

## B. Матрица покрытия

| Требование / инвариант | Существующий тест | Новый тест | Статус | Пробел |
|---|---|---|---|---|
| S01–S14, 46 examples, preliminary/semantic_gold=false | test_inventory_annotations_and_traceability; revised_versions | Нет дублирования | PASS | Экспертная разметка остаётся предварительной |
| Все 24 faults и неизменность | test_each_intentional_fault_detected_and_source_unchanged | Отдельная сверка по case/example/attempt, не по порядку zip | 24/24 PASS | Не доказывает полноту классов ошибок |
| Неизвестные поля без утечек и исправления | test_invalid_response_is_not_repaired... | nested_unknown_field... | PASS | Новые допустимые структуры потребуют своих границ |
| Глобальная уникальность input/output идентификаторов | faults + общие проверки | input_keys...; output_ids... | PASS | — |
| Unicode/code points, цитаты и вхождения | unicode_exact_second_occurrence; overlapping... | non_bmp_locator... | PASS | previous_fragments: QA-AI-01 |
| Безопасность response_file и привязки эксперта | response_file_cannot_escape...; expert binding | symlink escape; changed_external_response_bytes... | PASS | Защита от злоумышленной одновременной замены файлов не оценивалась |
| Метаданные/версии/no overwrite | CLI/version/compare tests | boolean metadata; schema drift/comparison preservation | PASS | Не тест реального провайдера |
| Coverage и согласованность outputs | completed_group...; partial_found...; faults | not_processed_verification... (opt-in) | FAIL, QA-AI-02 | issues обходят проверку отсутствия review |
| Предыдущий контекст и основания | history/comparison snapshot tests | Три previous_fragment... (opt-in) | FAIL, QA-AI-01 | Ни один исходный dataset example не содержит previous_fragments |
| Owner/Member/Approver/outsider, Owner immutable | access.spec.ts; backend projects/security | Нет дублирования | PASS | Реальные ограничения API остаются |
| Все страницы Access и повтор загрузки | cursor/reload; duplicate ID beyond first page | failed_middle_page... | PASS | Нет атомарного snapshot всего списка между страницами |
| UUID ввода | invalid IDs в access.spec.ts | UUID spelling... | PASS | — |
| Гонки до и после preflight | concurrent_removal_before...; permissions_changed... | removal_after_preflight...; concurrent_add_after_absence... | PASS | API PUT остаётся upsert без версии; это явно раскрыто DEC-012 |
| Неопределённая запись и сверка | lost PUT/DELETE; focus during PUT | failed_reconciliation...; committed_late_add... | PASS | Текущее состояние не доказывает прошлый исход |
| Поздние ответы, clipboard, Back/Forward, клавиатура/390 px | 22 исходных Access сценария | Не дублируются; новые комбинации выше | PASS | Не полный аудит доступности, не Firefox/Safari |
| Клиентская ошибка строк И1 | Старые security/identity тесты | 4 AUD-01 регрессии | FAIL ожидаемо | Унаследованный дефект |
| Unicode-пароль без обрезания | Короткие пароли в старых браузерных тестах | AUD-03 opt-in | FAIL ожидаемо | Унаследованный дефект |
| Код завершения конечного worker | Old-schema refusal в backend; detached deployment | Отдельный предложенный worker gate | Контроль 0→0, инъекция 17→1 | Общий workflow не исправлен |

## C. Подтверждённые дефекты

### QA-AI-01 — MEDIUM: previous_fragments обходят проверки trusted-содержимого

Ветка/SHA: evals, 800d9fb. Код:
[checks.py:177](https://github.com/aarakova/feedback2req/blob/7f9fca437b8c11b51b21d7f4452833a1adebf705/evals/ai/checks.py#L177).
См. также approved AI_CONTRACTS §7.1 (previous_fragments), AP-02/AP-04/AP-05.

Условия: корректный extract-запрос с previous_findings и previous_fragments,
существующими StateRef в trusted и точной исходной цитатой. Такой контекст
разрешён существующим контрактом. Независимая фикстура сначала проходит
check_request без ошибок; она не меняет dataset и не добавляет новое правило.

Воспроизведение: в корректном контексте отдельно изменить (1) quote на
WRONG-QUOTE, (2) locator на [9999,10000), (3) reliability с usable на uncertain
при неизменном trusted. Запустить три opt-in регрессии.

Факт: в каждом случае check_request возвращает `[]`, хотя структура остаётся
валидной, а исходное trusted-соответствие нарушено. Цикл рассматривает только
segments + fragments; previous_fragments используются позднее для наличия
evidence, но их содержимое не проверяется аналогичным образом.

Ожидание: диагностическое отклонение неверной цитаты/координат и надёжности
существующими кодами LOCATOR-OR-TEXT / RELIABILITY-MISMATCH. Последствие —
некорректный предыдущий контекст может быть принят как диагностически чистый.
Это дефект автономной проверки, не доказанный обход прикладного приёма AI.

Исправление: после отдельного разрешения распространить применимые проверки
trusted-текста/источника/координат/надёжности/времени на previous_fragments.
Три регрессии сейчас падают; production-код не изменён.

### QA-AI-02 — MEDIUM: содержательные issues принимаются для not_processed

Ветка/SHA: evals, 800d9fb. Код:
[checks.py:473](https://github.com/aarakova/feedback2req/blob/7f9fca437b8c11b51b21d7f4452833a1adebf705/evals/ai/checks.py#L473),
[обработка issues:484](https://github.com/aarakova/feedback2req/blob/7f9fca437b8c11b51b21d7f4452833a1adebf705/evals/ai/checks.py#L484).
Основания: AI_CONTRACTS §6/§7.4, AP-07 и согласованность содержательной проверки.

Воспроизведение: взять S06/verify с настоящим issue, установить coverage target
в reviewed=false / not_processed с reason; очистить considered_keys четырёх
checks, оставив issues_found и issue. Структура и ссылки остаются валидными.

Факт: check_response возвращает пустую диагностику. RESULT-FROM-UNREVIEWED
проверяется только при непустом considered_keys; сам содержательный issue эту
проверку не вызывает. Ожидание: такой противоречивый ответ должен получить
диагностику, поскольку цель заявлена полностью нерассмотренной. Это проверяемое
несоответствие метаданных результата, не экспертная оценка его смысла.

Исправление: после разрешения явно связать возможность содержательных выводов
и issues с рассмотрением target, сохраняя допустимый пустой/inconclusive исход.
Независимая регрессия сейчас падает на `errors == []`.

### AUD-01 — MEDIUM, остаётся: строки И1 дают 500

Общие файлы во всех четырёх SHA идентичны для соответствующей валидации:
[schemas.py:11](https://github.com/aarakova/feedback2req/blob/8a904fa25a21691c4ecc234b8afaa89a2c51575d/backend/feedback2req/api/schemas.py#L11),
[ProjectName:20](https://github.com/aarakova/feedback2req/blob/8a904fa25a21691c4ecc234b8afaa89a2c51575d/backend/feedback2req/api/schemas.py#L20),
[Identity:45](https://github.com/aarakova/feedback2req/blob/8a904fa25a21691c4ecc234b8afaa89a2c51575d/backend/feedback2req/identity/service.py#L45).

На Access SHA с реальной PG повторены NUL в названии при POST/PATCH и surrogate
пароля при register/login, переданные escaped JSON. Все четыре возвращают
500 internal_error вместо контролируемой 422. Privacy/request_id/rollback
assertions до проверки статуса проходят: секретов/SQL/traceback в ответе нет,
неудачное создание не оставляет проект, PATCH сохраняет старое имя.

Исправление ранее предложено: проверять сохраняемость названия и корректность
Unicode пароля до PostgreSQL/Argon2, без нормализации/обрезания паролей. Здесь
только добавлены независимые регрессии, вне backend/tests.

### AUD-02 — MEDIUM, остаётся: detached deployment не проверяет worker exit

main/Access/И2б наследуют неизменённый
[workflow:73](https://github.com/aarakova/feedback2req/blob/8a904fa25a21691c4ecc234b8afaa89a2c51575d/.github/workflows/i1.yml#L73).
`up -d` и ожидание backend/frontend не являются проверкой результата конечного
worker. В старой evals-ветке deployment/worker DEC-011 вообще отсутствуют:
там замечание неприменимо к текущему workflow, но важно при будущей интеграции.

Независимая инъекция: собственный конечный worker завершается кодом 17.
Detached Compose возвращает 0; предложенный явный gate читает State.ExitCode
и возвращает 1. Контрольный worker exit 0 даёт gate exit 0. Оба случая реально
выполнены, контейнеры удалены по проверенному уникальному project label.

Это доказывает способность предложенного отрицательного теста падать по причине
неуспешного worker. Не заявляется, что текущий worker штатно падает. Исправление
общего workflow только предложено, требует отдельного согласования.

### AUD-03 — LOW, остаётся: HTML maxlength обрезает допустимый пароль

Во всех ветках одинаковое
[поле AuthForm:63](https://github.com/aarakova/feedback2req/blob/8a904fa25a21691c4ecc234b8afaa89a2c51575d/frontend/src/AuthForm.tsx#L63).
Регрессия на настоящем приложении: API принимает пароль 500 X + 300 🧭
(800 code points / 1100 UTF-16 units). Browser keyboard.insertText в поле
maxlength=1024 оставляет 762 code points. Регрессия падает через Vite и Nginx.

Ожидание: допустимый пароль целиком сохраняется в поле и позволяет войти.
Предложение: согласованная проверка code points с явной ошибкой вместо
молчаливого обрезания; здесь пользовательские/серверные лимиты не менялись.
Отдельная конфигурация исключает этот failing test из обычного Playwright.

## D. Новые тесты и фактические результаты

| Новый файл | Назначение | Фактический итог |
|---|---|---|
| [test_independent_review.py](https://github.com/aarakova/feedback2req/blob/7f9fca437b8c11b51b21d7f4452833a1adebf705/evals/ai/tests/test_independent_review.py) | 8 независимых границ/привязок/Unicode/privacy | 8 PASS; полный объединённый suite 55 PASS, 23.499 s |
| [test_known_defects.py](https://github.com/aarakova/feedback2req/blob/7f9fca437b8c11b51b21d7f4452833a1adebf705/evals/ai/regressions/test_known_defects.py) | 3 прежних фрагмента + unreviewed verification | 4 FAIL ожидаемо; не основной набор |
| [access-independent.spec.ts](https://github.com/aarakova/feedback2req/blob/8a904fa25a21691c4ecc234b8afaa89a2c51575d/frontend/tests/access-independent.spec.ts) | 6 новых сочетаний Access, реальные серверные записи | 6 PASS через Vite, затем все 46 PASS через Nginx |
| [test_audit_input.py](https://github.com/aarakova/feedback2req/blob/8a904fa25a21691c4ecc234b8afaa89a2c51575d/backend/regressions/test_audit_input.py) | 4 контролируемых ошибки AUD-01, privacy/rollback | 4 FAIL ожидаемо; status 500 вместо 422 |
| [password-unicode.spec.ts](https://github.com/aarakova/feedback2req/blob/8a904fa25a21691c4ecc234b8afaa89a2c51575d/frontend/regressions/password-unicode.spec.ts) | AUD-03, реальная вставка текста | 1 FAIL ожидаемо, 762 вместо 800 |
| [playwright.regressions.config.ts](https://github.com/aarakova/feedback2req/blob/8a904fa25a21691c4ecc234b8afaa89a2c51575d/frontend/playwright.regressions.config.ts) | Явный opt-in directory regressions | Не изменяет обычный testDir tests |

Ни один старый тест не изменён. Нет skip/xfail, замены ожидаемого поведения,
моков PostgreSQL или фиктивных положительных AI-эталонов. В Access HTTP-перехваты
использовались только для транспортных отказов/задержек; конкурирующие операции
выполнялись второй настоящей серверной сессией. Две гонки после preflight
намеренно подтверждают согласованное ограничение upsert, не объявляя его багом.

Команды выполнялись внутри описанных read-only/container окружений:

```text
python -B -W error -m unittest discover -s evals/ai/tests -v
python -B -W error -m unittest discover -s evals/ai/regressions -v
python -B evals/ai/cli.py validate-dataset
python -B evals/ai/build_dataset.py
python -B scripts/validate_ai_contracts.py
python -B -m ruff check --no-cache evals/ai
python -B -m ruff format --no-cache --check evals/ai
python -B -m pytest -p no:cacheprovider backend/tests/test_projects.py backend/tests/test_security.py -q -W error
python -B -m pytest -p no:cacheprovider backend/regressions/test_audit_input.py -q -W error
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vite/bin/vite.js build --outDir /qa-output/dist
playwright test --reporter=line
playwright test tests/access-independent.spec.ts --reporter=line
playwright test --config=playwright.regressions.config.ts --reporter=line
```

Первый `playwright test` — исходные 40 через Vite; targeted — новые 6 через
Vite; финальный `playwright test` — 46 через Nginx. Совпадение кода приложения
обеспечено сборкой из frozen Access worktree с его lockfile и имеющимися теми же
зависимостями контейнера; npm install не выполнялся. Проверка tsc/build — PASS.
Backend projects/security: **11 PASS с -W error**. Новый backend regression
отдельно прошёл Ruff check/format; evals целиком — Ruff PASS, 11 Python-файлов
форматированы. Изменялись форматтером только два собственных новых файла.

Nginx проверен в частной топологии: собранный из SHA frontend → настоящий
Nginx → API → PostgreSQL, с namespace-local upstream 127.0.0.1:18000 и test-only
relay на localhost:18080. Политика замены заголовков сохранена. Это не новый
прогон исходного Compose DNS/spoofing/restart; эти свойства подтверждены текущим
CI и не выдаются за повторно проверенные здесь. Общий Compose не менялся.

Неуспешные подготовительные попытки также учтены: native Python отсутствует;
первый Node -e вызов пострадал от Windows quoting; первый Vite запуск не смог
создать кэш в read-only node_modules. Использованы stdin и частные tmpfs-кэши,
затем тесты прошли. Первое format --check показало форматирование двух новых
Python-файлов; исправлено только их форматирование. Windows ExecutionPolicy
не позволила запустить worker gate через -File; проверенное тело выполнено inline
в текущем PowerShell без изменения политики. Эти ошибки окружения не скрыты
и не классифицируются как дефекты приложения.

## E. AI evaluation harness

Подтверждены 14 сценариев S01–S14, 46 примеров, набор 1.1.0, разметка 0.2.0.
Проверены все синтетические исходные тексты/предлагаемые смыслы/альтернативы и
роли фикстур. Реальных материалов или секретов в просмотренных данных нет;
вымышленный продукт — «Задачник». Backend/PostgreSQL/provider imports отсутствуют.

Генератор без --write воспроизводит **22 артефакта**. Dataset SHA256:
`6926cb777854891d20727d868036e0e5fcfb0956952bf4e2ef566e224ea6169d`.
Исходные файлы не исправлялись; read-only mount и чистый tracked diff исключают
незаметную починку fixtures в этой проверке.

CLI validate-dataset/replay/compare/no-overwrite реально проверены:

- controls: 46 records, 46 pending expert forms, exit **0**;
- faults: 24 records, ожидаемые нарушения, exit **1**;
- compare сопоставимых отчётов: exit **0**;
- повтор записи в существующий comparison directory: exit **2**, прежний файл сохранён;
- несовместимые версии/request/tool/schema, пути, дубли JSON и nonfinite значения
  проверены существующими и новыми тестами; CLI tool/input error не выдаётся за успех.

[Все 24 результата с ожидаемым и фактическими кодами](evals-results/FAULT_RESULTS.md)
сверены отдельной проверкой по case/example/attempt. Это не только повтор zip
из авторского теста. [Controls](evals-results/controls/report.md),
[faults](evals-results/faults/report.md), [comparison](evals-results/comparison/comparison.md)
сохранены отдельно от исходного набора.

Два пропуска валидатора описаны в C. Чистая диагностика остальных примеров не
доказывает семантическую корректность. Три intentional_semantic_error сохранены
(S09 missed-unsupported/false-positive, S11 irrelevant-evidence), semantic_gold=false,
итогового балла/рейтинга/precision/recall нет; uncertain не превращается в met.
Все исходные экспертные записи остаются pending/preliminary, AI-модели не вызывались.

Ручная оценка нужна для полноты смысла, поддержки каждой части S03/S12,
direct/inferred, конфликтов, ложных срабатываний, severity/scope и устойчивости
перефразирования. S06 покрывает только конфликтующие позиции; независимое
продолжение при смысловом конфликте не проверено, S10 проверяет технический сбой.

Дополнительный риск оператора: apply_expert допускает вручную выставить met даже
в записи outcome=failed; это не автоматическое присвоение качества и не снимает
preliminary. Полезен отдельный согласованный guard экспертной формы для
неприменимых содержательных критериев. В обязательные требования/новые failing
tests такое усиление здесь не внесено.

## F. Frontend Access

Утверждённый DEC-012 объём подтверждён: вкладка Owner-only, UUID/Clipboard,
все страницы, добавление и отдельное изменение Approver, подтверждение удаления,
Owner immutable, ошибки, текущая сессия, очистка после потери доступа, навигация.
Проверены настоящие API-гарантии Owner/Member/Approver/outsider, 401/403/404,
Origin/CSRF; права не выводились только из кнопок.

Конкурентность проверена по обе стороны preflight:

- Изменение/удаление до preflight обнаруживаются без PUT (исходные тесты).
- Удаление после preflight допускает восстановление через PUT; concurrent add
  может заменить Approver. Новые тесты проверяют предупреждения, одну запись
  и фактическое состояние во второй сессии. Это ограничение API прямо согласовано.
- Потерянный ответ не даёт ложного успеха/автоповтора; ошибочная сверка оставляет
  неопределённость и ввод, успешная сверка показывает только текущее состояние.
- Поздний ответ уже сохранённого добавления не возвращает старый UI после
  смены проекта. Исходные задержанные GET/logout/user/focus также проходят.

Новых подтверждённых дефектов Access не найдено. Ограничения: нет условного
membership write/version; список между страницами не атомарен; полный аудит
доступности/Firefox/Safari/native Node/TLS не выполнялся. Базовые AUD-01/03 и
CI AUD-02 не исправлены этой feature-веткой.

## G. CI

Проверены текущие exact-SHA runs и jobs/steps:

| Ветка | Run | Что подтверждено |
|---|---|---|
| main | [39958839314](https://github.com/aarakova/feedback2req/actions/runs/39958839314) | i1/deployment success |
| evals | [39995098523](https://github.com/aarakova/feedback2req/actions/runs/39995098523) | Только i1 success, НЕ evals tests |
| Access | [39994169920](https://github.com/aarakova/feedback2req/actions/runs/39994169920) | i1/deployment success, оба полных browser steps |
| И2б | [40000547178](https://github.com/aarakova/feedback2req/actions/runs/40000547178) | Existing application i1/deployment; не будущий worker |

На момент проверки новые независимые тесты **не запускались GitHub Actions**:
их публикация разрешена позднее. Результаты Actions для новых тестовых коммитов
этот отчёт не заявляет. Исходные 22 Access-теста находятся в committed tests/
и входят в полный Playwright соответствующего SHA. Новые 47 evals-тестов при
зелёном CI своей ветки не выполняются вовсе.

[Минимальное предложение CI и разделение тяжёлых/ручных проверок](CI_PROPOSAL.md)
подготовлено для согласования. Для evals достаточно добавить unittest discovery,
генератор без --write и Ruff check/format, используя уже совпадающие зависимости
i1. CLI/24 faults проверяются unittest с точными ожидаемыми кодами, без `|| true`.
Изменение общего workflow и включение failing regressions требуют согласования.

## H. Предварительная матрица И2б

[Отдельная матрица из 44 сценариев](I2B_TEST_MATRIX.md) содержит для каждого
инвариант, входные условия/данные, ожидаемый исход, уровень, необходимость PG
и управление временем/процессами/отказами. Покрыты start/idempotency/refs,
inspect_text/Unicode, DDL/изоляция, claims/lock/fencing, права, heartbeat/lease,
COMMIT uncertainty/reconciliation, recovery, timeouts, watchdog/init/pidfd,
SIGTERM/restart, однократность результата и сохранение независимых результатов.

Все строки PROVISIONAL / NOT IMPLEMENTED / NOT RUN. Очередь, миграции, worker,
новые endpoints и их исполняемые тесты не создавались. Документ ревизии 3
сохраняет PROPOSED; его согласование само по себе не разрешает реализацию.

## I. Готовность и следующие действия

| Ветка | Статус | Основание и граница |
|---|---|---|
| main | READY WITH NOTES | Известные AUD-01–03 сохраняются, новых оснований объявлять всю baseline непригодной не получено |
| AI evals | FIXES REQUIRED | QA-AI-01/02 дают ложную чистую диагностику; перед интеграцией исправить checker по отдельной команде, затем включить регрессии; CI добавлять согласованно |
| Frontend Access | READY WITH NOTES | Проверенный DEC-012 объём работает через Vite/Nginx и реальную PG; базовые AUD и ограничения API перечислены |
| И2б, ревизия 3 | READY WITH NOTES — только документация | Готова к содержательному рассмотрению как PROPOSED; runtime-готовность не оценивалась и не заявляется |

Не объединять ветки автоматически. Сначала отдельно рассмотреть исправления
двух evals-checker дефектов и CI-предложение; разметку согласовать содержательно.
Access может рассматриваться независимо от evals и И2б. Исправления production
и общих workflow требуют отдельного разрешения, их здесь нет.

Независимость — относительно авторов реализации; новые тесты написаны одним
SDET в этой сессии, второго рецензента новых тестов не было. Green checks
подтверждают только указанную среду/сценарии, не отсутствие всех ошибок.

## Завершение и ограничения

Оригинальные worktree/HEAD и отслеживаемые файлы не менялись. Общие Docker tags,
рабочий PostgreSQL volume и три работавших контейнера не изменялись и не
останавливались. Все собственные временные контейнеры остановлены и удалены;
пользовательские volumes не удалялись. Финальная проверка подтвердила прежние
ID трёх рабочих healthy-контейнеров, чистый main и исходные worktree агентов,
чистый detached spec checkout и отсутствие tracked diff в тестовых worktree.
План проверки обновлён; 44 строки матрицы дополнительно пересчитаны.
