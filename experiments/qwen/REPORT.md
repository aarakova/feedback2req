# Подготовка Qwen: факты, аудит и следующий эксперимент

Проверки начаты 2026-11-04, продолжены 2026-11-06. Это исследовательская
подготовка, не выбор production-модели и не оценка качества inference.
**Установка Ollama/весов и реальный inference не выполнялись.** Настоящие
пользовательские материалы и внешние вычисления не использовались.

## База и границы

`git fetch origin` выполнен перед созданием worktree. Удалённая
`integration/ai-foundation` совпала с проверенным
`410b936e451629a53ca1eb0fb15a4908961155b6`. Созданы собственные ветка
`experiment/qwen-group-findings` и worktree `.local/worktrees/qwen-group-findings`.
Исходный checkout пользователя не переключался.

Фактические подтверждения истории:

- F1 находится в `origin/main`: `e300a76` — extraction, `93013bc` — supervision;
  merge `0b5f3e0` включён в историю интеграционной базы.
- Автономная группировка включена коммитом `88ca281` перед HEAD `410b936`.
- Опубликованный `origin/feat/backend-finding-groups` при проверке указывал на
  `20656819aad3a857875ec0d91a263d903c85638b`. Он не сливался и не менялся.
- Backend, worker, AI-контракты 1.0, main и чужие ветки не изменялись.

Основания: [DECISIONS](../../docs/DECISIONS.md),
[AI_CONTRACTS](../../docs/AI_CONTRACTS.md),
[AI_VALIDATION](../../docs/AI_VALIDATION.md),
[AGENT_ARCHITECTURE](../../docs/AGENT_ARCHITECTURE.md),
[REQUIREMENTS](../../docs/REQUIREMENTS.md) и [DOMAIN](../../docs/DOMAIN.md).
Роли и человеческое решение сохраняются. Новых согласованных продуктовых
контрактов этот эксперимент не вводит.

## Оборудование

Windows CIM и read-only диагностика, 2026-11-06:

| Параметр | Наблюдение |
|---|---|
| CPU | AMD Ryzen 7 3700U with Radeon Vega Mobile Gfx; 4 физических ядра, 8 логических потоков; Environment.ProcessorCount=8 |
| RAM | TotalPhysicalMemory и видимая RAM: 7 448 702 976 bytes = 6,94 GiB |
| Свободная RAM | 417 036 KiB ≈ 0,40 GiB в одном актуальном снимке; 2026-11-04 было 555 440 KiB ≈ 0,53 GiB. Это изменчивые снимки, не резерв для модели |
| GPU | AMD Radeon RX Vega 10 Graphics, driver 31.0.12027.9001 |
| GPU AdapterRAM | 1 073 741 824 bytes. Это **не подтверждённая доступная вычислительная VRAM**; shared RAM дополнительно конкурирует с системой |
| VRAM/free GPU memory | Не измерены: нет работающего Ollama/GPU inference, nvidia-smi не применим к этой AMD iGPU |
| ОС | Windows 11 Pro x64, 10.0.26200 |
| Native Python | `python`/`python3` в PATH — Windows Store aliases, рабочего интерпретатора через них нет; `py` не найден. Обнаруженная ранее venv также ссылается на отсутствующий интерпретатор |
| Тестовый Python | Имеющийся Docker image: Python 3.12.15, jsonschema 4.26.0, referencing 0.37.0, Ruff 0.17.1 |
| Docker | Client/Engine 29.9.2, Docker Desktop 4.96.2; Linux amd64, WSL kernel 6.18.54.1; daemon временно был недоступен после возобновления, затем снова отвечал |
| Docker ресурсы | 8 CPU, 3 543 867 392 bytes ≈ 3,30 GiB RAM; CPU quota проверочных контейнеров ограничена отдельно |
| Ollama | Не найден в PATH и стандартном `%LOCALAPPDATA%/Programs/Ollama/ollama.exe`; установка/версии/веса не подтверждены; сервер не запускался |
| Диск C | Free 410 949 341 184 bytes ≈ 382,72 GiB в снимке; места достаточно для кандидатов, это не означает достаточную RAM |

Предыдущие сведения о CPU и 6,94 GiB RAM подтвердились. CPU inference технически
планируем; скорость и работоспособность не измерены. Vega 10 не найдена в
перечне поддерживаемых Windows AMD устройств в [Ollama GPU docs](https://docs.ollama.com/gpu).
Не считать ROCm/Vulkan ускорение доказанным и не менять драйверы/настройки ради
него автоматически. Первый конфиг задаёт `num_gpu=0`.

## Аудит двух существующих адаптеров

Сопоставлены именно интеграционные версии
[F1 provider](../../backend/feedback2req/processing/provider.py),
[F1 config](../../backend/feedback2req/config.py),
[F1 validation](../../backend/feedback2req/processing/validation.py),
[group provider](../../ai/group_findings/provider.py),
[group service](../../ai/group_findings/service.py) и
[group validation](../../ai/group_findings/validation.py).

| Аспект | F1 extract_feedback | Автономный group_findings |
|---|---|---|
| Вызов | `extract(value) -> dict` с decode content внутри адаптера | `group(value) -> str/bytes`; service отдельно decode/validate; mandatory verify_context до передачи |
| Конфигурация | Backend Settings, URL/model/gate; timeout 1–60 s | Frozen OllamaConfig, URL/model/gate; конечные положительные timeout, temperature 0–2, think bool |
| Сообщения | Inline английский system prompt, русский выход; полный canonical JSON user | Отдельный versioned русский prompt; полный canonical JSON user; копии request/verifier/provider |
| Structured output | `/api/chat`, stream=false, format из утверждённой response schema; общие defs целиком; temperature=0 | Та же схема вызова; только достижимые defs; temperature/think явно |
| Детерминированный приём | F1 runtime проверяет схему, точные цитаты/occurrence, ссылки, atomic coverage и сохранение | Service проверяет schema, global keys/IDs, coverage, роли, conflict members, many-to-many, lost completed, вопросы; частичность без trusted plan отклоняет |
| Ошибки | InvalidResponse или ProviderError; transport исключения объединены, `raise ... from exc` сохраняет cause | Safe GroupingError(code,rule), timeout отдельно, service redacts сторонние ошибки; без текста/URL в диагностике |
| HTTP envelope | done=true, decode message.content; нет отдельной проверки role/tool_calls/done_reason | done=true, message/content types, запрет tool_calls; нет проверки done_reason/role/thinking |
| Тайм-аут | socket timeout и внешняя worker supervision (не свойство HTTP-адаптера) | socket timeout, standalone hard deadline отсутствует |
| Ограничения | envelope cap 262144 bytes; материал по Settings по умолчанию ≤8192 chars; весь backend request/body ограничивается прикладным слоем | MAX_JSON_BYTES=1048576; bounded file reads/envelope decode, schema/domain checks; bytes не равны tokens |
| Генерация | Нет явных num_ctx/num_predict/threads/GPU/seed/keep_alive | То же; think/temperature есть. Ни один не контролирует вместимость полного prompt+input+output |
| Передача | Явный ai_transfer_enabled, URL+model; HTTP/HTTPS с host без username; proxies отключены, redirects запрещены | transfer_enabled is True, строгий /api/chat без query/fragment/credentials, port !=0; proxies отключены, redirects запрещены |
| Ограничение адресата | При включённом gate допускает любой настроенный host; это не локальная allowlist | Аналогично: gate — разрешение конфигурации, не проверка согласованного списка получателей |
| Synthetic/real | synthetic из processing_test_mode; сама метка не доказывает происхождение вывода | Явный Replay synthetic=True/model=none; Ollama synthetic=False; CLI только replay |
| Диагностика эксперимента | Нет полного weight/runtime/prompt lock или измерений ресурсов в адаптере | Versioned adapter/prompt; прежний CLI/replay не записывает реальную модель, latency/quality отсутствуют |

Рекомендации для будущего отдельного согласованного изменения:

1. Общий транспорт `/api/chat`: одинаковая политика URL/получателей, отключённые
   redirects/proxies, типизированные безопасные ошибки, конечные time/byte limits,
   проверка envelope/role/tools/thinking/done_reason и различимые timeout.
2. Сохранить operation-specific подготовку, prompts/schema/application validation;
   не смешивать extraction, grouping, generation и verification или их охват.
   Стандартизировать границу возврата raw content, а не переносить проверки в HTTP.
3. Вынести технический envelope (model digest, runtime, config, prompt hash,
   generation timings, unavailable measurements) за пределы canonical AI JSON.
   Не добавлять поля в контракт 1.0.
4. Разделять происхождение inference/replay независимо от test-mode запуска;
   fixture/model results хранить в разных сериях. Не измерять модель по скорости replay.
5. Общая cancellation/supervision политика должна принадлежать вызывающему слою;
   один socket timeout не гарантирует остановку server inference.

Здесь рекомендации **не применены к production**. Эксперимент использует отдельный
[adapter](adapter.py), существующие неизменённые схемы/прикладной валидатор и
выделенный loopback endpoint. Общая унификация production потребует отдельной
задачи, регрессий F1 и согласования затрагиваемых контрактов при их изменении.

## Модели и источники

Официальные карточки и runtime-публикации проверены 2026-11-04 и 2026-11-06.
Карточка — свидетельство устройства/лицензии и рекомендаций автора, не качество
на задачах feedback2req. Статья о классификации ожиданий отсутствует в доступном
контексте; ссылка/название запрошены, выводов по статье нет.

| Параметр | Qwen3-4B | Qwen3.5-9B |
|---|---|---|
| Официальная карточка | [Qwen/Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B), наблюдённая revision `1cfa9a7208912126459214e8b04321603b3df60c` | [Qwen/Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B), revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a` |
| Лицензия | Apache-2.0 по карточке; сохранять license/notice при распространении | Apache-2.0 по карточке, отдельно от любых лицензий статьи/данных/хостинга |
| Модель | Dense language model, 4,0B; выбран исходный Qwen3, не отдельные instruct/thinking-2507 | Language model 9B с vision encoder; group_findings использует только текст |
| Официальный контекст | 32768 native; до 131072 с YaRN, не настройка этой машины | 262144 native; расширение до 1010000 заявлено автором; это не обещание памяти или качества |
| Runtime | Карточка указывает Ollama/llama.cpp, Transformers, vLLM≥0.8.5, SGLang≥0.4.6.post1 | Transformers, vLLM, SGLang, KTransformers; текущая карточка рекомендует свежие/nightly builds, которые надо отдельно pin и проверить |
| Ollama quantization | [4b-q4_K_M](https://ollama.com/library/qwen3:4b-q4_K_M), около 2,6 GB; [tags](https://ollama.com/library/qwen3/tags) также Q8_0/FP16 | [9b-q4_K_M](https://ollama.com/library/qwen3.5:9b-q4_K_M), весь package около 6,6 GB: language model ~5,6 GB плюс BF16 projector ~922 MB |
| Выбранный runtime | Ollama 0.40.14, [официальный релиз](https://github.com/ollama/ollama/releases/tag/v0.40.14), опубликован 2026-11-03; фиксируем версию, а не плавающий latest | Тот же pin для сравнения; совместимость фактической модели+схемы должна пройти smoke после установки |
| Настройки пробы | think=false, temperature=.7, top_p=.8, top_k=20, min_p=0, seed=42, num_ctx=8192, num_predict=1024, num_thread=4, num_gpu=0 | Отдельный конфиг, think=false, такие же sampling/context/output/seed; presence_penalty=1.5, repeat_penalty=1 по non-thinking рекомендации карточки; num_gpu=99 для согласованного GPU-хоста |

Квантизации Ollama — runtime-distribution выбранных весов; revision HF не является
их digest. Короткие web-ID не заменяют SHA установленного manifest. Полный digest
весов/размер/quantization фиксируются локальным `/api/tags` + `/api/show` lock
**после** разрешённой загрузки. Они пока неизвестны. Явные теги существуют;
runtime-совместимость, лицензия конкретного downloaded package, GPU загрузка и
работа сложной JSON Schema фактически ещё не испытаны.

[Structured outputs docs](https://docs.ollama.com/capabilities/structured-outputs)
подтверждают передачу JSON Schema в format; облачный Ollama не поддерживает эту
возможность согласно текущей странице. Документация предлагает temperature=0 для
детерминированности; здесь .7 взято из рекомендаций Qwen non-thinking и не
оптимизировано под задачу. Сравнение с temperature=0 — отдельная конфигурация/серия,
не скрытая замена. Greedy не рекомендуется карточкой Qwen3 для thinking.

Прежний [MODEL_SELECTION](../../ai/group_findings/MODEL_SELECTION.md) сравнивал
Qwen3-4B, Qwen2.5-7B и Qwen2.5-3B по карточкам и теоретическому размеру весов.
Это не сравнительный inference; численных оценок качества/скорости там нет.
Qwen3.5-9B исследуется отдельно и не заменяется результатами 4B.

## Ресурсы и выбор первого запуска

Фактический RSS/VRAM/runtime overhead не измерен. Размер файла не равен памяти.
Для Qwen3-4B Q4_K_M ~2,6 GB весов плюс F16 KV cache при 8192 приблизительно
1,125 GiB (36 layers × 8 KV heads × 128 dims × K/V × 2 bytes × 8192), плюс
runtime, buffers, ОС и Python. Это расчёт для планирования, не измерение и не
гарантия реализации конкретного runtime. Ориентир — несколько GiB свободной RAM
с запасом; при текущих 0,40 GiB проба не должна запускаться. Docker VM 3,30 GiB
также меньше этого расчёта вместе с runtime. Native запуск может иметь больше
ресурсов, если пользователь освободит память. Нельзя обещать устойчивую работу.

Первый кандидат остаётся **Qwen3-4B Q4_K_M, CPU, non-thinking, один G-compatible**
после разрешения и повторной проверки RAM. Сначала измерить загрузку, время,
объём памяти и сложную schema. При OOM/timeout сохранить факт и остановиться;
не выдавать replay за fallback. При нехватке памяти использовать отдельную
машину, не наращивать swap/WSL и не менять параметры системы автоматически.

9B BF16 — порядка 18 GB только language weights до encoder/cache/runtime;
Q4 package уже ~6,6 GB до buffers/cache. Этот ноутбук с 6,94 GiB и Windows не
предлагается как рабочее 9B-окружение. Планировать отдельный CPU-хост с 16–32 GiB
RAM или GPU с 16–24 GiB для Q4; для BF16 и запаса контекста — 24–48 GiB VRAM
после проверки фактической свободной памяти. Это ориентиры provisioning, не
подтверждённые минимумы; 24 GiB BF16 может потребовать ограничения контекста и
text-only runtime. Не переносить огромный контекст из примеров карточки вслепую.

## План Qwen3.5-9B и варианты среды

1. Получить статью и зафиксировать точную версию/квантизацию, исходные данные,
   prompt, thinking mode и критерии автора; текущий план не заявляет её репликацию.
2. Согласовать отдельный хост и обработку **только synthetic**. Pin runtime,
   загрузить конкретный тег, записать digest/model show и license. Запустить
   [отдельный конфиг](qwen35-9b.json) через тот же local CLI **на том хосте**.
   Конфиг CPU serving из compose не включает GPU: согласовать GPU runtime/
   provisioning отдельно, не включать устройства незаметно.
3. Smoke G-compatible, затем S05/S06, потом 24 случая и повторные серии.
   Сначала Q4, при необходимости отдельно BF16 как контроль эффекта квантизации.
   Разные весовые варианты/разные GPU — отдельные серии.
4. Для сравнения 4B/9B удерживать одинаковые входы/prompt/context/output;
   отдельно сообщать различие рекомендованных sampling параметров. Для строгого
   контроля sampler использовать ещё одну явно одинаковую конфигурацию для обеих.
5. Заполнить экспертные листы, сохранить техническую частоту ошибок с числом
   попыток/исключений, времена cold load/eval, ресурсы и unavailable поля.
   Проверять permutation/paraphrase по смысловым группам и позициям, не по ID.
   До утверждения gold — только предварительные наблюдения, без окончательного
   рейтинга/превосходства или production-порога.

Варианты, цены проверены по [официальному Runpod pricing](https://www.runpod.io/pricing)
2026-11-06 (страница обновлена 2026-11-04):

| Вариант | Ориентир стоимости | Ограничения и данные |
|---|---|---|
| Имеющаяся отдельная рабочая станция организации, CPU 16–32 GiB или подходящий GPU | $0 дополнительной аренды, если уже доступна; электричество/администрирование не оценены | Самостоятельное размещение, контроль доступа/диска/логов у владельца; медленный CPU не исключён; наличие не подтверждено |
| Runpod RTX 4090, 24 GB | Community от $0.34/h, Secure $0.89/h; 2 GPU-hours ≈ $0.68/$1.78 до extras | Тариф/stock/регион не гарантированы; disk, stopped storage, transfer, налоги и warmup не включены; платное внешнее окружение требует отдельного разрешения |
| Runpod A40, 48 GB | Community $0.35/h, Secure $0.59/h; 2 GPU-hours ≈ $0.70/$1.18 до extras | Больше запаса для BF16, но скорость не измерена; те же ограничения availability/стоимости |

Для hosted VM не утверждены конфиденциальность, отсутствие retention/training,
регион, договорные условия и полный доступ провайдера. Перед возможным запуском
согласовать конкретного получателя/регион/бюджет/срок удаления; сверить применимые
условия и настройки логов. Передавать только выбранный synthetic dataset и
экспериментальный код, без репозитория с секретами, пользовательских материалов
или токенов. Не открывать публичный Ollama endpoint; выполнять harness внутри
выделенного хоста. Аккаунты, VM и платные API здесь не создавались.

## Валидация и ограничения

См. команды в [README](README.md). Фактические проверки выполнялись offline в
уже имевшемся `feedback2req-checks:latest`, image ID
`sha256:0c154beef3fd4f49181dafba8fabc4f4c3211aa2110e4c966bf686cdc23b9379`.
Новых образов/пакетов/моделей не скачивали. Исходные набор и схемы не менялись.

| Проверка | Факт |
|---|---|
| Новые mocked adapter/harness tests | Финальный повтор: 21 tests OK, 19.005 s |
| Существующая группировка | 37 tests OK, 12.691 s |
| Существующий eval harness | 47 tests OK, 38.622 s |
| Утверждённые схемы | 9 schemas, 88 refs, 38 positive/34 negative, 399 unknown-field mutations, 20 fixture pairs: PASS |
| Inventory | 24 synthetic cases; применимость S01–S14; no inference |
| Docker Compose | `config --quiet`: PASS; serving не запускался |
| PowerShell | Оба скрипта прошли parser без ошибок; runtime/sampling не выполнялись |
| Ruff | Финальные check и format --check: PASS (EXE002 исключён в команде из-за executable permissions Windows bind mount) |

Первичные тесты обнаружили SyntaxError при первоначальном редактировании
проверки конфигурации и неверное вычисление ROOT. Исправлено; тесты не ослаблялись.
Независимый read-only reviewer подтвердил исправление ROOT, watchdog receive/crash
и bounded сохранения HTTP error/partial bytes. Замечание о потере safe preflight
диагностики исправлено отдельным выводом code/rule. Финальный повторный review
также охватил PowerShell/compose/документацию: новых существенных замечаний нет.
Reviewer самостоятельно не запускал tests/inference/serving/resource scripts
и не проверял внешние источники. Установка и совместимость реального Ollama остаются
непроверенными, peak RAM/VRAM, throughput и содержательное качество неизвестны.

Исходный synthetic dataset hash:
`6926cb777854891d20727d868036e0e5fcfb0956952bf4e2ef566e224ea6169d`.
Хэш экспериментального набора печатает inventory и фиксирует каждый реальный
run; при изменении annotations/variant он закономерно меняется. Нет сохранённых
реальных модельных ответов или содержательных метрик для обеих Qwen.

Предложение будущей интеграции: сначала измерения и экспертная оценка, затем
отдельная задача на transport унификацию и сравнение operation-specific адаптеров.
После готовности F2 отдельно подключать одобренную конфигурацию через существующий
group service и его verifier, с повторной атомарной проверкой актуальности при
публикации. Эксперимент не подключает worker, не изменяет F2 и не выбирает
production-модель автоматически.
