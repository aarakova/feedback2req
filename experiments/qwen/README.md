# Qwen: локальный эксперимент group_findings

Подготовка по запросу пользователя; **не production-интеграция**.
Реальный inference ещё не выполнялся. Установка runtime/Python, загрузка весов,
изменение системной конфигурации и внешние вычисления требуют разрешения.
Флаги CLI обозначают уже полученное разрешение, сами его не предоставляют.

[Отчёт, оборудование, аудит и план 9B](REPORT.md).
Утверждённые [контракты 1.0](../../docs/AI_CONTRACTS.md) не изменены.

## Подготовленные файлы

| Файл | Назначение |
|---|---|
| [adapter.py](adapter.py) | Отдельный экспериментальный HTTP transport, настройки, идентичность модели и structured output |
| [run.py](run.py) | Opt-in CLI, watchdog, реальные ответы, диагностика и экспорт в существующий evaluator |
| [dataset.py](dataset.py) | Только синтетические входы из репозитория, применимость S01–S14, вариации |
| [prompt.py](prompt.py) | Версионированный компактный экспериментальный prompt |
| [qwen3-4b.json](qwen3-4b.json) | Qwen3-4B Q4_K_M, CPU, non-thinking |
| [qwen35-9b.json](qwen35-9b.json) | Отдельный Qwen3.5-9B Q4_K_M для согласованной GPU-машины |
| [start-ollama.ps1](start-ollama.ps1) | Отдельный локальный сервер Windows и каталог весов |
| [compose.yaml](compose.yaml) | Альтернативное изолированное CPU-serving с лимитом памяти и отключённым внешним маршрутом |
| [measure-resources.ps1](measure-resources.ps1) | Выборочные замеры дерева процессов отдельного Windows-сервера |
| [tests/test_experiment.py](tests/test_experiment.py) | Подменённый транспорт, ошибки, watchdog, схема и интеграция evaluator |

## Проверки без модели

Python 3.12, зависимости из [ai/requirements.txt](../../ai/requirements.txt).
На исследованной Windows рабочий Python в PATH не обнаружен. Следующие Python-
команды требуют рабочего интерпретатора с этими зависимостями; они **не были**
выполнены через Windows Store alias. Фактические проверки использовали уже
имеющийся Docker-образ, без установки пакетов и без сети:

```powershell
$repoPath = (Get-Location).Path
docker run --rm --pull never --network none --read-only --tmpfs /tmp:rw,size=64m,mode=1777 --cap-drop ALL --security-opt no-new-privileges --memory 512m --cpus 2 --mount "type=bind,src=$repoPath,dst=/work,readonly" --workdir /work feedback2req-checks:latest python -B -W error -m unittest discover -s experiments/qwen/tests -v
docker run --rm --pull never --network none --read-only --tmpfs /tmp:rw,size=64m,mode=1777 --memory 512m --cpus 2 --mount "type=bind,src=$repoPath,dst=/work,readonly" --workdir /work feedback2req-checks:latest python -B -m experiments.qwen.run inventory
```

Эквиваленты в готовом Python-окружении, из корня **этого worktree**:

```text
python -B -W error -m unittest discover -s experiments/qwen/tests -v
python -B -W error -m unittest discover -s ai/tests -v
python -B -W error -m unittest discover -s evals/ai/tests -v
python -B scripts/validate_ai_contracts.py
python -B -m experiments.qwen.run inventory
```

`inventory` не соединяется с Ollama. В нём 24 случая и явная применимость всех
14 сценариев. Только S05/group, S05/reordered и S06/group уже содержат запросы
group_findings. Остальные операции не преобразуются и не запускаются автоматически.
Восемь исходных grouping-контролей используются **только как входы и фокус оценки**;
их сохранённые ответы никогда не подаются в inference.

## После отдельного разрешения: Windows, первый CPU smoke

1. Предоставить рабочий Python 3.12 с зависимостями. При необходимости отдельно
   разрешить его установку и установку зависимостей. Перепроверить RAM; сейчас
   свободной памяти недостаточно. Не останавливать чужие задачи автоматически.
2. Получить Ollama **0.40.14** из [официального релиза](https://github.com/ollama/ollama/releases/tag/v0.40.14),
   сверить checksum скачанного дистрибутива с релизом. Предпочтителен переносимый
   архив в `.local/ollama-runtime`, без регистрации службы и автозапуска.
3. В отдельном терминале запустить только экспериментальный сервер:

```powershell
./experiments/qwen/start-ollama.ps1 -OllamaExe ./.local/ollama-runtime/ollama.exe -Approved
```

4. Только после разрешения загрузки весов, в другом терминале:

```powershell
$env:OLLAMA_HOST = '127.0.0.1:11435'
./.local/ollama-runtime/ollama.exe pull qwen3:4b-q4_K_M
```

CLI `pull` обращается к выделенному серверу; веса сохраняются в его
`.local/qwen-models`. Объём модели около 2,6 GB плюс runtime и служебные файлы.
Никакой команды загрузки в Python-контуре нет.

5. Зафиксировать lock и выполнить один маленький запрос:

```text
python -B -m experiments.qwen.run lock --config experiments/qwen/qwen3-4b.json --output .local/qwen-runs/qwen3-4b.lock.json --allow-local-inference --synthetic-only
python -B -m experiments.qwen.run run --config experiments/qwen/qwen3-4b.json --lock .local/qwen-runs/qwen3-4b.lock.json --output .local/qwen-runs/4b-smoke-01 --case G-compatible --allow-local-inference --synthetic-only
```

Lock содержит фактические version/digest/quantization/size и хэши model show,
шаблона и конфигурации. При изменении runtime, весов или конфигурации запуск
отклоняется. Lock не доказывает источник весов: его нужно сопоставить с явно
полученным официальным тегом и сохранить вместе с результатами. Не перезаписывать
прежний lock при сравнении; использовать новое имя и отдельную серию.

6. После технического smoke и проверки памяти — S05/S06 и полный набор:

```text
python -B -m experiments.qwen.run run --lock .local/qwen-runs/qwen3-4b.lock.json --output .local/qwen-runs/4b-s05-s06-01 --case S05-group --case S05-reordered --case S06-group --allow-local-inference --synthetic-only
python -B -m experiments.qwen.run run --lock .local/qwen-runs/qwen3-4b.lock.json --output .local/qwen-runs/4b-all-01 --allow-local-inference --synthetic-only
```

Одна попытка на случай; повтор — новая серия/каталог. Seed не гарантирует
побитовую повторяемость между runtime, устройствами и квантизациями. Для оценки
стабильности нужны несколько серий с одинаковыми условиями. Не смешивать 4B,
9B, разные prompt/context/seed или разную квантизацию в одну оценку модели.

Тайм-аут одной попытки — 180 s, бюджет серии — 900 s, включая проверку runtime.
Watchdog завершает дочерний Python; после timeout серия останавливается.
Отмена вычисления **на сервере** не гарантируется: перед следующим запуском
остановить свой выделенный Ollama через Ctrl+C и запустить заново. Остальные
случаи остаются not_attempted. Автоматических повторов нет.

## Контекст и память

8192 — экспериментальная настройка, не обещание поддержать длинные материалы.
Контур сохраняет целый запрос и применяет консервативную проверку: UTF-8 bytes
system+user, резерв шаблона 512 и output budget 1024 должны уместиться в num_ctx.
Schema передаётся в `format`, не дублируется в сообщении. Запросы, не прошедшие
проверку, отклоняются до HTTP; скрытого сокращения/разбиения нет. Это оценка
для штатного Qwen-шаблона, не измерение токенизатором. Проверить фактический
template/hash и prompt_eval_count в smoke; произвольные пользовательские шаблоны
не поддержаны. Ответ с `done_reason != stop` отклоняется целиком, включая length.
При нехватке output/context — новая конфигурация/lock/серия, без ремонта ответа.

Уменьшение num_ctx до 4096 может отклонить даже маленький запрос с полной
инструкцией. Прежняя рекомендация 2–4k из MODEL_SELECTION не означает, что
весь текущий prompt+вход+выход туда помещается. Для будущей экономии памяти
можно отдельно исследовать более короткий prompt и KV-квантизацию; здесь они
не включены автоматически.

В Windows нет жёсткого лимита RSS процесса; ограничены контекст, output,
параллелизм, потоки и время клиента. Для жёсткого ограничения памяти применять
контейнер на машине с достаточной RAM. Не увеличивать WSL/Docker RAM без согласования.

## Альтернатива: контейнер serving

Подготовленный compose **не запускался**. Нужны заранее согласованные/загруженные
образ Ollama и веса. Serving имеет внутреннюю Docker-сеть, read-only веса,
порт только на host loopback, CPU=4, memory+swap=5 GiB, pids=128, без restart.
Текущая Docker VM имеет 3,30 GiB и для этого варианта не подходит.

```text
docker compose -f experiments/qwen/compose.yaml --project-name f2r-qwen config --quiet
docker compose -f experiments/qwen/compose.yaml --project-name f2r-qwen up -d
docker compose -f experiments/qwen/compose.yaml --project-name f2r-qwen ps
```

`pull_policy: never` исключает неявную загрузку образа. Веса предварительно
получать только после разрешения; сервер с `internal: true` их не скачивает.
Для Linux/Docker runner использовать **network namespace этого контейнера**,
тогда фиксированный `127.0.0.1:11435` доступен без изменения кода/контрактов:

```powershell
$repoPath = (Get-Location).Path
$serverId = docker compose -f experiments/qwen/compose.yaml --project-name f2r-qwen ps -q ollama
# Создать ignored output root до bind mount.
New-Item -ItemType Directory -Force .local/qwen-runs | Out-Null
docker run --rm --pull never --network "container:$serverId" --read-only --tmpfs /tmp:rw,size=64m,mode=1777 --memory 512m --cpus 1 --mount "type=bind,src=$repoPath,dst=/work,readonly" --mount "type=bind,src=$repoPath/.local/qwen-runs,dst=/work/.local/qwen-runs" --workdir /work feedback2req-checks:latest python -B -m experiments.qwen.run lock --output .local/qwen-runs/container.lock.json --allow-local-inference --synthetic-only
```

Для `run` использовать тот же контейнерный вызов, заменив аргументы Python на
smoke-команду выше с нужным lock. На другом компьютере тестового образа может
не быть: заранее согласовать создание окружения с Python 3.12 и зависимостями.
Идентификатор образа serving сохранить через `docker image inspect`, фактическую
память/CPU — через `docker stats --no-stream <serverId>` до/во время/после запуска.
Это выборочные замеры, не точный peak. Завершение только своей среды:

```text
docker compose -f experiments/qwen/compose.yaml --project-name f2r-qwen down
```

## Результаты и содержательная оценка

Все результаты только под ignored `.local/qwen-runs/<new-name>`.
Существующие каталоги и файлы не перезаписываются. Git-ignore не является
шифрованием или системой контроля доступа; контур предназначен только для
синтетических материалов. Не переносить сюда реальные отзывы.

- `metadata.json`: модель/digest/runtime, полная конфигурация, prompt/schema/code
  и dataset hashes, зависимости, назначенные примеры, применимость сценариев,
  явно отсутствующие измерения ресурсов.
- `dataset.json`: точные синтетические запросы и предварительная разметка.
- `responses/*.envelope.bin`: фактические полученные байты, включая HTTP error,
  доступную часть IncompleteRead и повреждённый JSON. При превышении byte cap
  сохраняется только ограниченный префикс cap+1; остаток не считывается.
  При разрыве сокета/timeout до завершённого read полученные внутри transport
  неполные байты могут быть недоступны; это не выдаётся за сохранённый ответ.
- `responses/*.json`: content без исправления, если удалось выделить строку.
  Некорректные Unicode-surrogate сохраняются как невалидные UTF-8 bytes;
  исходный HTTP envelope остаётся основным точным свидетельством.
- `*.diagnostics.json`: checkpoint после каждой попытки; `diagnostics.json` —
  отдельная сводка, ошибки, schema/application states, duration и Ollama metrics.
  attempt_failure_rate имеет знаменатель всех выполненных попыток, включая
  локальный отказ по context budget. confirmed_http_attempts и unknown_http_attempts
  отдельно показывают, для каких попыток начало HTTP известно; это не число
  доказанно завершённых inference. Неназначенные/not_attempted не входят в rate.
  Ollama duration — ns, counts — tokens; wall duration — ms и включает startup
  изолированного процесса, а также локальную валидацию.
- `expert-review.json`: отдельные листы оценки с hash ответа, pending-вердиктами,
  исходным фокусом, связями permutation/paraphrase. По
  [REVIEW](../../evals/ai/REVIEW.md) эксперт указывает met/not_met/uncertain/
  not_applicable и основания. Автоматического балла, ранжирования и порога нет.
  Для технического отказа status=technical_failure: содержательный вердикт не
  вычисляется, даже если часть content доступна для диагностики.
- `saved-model-responses.json` и `source-evaluation/`: совместимый экспорт только
  трёх исходных S05/S06 примеров, отчёт и экспертный шаблон существующего evaluator.
  Остальные 43 примера исходного набора считаются неназначенными, а не успешными.
  Ошибки envelope/generation экспортируются как технический failed, даже если
  частичный content похож на валидный канонический JSON.

Структурные и прикладные ошибки — разные стадии. Валидный JSON, ссылки и
заявленный coverage не доказывают смысл, достаточность оснований и полноту чтения.
Контекст synthetic не проверяет права или актуальность настоящего приложения.
Сравнивать группы и позиции по finding keys, не по local_id, порядку или точной
формулировке. Допустимы альтернативные обоснованные группировки. Предварительная
разметка не превращается в окончательный gold при заполнении листов.

Для Windows sampling во время отдельного smoke, в третьем терминале:

```powershell
$serverProcess = (Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 11435 -State Listen).OwningProcess
./experiments/qwen/measure-resources.ps1 -ServerProcessId $serverProcess -Seconds 180 -Output "$PWD/.local/qwen-runs/4b-smoke-01/resources.jsonl"
```

Каталог smoke должен уже существовать; начало sampling фиксируется временем,
оно может пропустить раннюю загрузку. Файл не подключается к сводке автоматически:
прикладывать его к соответствующей серии и явно описывать интервал. Сумма RSS
может повторно учитывать shared pages; CPU-суммы не являются точным total при
перезапусках дочерних процессов. VRAM не измеряется этим скриптом. При отсутствии
sampling поля peak RSS/VRAM/CPU остаются `null`, не нулём и не размером весов.

## Будущие операции

CLI поддерживает только group_findings. Повторно используемые границы уже
выделены: LocalHTTP, watchdog/bounded_job, version/weight lock, exclusive writer,
metadata и независимые review artifacts. Для каждой следующей операции добавить
отдельные prompt, loader применимых synthetic cases и execute/validation adapter;
зарегистрировать явный CLI-выбор только после готовности/разрешения соответствующего
модуля. При этом переиспользовать transport и измерения, а не F1 worker.
extract_feedback сохраняет свой atomic segment; generate/verify используют свои
утверждённые схемы и прикладные инварианты. Общий transport не объединяет роли.
Нет зависимости от незавершённых generate_requirements, Z3 или F2, нет нового API.
