# Воспроизводимое испытание Qwen: план и комплект запуска

Статус: подготовка и офлайн-проверки, **без настоящего inference**.
Продолжение 2026-11-21 не разрешает push, merge, установку runtime, скачивание
весов или внешние вычисления. CLI-флаги ниже обозначают отдельно полученное
разрешение; сами разрешения они не дают. Данные — только существующая синтетика.
Методика и разметка предварительные, окончательных порогов качества нет.

## База и уже выполненная работа

После fetch проверены опубликованные объекты; чужие рабочие деревья не менялись:

| Назначение | Ветка / SHA |
|---|---|
| Согласованная исходная AI-база и нынешний main | `integration/ai-foundation`, `410b936e451629a53ca1eb0fb15a4908961155b6` |
| Более полная опубликованная интеграция | `integration/full-workflow-ui`, `600065626be5e671223c8a8afd696a14bb4c20e5` |
| Продолжаемый Qwen-контур, чистый в начале работы | `experiment/qwen-live-evaluation`, `5ca279836ba6237744d4c55f8197ed9b516af8b9` |
| Граница внутреннего F2 | `feat/backend-finding-groups`, `4c62684e7769d2c3a71de3264aa15e954a1262d0` |

Текущий отдельный worktree сохраняется: его история содержит согласованную базу
410b936. Новый дублирующий контур или перенос на preview/workspace не создаётся.
У 6000656 прочитана применимая область DEC-017/F3: реальный provider не выбран,
Qwen не импортируется в worker, публичный POST остаётся PROPOSED. Схемы AI 1.0 и
AI_VALIDATION совпадают с нашей базой. Наш прежний F2 snapshot остаётся точным
read-only reference; здесь не заявляется новая проверка всего приложения 6000656.

Уже готовы два неизменённых prompt, матрица моделей/настроек, 34 входа, watchdog,
raw responses, schema/application validators, expert-review и опциональный F2
test. Этот план использует их; новые API, storage, worker и AI-роли не вводятся.

## Конкретный первый профиль и ресурсы

Основной кандидат — `Qwen/Qwen3.5-9B`, отдельный Ollama tag
`qwen3.5:9b-q4_K_M`, runtime **0.40.14**, quantization **Q4_K_M**.
Фактический digest пока отсутствует: его необходимо получить с установленного
runtime через `run lock`, затем сверять перед серией. Тег не заменяет digest.
Проверенные первичные источники и различия runtime — в
[DEVELOPER_GUIDANCE.md](DEVELOPER_GUIDANCE.md).

| Параметр | Первый профиль |
|---|---|
| sampler | `recommended`, non-thinking / general tasks |
| temperature / top_p / top_k / min_p | `0.7 / 0.8 / 20 / 0` |
| presence_penalty / Ollama repeat_penalty | `1.5 / 1.0` |
| think / truncate / shift | `false / false / false` |
| num_ctx / num_predict / template reserve | `16384 / 1024 / 512` |
| num_thread / num_gpu / seed | `4 / 99 / 42` |
| Wall deadline одного запроса | **90 s**, включая запуск client child |
| Бюджет каждой серии | **900 s**, непрошедшие случаи фиксируются как not_attempted |
| Внешний watchdog процесса серии | smoke **600 s**, all **1020 s** |
| JSON/request/response ограничения | max request 16384 bytes, max envelope 262144 bytes |
| Параллелизм | Один запрос, одна загруженная модель, очередь не более одной |

90 s — срок до отмены client child; дополнительно до 4 s отведено его
terminate/kill. Для собственной server group бюджет ожидания TERM 5 s, затем
KILL 2 s; sampler join 3 s и финальный GPU query до 2 s. Это бюджеты ожидания,
не гарантия освобождения VRAM драйвером. Shutdown учитывается отдельно от
per-case duration; общий elapsed серии может включать дополнительные cleanup
расходы. Не заявлять, что каждый процесс гарантированно исчезает ровно на 90-й s.

Изолированный Linux x86_64 GPU host/notebook, Python 3.12+, рабочий драйвер и
доступный ускоритель. До установки preflight должен измерить **свободные**:
GPU >=10 GiB, host/cgroup RAM >=8 GiB, диск >=16 GiB. Это conservative planning
gates, не доказанные минимумы модели; прошедший gate не гарантирует отсутствие
OOM. CPU-only 9B потребовал бы >=16 GiB свободной RAM и отдельного плана времени;
текущий GPU bootstrap этот вариант не запускает. RAM ноутбука ~6.94 GiB и VM
~3.30 GiB недостаточно. Размер весов и AdapterRAM не являются доступной VRAM.
Существующая числовая CUDA_VISIBLE_DEVICES ограничивает выбор устройства и не
расширяется. Отключённые/UUID/MIG masks отклоняются до установки/загрузок: для
них нужен отдельный проверенный setup. Без mask оператор должен подтвердить
разрешённость выбранного выделенного устройства; free memory не доказывает квоту.

Лимиты здесь — краткий эксперимент, не длинный reasoning benchmark. При output
length stop не повышать cap автоматически и не дописывать JSON. Отдельный профиль
с большим cap допустим только как новая явно обозначенная серия с достаточными
ресурсами. Sampling не гарантирует отсутствие повторов. Самодельные stop-маркеры
и greedy decoding не используются. Seed не гарантирует побитовой идентичности
разных GPU/runtime.

## Исполнение по этапам

1. **Без inference:** проверить чистоту источников, SHA bundle и его manifest,
   выполнить inventory, экспериментальные тесты и валидатор контрактов. Матрица
   и bundle не должны скачивать runtime/веса или обращаться к model endpoint.
2. **До настоящего запуска:** получить разрешение на конкретную машину, runtime,
   веса и передачу синтетического комплекта. Для бесплатного notebook пользователь
   сам входит в свой аккаунт и выделяет GPU; проверить фактическую квоту/срок.
   Без оплаты/нового аккаунта/нежелательной проверки личности; не монтировать Drive.
3. **Smoke:** в свежей распаковке комплекта выбрать `smoke`. По четыре одинаковых
   входа D-conflict/K-conditions/S-compatible/U-insufficient для product и
   experimental; не более **8** попыток. Product первым — порядок фиксирован,
   это пока не рандомизированный сравнительный benchmark.
4. **Разбор smoke:** проверить runtime/digest/off switch, отсутствие обрезки,
   technical errors, raw JSON, content, halt_reason и shutdown. Смысл независимо
   проверяет эксперт. При timeout, length stop, unexpected thinking или иной
   незавершённой provider-оболочке следующая попытка/серия не ставится в очередь.
5. **Полный pilot:** только после разбора и разрешения соответствующего объёма
   вычисления — свежая распаковка, `all`. Тот же профиль/seed, все **34** входа
   на каждый prompt, максимум **68** попыток. Бюджет 900 s может оставить часть
   входов not_attempted; они не превращаются в успешные. Автоматического перехода
   от smoke к all нет. Не смешивать их latency и failure denominators.
6. **Необязательное сравнение 4B:** отдельное разрешение на её веса/вычисления.
   Для model comparison использовать существующую `matched` матрицу: presence=0
   у обеих моделей, остальные одинаковые sampler settings. Это дополнительный
   эксперимент; recommended 9B (presence=1.5) не заменять его результатами и не
   приписывать sampler effect размеру модели. Новые seeds/repeats — отдельные серии.

Команды этапа 1 из готового Python окружения, из корня **этого** worktree:

```text
python -B -m experiments.qwen.run inventory
python -B -m experiments.qwen.portable preflight
python -B -m experiments.qwen.portable matrix --sampler recommended --output .local/qwen-runs/planned-9b-recommended
python -B -W error -m unittest discover -s experiments/qwen/tests -v
python -B scripts/validate_ai_contracts.py
```

Только для отдельно одобренного интерактивного бесплатного GPU runtime, после
проверки bundle, из новой распаковки (сейчас эти команды **не исполнялись**):

```text
python -B -m experiments.qwen.bootstrap_cloud --suite smoke --approved-runtime --approved-weights --approved-synthetic-transfer --free-runtime-confirmed
# После разбора smoke и согласования объёма, в другой свежей распаковке:
python -B -m experiments.qwen.bootstrap_cloud --suite all --approved-runtime --approved-weights --approved-synthetic-transfer --free-runtime-confirmed
```

Для отдельной Linux-машины с заранее установленным runtime можно использовать
существующие `run lock`/`run run` из [README](README.md); не заявлять облачный
bootstrap исполненным и обеспечить свой supervisor/измерения. Все output paths
новые и под `.local/qwen-runs`; ничего не перезаписывать. Bootstrap single-use:
его `.local/cloud-runtime` создаётся исключительно, повтор требует свежей
распаковки, а не автоматического удаления файлов. Notebook по умолчанию smoke,
все разрешения False. Достаточная память без разрешения не включает inference.

## Что именно оценивается

Три независимых результата: **структура**, **смысл**, **производительность**.

| Проверка смысла | Существующие входы / ожидаемое наблюдение (preliminary) |
|---|---|
| Выдуманные основания/детали | S-compatible, G-deleted-evidence, G-direct-inferred-uncertain: не изобретать пресеты, цитаты и достоверность |
| Реальные противоположные позиции | S06-group, G-conflict, D-conflict: сохранить обе позиции; D-independent — также независимую находку |
| Ложный конфликт при разных условиях | G-different-conditions, K-conditions: учесть устройство/условия |
| Неоднозначность и недостаток данных | G-ambiguous, U-insufficient: вопросы/uncertainties вместо выдуманной причины |
| Сходство и возможные дубли находок | S05-group/reordered, G-compatible, S-compatible: объединение по смыслу без удаления идентичности/разных оснований |
| Пересечения и полнота | G-many-to-many, G-mixed-coverage: различить membership и уникальность входов; ungrouped — явный результат |
| Злоумышленная инструкция в данных | G-injection, U-injection: не получать полномочия, инструменты или внешний URL из текста |
| Перестановки и перефразы | Все имеющиеся reversed пары и G-compatible-paraphrase: сравнивать finding sets/позиции и смысл, не local_id/порядок/точную формулировку |

Из S01–S14 только S05/group+reordered и S06/group уже содержат group_findings
входы; inventory явно отмечает применимость остальных. S09/unsupported evidence,
S12/составные основания и S13/possible_duplicate Requirement — случаи операции
verify_requirement, **не** проверенные группировкой. Указание similarity в группе
не создаёт её вердикт possible_duplicate. Их нельзя автоматически преобразовать
в группировку и объявить покрытыми.

Структурный путь: strict JSON → Schema 1.0 → прикладные ссылки, coverage и
membership → отдельно при включении F2 его более строгий приём. Technical PASS
не подтверждает поддержку основаниями или отсутствие реального конфликта.
Эксперт заполняет существующий expert-review, включая evidence,
unsupported_additions, opposite_positions, uncertainty и possible_duplicates,
со ссылками на конкретные synthetic finding/fragment keys. Итог — наблюдения и
примеры ошибок, без окончательного score или утверждения превосходства модели.

Производительность: отдельно cold/reload latency (keep_alive=0), wall duration,
Ollama load/prompt/eval counters, attempted/scheduled/errors/not_attempted,
выборочные RAM/CPU и GPU device measurements. Сравнивать одинаковые inputs,
sampler, порядок и host; одна серия не доказывает стабильный throughput или p95.

## Диагностика и доказательства остановки

Экспорт notebook включает `.local/qwen-runs`, без весов, runtime, аккаунта и
server.log. В нём должны находиться:

- `cloud-plan.json`, `cloud-resource-preflight.json`, configs и per-prompt locks;
- точные dataset/requests, raw envelope/content, request/prompt/config/schema/
  code/dataset hashes, actual model digest и runtime version;
- per-case и aggregate diagnostics, unfinished/not_attempted, expert-review;
- `cloud-runtime-resources.jsonl` / `.json` и `cloud-runtime-shutdown.json`.

[Сборщик Linux](resource_monitor.py) начинает наблюдение **после pull, до model
requests**, завершает после попытки shutdown. Номинальный interval 1 s; query
GPU ограничен 2 s, фактические интервалы видны по UTC timestamps. RSS sum может
повторно учитывать shared pages, CPU deltas пропускают первые samples и короткие
процессы. Device used/free и utilization относятся ко всему выбранному GPU;
`model_peak_vram_bytes` остаётся null. Пропуск измерения не записывается нулём.
Отчёт серии не выдаётся за точный peak каждой отдельной попытки. Для корреляции
использовать её started/dispatched timestamps и duration. Измеритель не является
механизмом остановки и может влиять на latency.

Client watchdog закрывает только client child. Bootstrap отдельно завершает
свою session/process group (TERM, затем KILL), проверяет живые PID и сохраняет
status. `cleanup_failed`, отсутствующий shutdown report, оставшийся свой runner
или сомнение в прекращении compute блокируют следующий запуск. Сравнить GPU
before/after snapshot с фактической доступной памятью после завершения; device
delta при соседних процессах не является доказательством работы/остановки модели.
Отсоединившийся в новую группу runner не покрывается process-group контролем.
Если это обнаружится на реальном runtime, сохранить данные и завершить **свою**
эфемерную VM; не искать/убивать чужие процессы по имени. После экспорта notebook
отключить runtime. Сильная cgroup-изоляция отдельного GPU-контейнера — возможная
доработка после выбора среды; данный комплект её не объявляет готовой.

## Зависимости и конкретные следующие согласования

1. Достаточная выделенная среда, реальный свободный GPU/RAM/disk, авторизация,
   квота/срок и разрешённые условия обработки synthetic data.
2. Явное разрешение на task-local runtime/dependencies, веса 9B и, если среда
   внешняя, перенос именно проверенного комплекта; smoke/all объём определяется
   отдельно от выбора машины. Платных ресурсов и production-доступа не требуется.
3. Предварительная экспертная разметка/ответственный эксперт: до этого смысловой
   результат остаётся pending/preliminary. Метрики не заменяют согласование.
4. Для настоящего F2 пути — exact snapshot 4c62684, отдельный PostgreSQL и
   согласованная test network namespace с Ollama. Notebook не устанавливает PG;
   предыдущие synthetic F2 PASS не равны выполненному Qwen → F2 inference.
5. Предложение за текущей границей: отдельный экспериментальный адаптер
   verify_requirement 1.0 на опубликованном готовом компоненте с S09/S10/S12/S13,
   без API/storage/worker. Потребуются согласование объёма исследования, exact
   component pin и validation mapping; сейчас такой адаптер не реализуется.

Установки, weight digest, ответы модели, semantic verdict, measured model RAM/VRAM
и real F2 path появятся только после фактического исполнения. До этого итог —
проверенный офлайн комплект и перечисленные зависимости, не оценка качества Qwen.
