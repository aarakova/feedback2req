# Проверка автономного адаптера group_findings → Z3

Дата: **2026-11-06**. База после `git fetch origin`:
`feat/formal-expectation-checks`, `cc8c62a9dc620092b2579597fbaab99d751abd88`.
Собственная ветка `feat/formal-expectations-bridge` и отдельный worktree.
F2 `4c62684` изучен через `git show` только для определения границы; его код,
Qwen и генерация не объединялись. Исходный Z3-компонент не изменён.

## Окружение и воспроизведение

Python **3.12.15**, native Z3/z3-solver **4.15.4.0**, jsonschema **4.26.0**,
referencing **0.37.0**, Ruff **0.11.13**. Новых production-зависимостей нет.
Requirements адаптера ссылаются на прежние автономные requirements.

На хосте отсутствует работающий Python launcher. Использован имеющийся image
`sha256:0c154beef3fd4f49181dafba8fabc4f4c3211aa2110e4c966bf686cdc23b9379`.
Прежний изолированный formal-venv подключён **только readonly**, не изменён.
Python образа предоставляет jsonschema/referencing, PYTHONPATH добавляет
закреплённые Z3/Ruff из venv. Исходники readonly; сеть отключена; временные
файлы тестов остаются в одноразовом контейнере. Пример PowerShell:

```powershell
$bridgeRoot = (Get-Location).Path
$formalEnv = 'C:/Users/Admin/PythonProjects/feedback2req/.local/worktrees/formal-expectation-checks/.local/formal-venv'
$checkImage = 'sha256:0c154beef3fd4f49181dafba8fabc4f4c3211aa2110e4c966bf686cdc23b9379'
docker run --rm --network none --mount "type=bind,source=$bridgeRoot,target=/workspace,readonly" --mount "type=bind,source=$formalEnv,target=/env,readonly" --env PYTHONPATH=/env/lib/python3.12/site-packages:/workspace --workdir /workspace --entrypoint python $checkImage -B -W error -m unittest discover -s ai/formal_expectations_bridge/tests -v
```

Аналогично выполнены регрессии с `-s ai/formal_expectations/tests` и `-s ai/tests`,
а также `python -B scripts/validate_ai_contracts.py`. Ruff запускался через
`/env/bin/ruff` с теми же readonly mounts:

```text
ruff check --no-cache ai/formal_expectations_bridge ai/formal_expectations ai/group_findings ai/tests
ruff format --no-cache --check ai/formal_expectations_bridge ai/formal_expectations ai/group_findings ai/tests
```

Переносимый запуск в собственном venv и CLI — в [README](README.md).

## Результаты

| Проверка | Итог |
|---|---|
| Новый адаптер | **27 tests passed**, `-W error` |
| Все прежние formal_expectations tests | **33 tests passed**, `-W error` |
| Регрессия group_findings | **37 tests passed**, `-W error` |
| Ruff check | PASS |
| Ruff format --check | PASS, 27 Python-файлов |
| Валидатор AI 1.0 | PASS: 9 схем/88 local refs; 38 позитивных/34 негативных примера; 399 unknown-field mutations; 20 fixture pairs |
| Неизменность старого кода/контрактов | `git diff <base> --exit-code` — PASS |
| Diff/staged diff whitespace | PASS |

Итого **97 unit/regression tests**, warnings не подавлялись. Генераторы
детерминированы; прежние fixed-seed тесты Z3 выполнены без изменений.
Проверены отсутствие diff в `backend/`, `ai/formal_expectations/`,
`ai/group_findings/`, `ai/tests/`, `docs/contracts/ai/`, AI_CONTRACTS.md,
AGENT_ARCHITECTURE.md, REQUIREMENTS.md, API.md и DATA_MODEL.md относительно базы.
Новая запись DEC фиксирует только область поручения; PROPOSED не утверждён.

## Объём проверки

- **19 русскоязычных сценариев** покрывают все 13 обязательных тем и
  дополнительные отказы. Для тройки сохранены три отдельные пары. В
  [cases.json](examples/cases.json) — тексты, подготовка, ожидаемый класс
  структуры/исход адаптера, основания, ограничения и синтетические fault controls.
- [expert-review.json](examples/expert-review.json) хранится отдельно:
  PRELIMINARY/pending, не semantic gold. Эти метки не управляют verifier/Z3.
- D/K/S/U получены через прежний Z3. Пропуск формализации, неполный контекст,
  неполное/неподтверждённо полное Ω не дают класса. Исторические Finding states
  не подменяются текущими; версии, Fragment/source/text states и evidence
  сохраняются. Чужое/удалённое/uncertain основание отвергается.
- Несколько находок позиции не сокращаются до первой молча. Разложение одной
  находки на атомы сохраняет источники и непроверенные атомы. Выбор возможен
  и при отсутствии конфликта LLM. Три попарных S не становятся глобальным итогом.
- Проверены противоречивые/неразрешённые context relations, разные объекты,
  параметры, типы/размерности, недопустимые зависимости A от C.
- Ошибочная solver-валидная формализация породила бы ложный K/D: отрицательные
  trusted confirmations блокируют analyze. Известные части не меняются в Ω;
  AI complete=true с усечённым списком не проходит trusted completeness.
- Квитанция должна поступить от явно назначенного callable и соответствовать
  hash всего packet. Dict/True/иной snapshot/не-bool/нет обоснования отклоняются;
  callback получает копию. Вход не может задать себе verification.
- Unknown/timeout инъецированы, реально выполнен Z3 rlimit=1: остаются
  техническими отказами с classification=null. Вредоносный Python не исполняется.
- CLI prepare проверен подпроцессом на временном файле: только подготовка,
  без formal_result. Demo K/U и негативное Ω проверяют synthetic=true и exit 0/2.

## Ревью и исправления

Независимый reviewer прочитал реализацию, tests, README и PROPOSED-документ.
Найден **P2**: первоначальный synthetic_verifier принимал произвольный case
как контрольный снимок. Исправлено: только зарегистрированный ID, снимок и
подтверждения берутся из внутреннего authoritative каталога. Подмена input
при прежнем ID блокируется, внешние confirmations не принимаются. Негативные
тесты добавлены; reviewer повторно проверил исправление.

Пропущенный при добавлении test helper импорт Verification обнаружен Ruff/reviewer
и восстановлен до итоговых тестов. Первоначальные замечания Ruff к стилю и
замыканию переменной цикла исправлены. Format на readonly mount сначала не
смог создать cache; повтор с `--no-cache` прошёл. Других существенных замечаний
reviewer не обнаружил. Ревью — независимое чтение кода, **не независимый прогон**
tests/Ruff; итоговый отчёт и SHA reviewer не проверял.

## Неисполненное и границы

Production verifier отсутствует: реальные права, доступность и состояние БД,
соответствие смысла тексту автономный пакет не подтверждает. SHA связывает
данные, но не доказывает авторство/истинность/полноту мира. Перед будущей
публикацией необходима повторная проверка актуальности и прав.

Время внешнего callback и OS-изоляция native-кода — обязанность вызывающего
кода; Limits ограничивают подготовленный JSON и прежний solver по отдельности.
Backend/F2/worker/API/БД/frontend не менялись, их интеграционные тесты не
запускались. Реальная LLM не вызывалась. Прямой приём backend GroupDetail
не реализован: нужны согласованные state mapping и lifecycle.
Статья остаётся недоступной; полный опубликованный метод не сверялся.

Следующие решения и гибридный эксперимент описаны в
[PROPOSED](../../docs/proposals/formal-expectations-results.md) и [README](README.md).
