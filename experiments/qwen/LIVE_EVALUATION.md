# Qwen live evaluation и совместимость с F2

Итерация 2026-11-06. **Настоящий inference пока не выполнен.** Нет модельных
ответов, установленного weight digest или содержательных результатов сравнения.
Технические прогоны ниже используют явно synthetic transport, не Qwen.
Qwen3.5-9B остаётся основной исследовательской моделью; 4B — отдельный baseline.

## Проверенная база

После `git fetch origin` подтверждены точные удалённые HEAD:

- собственная база `experiment/qwen-group-findings`:
  `c03d34310efd5c92a29450a2d6d06dc87d64fb9c`;
- F2 `feat/backend-finding-groups`:
  `4c62684e7769d2c3a71de3264aa15e954a1262d0`.

Созданы отдельные ветка `experiment/qwen-live-evaluation` и worktree.
F2 изучен через `git show` и собственный ignored `git archive` snapshot
`.local/f2-reference`; чужой checkout не менялся, backend не объединялся.
Его [API](https://github.com/aarakova/feedback2req/blob/4c62684e7769d2c3a71de3264aa15e954a1262d0/docs/FINDING_GROUPS_API.md),
[execution](https://github.com/aarakova/feedback2req/blob/4c62684e7769d2c3a71de3264aa15e954a1262d0/backend/feedback2req/grouping/execution.py),
[validation](https://github.com/aarakova/feedback2req/blob/4c62684e7769d2c3a71de3264aa15e954a1262d0/backend/feedback2req/grouping/validation.py)
и [отчёт интеграции](https://github.com/aarakova/feedback2req/blob/4c62684e7769d2c3a71de3264aa15e954a1262d0/docs/plans/grouping-component-integration.md)
используются без изменений. [Hash manifest](f2-reference.json) проверяет восемь
файлов reference, включая схемы, перед собственными PG-тестами.

JSON Schema group_findings 1.0, standalone service/validation и source prompts
не изменены. Исполнение/приём/хранение групп повторно не реализованы: используется
готовый `execute_grouping` и его prepare/verifier/heartbeat/accept/fail.
Production worker, публичные команды, API, чужие ветки, Z3 и генерация требований
не подключались и не менялись.

## Ресурсы и конкретный блокер

Windows 11 Pro, Ryzen 7 3700U (4/8), 6,94 GiB RAM. Свободно 0,68 GiB в начале
итерации, около 0,53 GiB при повторной проверке после возобновления. Docker Linux
VM располагает 3,30 GiB. Radeon Vega 10 `AdapterRAM=1 GiB` не доказывает доступную
вычислительную VRAM; работа ускорителя с Ollama не подтверждена. Рабочего native
Python в PATH и установленного Ollama не подтверждено. Runtime и веса не
устанавливались/не скачивались. 9B на этой конфигурации не запускалась.

Использованная среда проверки: существующий `feedback2req-checks:latest`,
Python 3.12.15, jsonschema 4.26.0, referencing 0.37.0; image ID
`sha256:0c154beef3fd4f49181dafba8fabc4f4c3211aa2110e4c966bf686cdc23b9379`.
Проверочные контейнеры ограничены 1–2 CPU и 256–512 MiB, source read-only,
`/tmp` tmpfs. PostgreSQL использует отдельную внутреннюю сеть
`f2r-qwen-live-test`, контейнер `f2r-qwen-live-test-db`, БД `qwen_live_test`,
память 256 MiB и временное хранилище 128 MiB. Порт PG наружу не публикуется.
Чужие контейнеры/volumes не останавливались и не удалялись.

Изучены официальные условия бесплатных вариантов:

| Среда | Проверенные условия | Что фактически доступно этой сессии |
|---|---|---|
| [Google Colab](https://research.google.com/colaboratory/faq.html) | Free compute ограничен динамически: конкретные GPU, квоты и срок сессии не гарантированы; free notebook может работать до 12 часов в зависимости от доступности. Выбирать интерактивный GPU notebook, без публичного serving/tunnel | При открытии браузера — Sign in и 401, runtime не выделен. GPU, свободная память и личная квота не измерены. Аккаунт не создавался |
| [Hugging Face ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu) | Текущая страница: 48 GiB default GPU slice; 2 min/day anonymous, 5 min/day free account. Hosting free Space требует подходящего аккаунта (verified email, возраст >30 дней). Совместим с Gradio/PyTorch, не обычным Ollama daemon | Подходящий аккаунт/квота/конкретный Space с контролируемыми весами не подтверждены. Это не готовая замена существующему Ollama harness; ничего не развёрнуто |
| [Kaggle Notebooks](https://www.kaggle.com/docs/efficient-gpu-usage) | Документация описывает бесплатный P100 и недельную GPU-квоту 30h либо выше в зависимости от спроса. Фактическое устройство/память/квоту нужно смотреть в runtime | Авторизация и статус аккаунта не проверены, GPU не выделен. Регистрация, проверка телефона/личности не выполнялись |

Платные ресурсы и API не создавались, никакой synthetic bundle не передавался
наружу. Бесплатность, разрешение пользователя и достаточная память — отдельные
условия. Наличие публичной страницы сервиса не означает доступ к GPU.

**Минимальные действия пользователя:** выбрать существующую отдельную машину
либо лично войти в бесплатный Colab, выбрать бесплатный GPU и получить реальный
runtime; отдельно разрешить установку task-local runtime/зависимостей, загрузку
Qwen3.5-9B и передачу только synthetic bundle. Если интерфейс требует оплаты или
нежелательной верификации — остановиться. Аккаунты/секреты/доступ к Drive не нужны
комплекту. До этих действий настоящий запуск остаётся заблокирован.

## Переносимый комплект

[Notebook](Qwen35-Free-GPU.ipynb), [bootstrap](bootstrap_cloud.py),
[stdlib preflight/bundler/matrix](portable.py) используют существующий harness.
Notebook сохранён без outputs, разрешения по умолчанию False. Создание bundle,
inventory, matrix и открытие notebook не запускают модель.

В готовом Python+Git окружении, из корня этого worktree после commit:

```text
python -B -m experiments.qwen.portable preflight
python -B -m experiments.qwen.portable matrix --output .local/qwen-runs/matrix-matched
python -B -m experiments.qwen.portable matrix --sampler recommended --output .local/qwen-runs/matrix-recommended
python -B -m experiments.qwen.portable bundle --output .local/qwen-runs/qwen-live-bundle.zip
```

На текущей Windows Python доступен через уже имеющийся Docker image, но Git
внутри этого image отсутствует. Эквивалентная упаковка без установки Python:

```powershell
New-Item -ItemType Directory -Force .local/qwen-runs | Out-Null
$revision = git rev-parse HEAD
git archive --format=zip --output=.local/qwen-runs/qwen-source.zip HEAD -- experiments ai evals/ai docs/contracts/ai docs/AI_CONTRACTS.md docs/AI_VALIDATION.md docs/REQUIREMENTS.md scripts/validate_ai_contracts.py
$repoPath = (Get-Location).Path
docker run --rm --pull never --network none --read-only --tmpfs /tmp:rw,size=64m,mode=1777 --memory 512m --cpus 2 --mount "type=bind,src=$repoPath,dst=/work,readonly" --mount "type=bind,src=$repoPath/.local/qwen-runs,dst=/work/.local/qwen-runs" --workdir /work feedback2req-checks:latest python -B -m experiments.qwen.portable seal --archive .local/qwen-runs/qwen-source.zip --revision $revision --output .local/qwen-runs/qwen-live-bundle.zip
```

Имена файлов должны быть свободны; не перезаписывать предыдущую серию. `seal`
предполагает, что source ZIP действительно создан показанным git archive из
чистого согласованного commit: он сверяет Git ZIP commit comment с revision,
проверяет пути/состав и сохраняет SHA исходного архива. Comment не является
подписью Git-объектов; в image без Git независимая проверка происхождения
не заявляется. Manifest явно указывает этот способ проверки. `bundle`
проверяет чистоту source paths и экспортирует напрямую из Git. Комплект содержит
только выбранные committed code/docs и synthetic fixtures; `.local`, env,
веса, аккаунтные файлы, рабочая БД и чужой backend в него не входят.
Manifest содержит revision и SHA-256 каждого файла, sidecar — SHA-256 ZIP.

После отдельного разрешения: открыть notebook в выбранном free runtime, явно
разрешить upload, загрузить **только** bundle и вписать проверенный ZIP SHA-256.
Preflight требует фактически свободных GPU ≥10 GiB, host RAM ≥8 GiB, disk ≥16 GiB.
Доступная RAM ограничивается также cgroup memory limit/current, если они
измеримы: host MemAvailable не подменяет лимит контейнера. Bootstrap выбирает
конкретный индекс GPU с достаточной free VRAM через CUDA_VISIBLE_DEVICES.
Это консервативные provisioning gates для Q4, не измеренные минимумы модели.
В CPU-варианте 9B gate требует свободных ≥16 GiB RAM; cloud bootstrap принимает
только GPU. Не путать total/free VRAM и shared RAM. Проверить поддерживаемый
драйвер отдельно: успешный preflight не доказывает CUDA/model совместимость.

Bootstrap устанавливает зависимости только в `.local/cloud-runtime/python-deps`,
получает официальный Linux x86_64 Ollama 0.40.14 archive (1 525 335 029 bytes),
проверяет SHA-256
`993e83d08c3d13d17c55009a3e2664c8a25445e644aec3a68bef5abb6abce67d`
из [официального релиза](https://github.com/ollama/ollama/releases/tag/v0.40.14)
и распаковывает с data filter. Службы/системные пакеты не устанавливает.
Этот путь пока не испытывался с настоящим runtime; его успешность не заявлена.

Занятый порт отклоняется до установки и запуска. Перед pull/сериями проверяется,
что собственный живой PID владеет listening socket через Linux /proc; готовый
чужой daemon не используется. Если /proc не даёт проверить владельца — отказ.
Сервер слушает только 127.0.0.1:11435, cloud mode выключен, параллелизм/model
count=1. Только после разрешения загружается `qwen3.5:9b-q4_K_M` (~6,6 GB package).
Затем выполняются D/K/S/U для product и experimental с matched sampler. После
тайм-аута следующая серия не начинается. Сервер останавливается в finally.
Notebook экспортирует только `.local/qwen-runs`, без весов/runtime; free VM
эфемерна, поэтому скачать результаты до отключения. Детальные процессы/GPU peaks
пока не инструментированы на Linux: соответствующие поля остаются null;
preflight — отдельный снимок ресурсов, не peak model RSS/VRAM.

## Модели, промпты и матрица

Точные **планируемые** теги: `qwen3.5:9b-q4_K_M`, необязательный
`qwen3:4b-q4_K_M`; runtime pin 0.40.14. Установленные weight digests отсутствуют,
поскольку загрузки/запуски не было. Будущие lock получают фактические `/api/tags`
и `/api/show`, quantization, size, version/template hashes, config hash и теперь
также prompt profile/version/hash. Старые lock предыдущего adapter version
нельзя подменять новыми; использовать новые имена. Adapter version теперь 2.

Prompt hash использует тот же canonical-JSON SHA-256 helper, что и request hash,
не SHA raw исходного файла. Зафиксированные значения:
product `c7df7c3de0e1576032d76536452913f158ffd03f80f80571efbd70f582dc7987`,
experimental `1057419ad25c9206d9c0d443e1c5398480b6698b000e80f82b19dbc12ad72cb7`.
Dataset hash 34 случаев:
`f7d097fc289ecc2c0dc22819f8c9fafa068bf93f9217430e89e71a690bb36c5d`;
исходный S01–S14 hash не изменён:
`6926cb777854891d20727d868036e0e5fcfb0956952bf4e2ef566e224ea6169d`.

[profiles.py](profiles.py) выбирает неизменённый
[product prompt](../../ai/group_findings/prompt.py) либо неизменённый
[experimental prompt](prompt.py). Product version `group-findings-1.0.0`,
experimental `qwen-group-findings-experiment-1`; схема и JSON user одинаковы.
Payload-тест проверяет product текст побайтово через строку и отсутствие
переписывания request. Полный product prompt длиннее, поэтому для матрицы обеим
моделям/обоим prompt задан num_ctx=16384; скрытого урезания или упрощения нет.

`matched`: temperature=.7, top_p=.8, top_k=20, min_p=0, seed=42,
presence_penalty=0, repeat_penalty=1, think=false, num_predict=1024,
num_thread=4, num_gpu=99, timeout=90 s для всех четырёх конфигураций.
`recommended`: та же база, но 9B presence_penalty=1.5/repeat_penalty=1,
у 4B эти override отсутствуют, как в исходных конфигурациях. Для этой матрицы
нельзя приписывать отличие только размеру модели: sampler и model defaults
тоже различаются. Дополнительные веса 4B не скачиваются автоматически.

В inventory теперь 34 случая: прежние 24 + D-conflict/K-conditions/S-compatible/
U-insufficient, D-independent, U-injection и 4 обратных перестановки.
Названия D/K/S/U — экспериментальные labels: отдельного именованного набора с
такими ID в базе не найдено; исходные grouping cases и S01–S14 не переименованы.
Все новые review expectations preliminary. Сохраняются смысловые перефразы и
исходные S05/group, S05/reordered, S06/group. Остальные операции S01–S14
не запускаются автоматически и не объявляются проверенными на модели.

Реальные ответы должны сохраняться прежним [run.py](run.py): raw envelope/content,
request/prompt/schema/code/dataset hashes, digest/quantization/runtime, sampling,
wall duration и Ollama token/timing counters; schema и application diagnostics
отдельны от экспертных листов. Для технического failed смысловой вердикт не
вычисляется. Сравнивать permutation/paraphrase по meaning/membership/positions,
не по ID/порядку. Реального сравнения двух prompt/моделей пока **нет**.

## Проверенная граница F2

Собственные [PG tests](f2_checks/test_f2_path.py) прогоняют оба prompt через
настоящий adapter payload и подменённый transport, затем неизменённый standalone
компонент, F2 execution/приём, реальную БД и GET через in-process TestClient.
Wrapper имеет `synthetic=True, model=none`; сохранённый ai_performed=False.
Это проверка инженерной совместимости, не результат Qwen и не публичный API.

Проверены две разные группы с пересечением, две позиции конфликта, ungrouped,
coverage/questions/uncertainties, оба annotation-типа на явно переданную прежнюю
группу, exact state/source refs и исторический GET после смены current state.
При неизвестном члене, повторной позиции, fragment annotation target или NUL
во второй группе — failed/invalid_response и **ноль** опубликованных групп.

Границы валидаторов различаются, хотя схема одна:

- F2 ограничивает local IDs 256 символами, строки 32768 и запрещает NUL/
  невалидный UTF-8; standalone структурный приём сам по себе не доказывает это.
- F2 не принимает одинаковые conflict positions (description+finding set).
- Related для обоих annotation-типов в F2 — только выбранные input findings/
  previous_groups или output groups. Standalone допускает более широкий scope
  uncertainties. Нельзя автоматически подрезать/переназначать ссылки для приёма.
- Обе стороны принимают completed+ungrouped без выдуманной reason; прежние
  группы являются контекстом, не целью перезаписи. Exact typed refs берутся из
  сохранённого F2 request, а не создаются моделью.

[F2LocalProvider](f2_provider.py) — только opt-in экспериментальный provider для
готового execute_grouping, без production-регистрации. Identity/lock проверяется
**до** F2 prepare. Timeout ≤90 s оставляет запас относительно F2 deadline 120 s;
lease 30 s продлевает уже существующий heartbeat. Старый 180 s cfg не принимается.
Внутри group сохраняются точный F2 request, response, hashes и технический исход
до независимого финального приёма. Ответ не ремонтируется и не перепривязывается.

Отказ, доказанно случившийся до HTTP, отображается как provider_not_configured
(ai_performed=False в F2); точная причина остаётся в отдельной diagnostics.
При timeout/смерти дочернего процесса неизвестно, началось ли server compute.
Поэтому backend ai_performed сам по себе не доказывает inference: сверять
request_attempted/provider_completed и сохранённый фактический envelope. Схемы
и реализация provenance F2 не менялись.

Для будущего настоящего полного пути есть [отдельный live test](f2_checks/test_live.py).
По умолчанию он пропущен. Нужны одобренные runtime/веса, достаточные ресурсы,
пиннутый F2 reference и отдельный PostgreSQL, доступные тестовому Python.
Настроить F2R_QWEN_CONFIG/LOCK/OUTPUT и F2R_TEST_DATABASE_URL, затем явно
F2R_QWEN_LIVE=approved-synthetic. TestClient остаётся внутри процесса.
Colab notebook **не устанавливает PostgreSQL и не выполняет этот тест**; без
такой среды реальный F2 end-to-end остаётся NOT RUN. Нельзя импортировать
сохранённый ответ на другой request как новый real inference.

## Повторяемые проверки

Source mount — собственный worktree; F2 mount — отдельный exact git archive.
Создание тестового стенда использовало уже имеющийся postgres:17 image:

```text
docker network create --internal f2r-qwen-live-test
docker run -d --pull never --name f2r-qwen-live-test-db --network f2r-qwen-live-test --memory 256m --cpus 1 --pids-limit 128 --tmpfs /var/lib/postgresql/data:rw,size=128m -e POSTGRES_DB=qwen_live_test -e POSTGRES_USER=qwen_test -e POSTGRES_HOST_AUTH_METHOD=trust postgres:17
docker exec f2r-qwen-live-test-db pg_isready -U qwen_test -d qwen_live_test
```

Если имена уже существуют, не трогать чужие ресурсы; использовать свои новые
имена. Для snapshot из уже fetched commit — `git archive` в новый ignored каталог,
без merge/checkout чужой ветки. Пример из PowerShell собственного worktree:

```powershell
$repoPath = (Get-Location).Path
docker run --rm --pull never --network f2r-qwen-live-test --read-only --tmpfs /tmp:rw,size=128m,mode=1777 --memory 512m --cpus 2 -e PYTHONPATH=/f2/backend:/f2:/work -e F2R_TEST_DATABASE_URL=postgresql+psycopg://qwen_test@f2r-qwen-live-test-db/qwen_live_test --mount "type=bind,src=$repoPath/.local/f2-reference,dst=/f2,readonly" --mount "type=bind,src=$repoPath,dst=/work,readonly" --workdir /f2 feedback2req-checks:latest python -B -m pytest /work/experiments/qwen/f2_checks -q -W error --tb=short -p no:cacheprovider
```

Для live test контейнерному клиенту недостаточно адреса host loopback: Ollama и
PG должны быть доступны в его согласованном test network namespace, с реальным
GPU и write-mount только собственного output. Предыдущий compose требует отдельной
настройки GPU на подходящей машине. Не включать GPU, сеть или публичные порты
автоматически. Внешний бесплатный ноутбук и локальная F2-БД пока не образуют такой
стенд; это конкретное условие будущей полной проверки, не скрытая готовность.

Основные проверки из готового Python окружения:

```text
python -B -W error -m unittest discover -s experiments/qwen/tests -v
python -B -W error -m unittest discover -s ai/tests -v
python -B scripts/validate_ai_contracts.py
python -B -m experiments.qwen.run inventory
python -m ruff check --no-cache --ignore EXE002 experiments/qwen
python -m ruff format --no-cache --check experiments/qwen
```

## Фактические итоги

| Проверка | Результат |
|---|---|
| Экспериментальный harness, prompts, sampler, bundle, gates и F2 boundary unit tests | **34 PASS**, 19.581 s; без сети и модели |
| Неизменённая AI-группировка | **37 PASS**, 6.830 s; без сети |
| Собственные F2/PG проверки | **8 PASS / 1 SKIP**, 26.20 s; skip — только отдельно разрешаемый live test |
| Опубликованные F2 execution + previous annotations tests | **38 PASS**, 83.51 s; без правок upstream |
| Контракты | **PASS**: 9 схем, 88 refs, 38 positive / 34 negative, 399 mutations, 20 offline APP-пар |
| Ruff check и format --check | **PASS**, включая notebook; EXE002 исключён из команды для Windows bind-mount permissions |
| Notebook | Содержимое code cells компилируется, execution_count=null и outputs=[]; облачное исполнение **NOT RUN** |
| Реальные Qwen, runtime bootstrap, live F2 | **NOT RUN**, нет авторизованной доступной вычислительной среды |

БД — PostgreSQL 17.11 x86_64 Linux. Суммарно 117 успешных тестов; пропущенный
live test не включён в эту сумму. Полный backend-набор и отдельные 47 eval-тестов
в этой итерации не повторялись: изменённый экспорт проверяется имеющимся mocked
harness/evaluator test, целевые F2 suites перечислены явно. Ошибки начальных
проверок не скрыты: при одновременной нагрузке 5s allowance в тесте аварии child
давал wall_deadline вместо child_failed. Этот тест проверяет классификацию
аварии, поэтому startup allowance повышен до 30s; отдельный 1s deadline test
сохранён. Lint/style и конкурирующее форматирование notebook исправлены,
проверки повторены успешно.

Независимый read-only review выявил и подтвердил исправление двух P2 (чужой
сервер на порту и происхождение seal revision); финальное чтение новых
существенных дефектов не нашло. Reviewer не запускал tests/runtime, не проверял
внешние источники и не давал проектных утверждений. Временная недоступность
Docker после возобновления устранена без установки; использован свой тестовый
контейнер. Подготовительные команды получения weights/runtime не исполнялись.

Runtime/weight compatibility,
peak resources, содержательное качество и действительный live F2 path остаются
неизмеренными до получения среды и разрешения. Все предложения дальнейшего
подключения требуют отдельной оценки; технический PASS не выбирает production-модель.
