# Рекомендации разработчиков и границы генерации Qwen

Проверено 2026-11-21. Это настройки **эксперимента**, не изменение AI-контракта
1.0 или разрешение подключить модель к приложению. Основная модель —
`Qwen/Qwen3.5-9B`, Ollama tag `qwen3.5:9b-q4_K_M`; Qwen3-4B остаётся отдельным
техническим baseline. Реальный inference и проверка этих настроек на весах
**не выполнялись**. Рекомендации не гарантируют отсутствие повторов или качество.

## Что рекомендует Qwen

Первичные источники: [Qwen3.5-9B model card](https://huggingface.co/Qwen/Qwen3.5-9B#using-qwen35-via-the-chat-completions-api),
[Qwen3-4B model card](https://huggingface.co/Qwen/Qwen3-4B#best-practices).
Использовать карточку конкретной модели: общий GitHub-репозиторий Qwen3.5 сейчас
переадресует на Qwen3.8, чьи правила thinking/history нельзя переносить на 9B.
У 9B отдельно указаны настройки по режиму и типу задачи:

| Модель / режим | temperature | top_p | top_k | min_p | presence_penalty | repetition_penalty |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3.5-9B, non-thinking, общие задачи | 0.7 | 0.8 | 20 | 0 | 1.5 | 1.0 |
| Qwen3.5-9B, non-thinking, reasoning | 1.0 | 0.95 | 20 | 0 | 1.5 | 1.0 |
| Qwen3.5-9B, thinking, общие задачи | 1.0 | 0.95 | 20 | 0 | 1.5 | 1.0 |
| Qwen3.5-9B, thinking, точное программирование | 0.6 | 0.95 | 20 | 0 | 0 | 1.0 |
| Qwen3-4B, non-thinking | 0.7 | 0.8 | 20 | 0 | см. ниже | см. ниже |
| Qwen3-4B, thinking | 0.6 | 0.95 | 20 | 0 | см. ниже | см. ниже |

Для Qwen3-4B разработчики предостерегают от greedy decoding и допускают
presence penalty 0–2 для борьбы с повторами. При выраженных повторах предлагают
1.5; повышение может усиливать смешение языков и ухудшать ответ. Карточка не
задаёт универсального repetition penalty для этой строки. В нашем исходном
профиле 4B теперь **явно** заданы presence=0 и repeat=1, чтобы не наследовать
неучтённые параметры Ollama tag. Если понадобится 4B presence=1.5, это отдельный
сравниваемый config/lock, без незаметного изменения неудачной серии.

Для первого `group_findings` smoke выбран non-thinking/general preset 9B.
Это инженерная исходная точка; пригодность reasoning preset для группировки
нужно проверять отдельно на тех же входах. Thinking пока запрещён конфигурацией.
Не переносить настройки Qwen3 на Qwen3.5 или между режимами автоматически.

Qwen3.5 не поддерживает prompt-команды переключения `/think`/`/nothink`.
Управление режимом выполняет API/runtime. Для Ollama используем top-level
`think=false`, а не аргументы vLLM `chat_template_kwargs` и не дописывание
инструкций к исходным отзывам. Перед запуском `/api/show` должен явно объявить
boolean `false` среди поддерживаемых thinking values; отсутствие метаданных
или только именованные уровни означают отказ. Нельзя считать низкий thinking
level выключенным режимом. В историю не переносятся рассуждения; сейчас каждый
запрос независим и содержит только system prompt и исходный JSON user message.

## Отличия API и ограничения эксперимента

Проверены [Ollama thinking](https://docs.ollama.com/capabilities/thinking),
[chat API](https://docs.ollama.com/api/chat),
[параметры](https://docs.ollama.com/modelfile#valid-parameters-and-values),
а также исходники именно закреплённого runtime
[api/types.go v0.40.14](https://github.com/ollama/ollama/blob/v0.40.14/api/types.go)
и [server/routes.go v0.40.14](https://github.com/ollama/ollama/blob/v0.40.14/server/routes.go).
Pin [релиза 0.40.14](https://github.com/ollama/ollama/releases/tag/v0.40.14)
сохраняется; ссылка на [Ollama Qwen3.5](https://ollama.com/library/qwen3.5)
подтверждает наличие семейства, а не измеренную совместимость нашего стенда.
Поддержка поля в коде ещё не доказывает его корректную работу с конкретным GGUF.

- Qwen `repetition_penalty` соответствует Ollama **`repeat_penalty`**.
  `presence_penalty` — отдельный параметр, не синоним. У runtime по умолчанию
  repeat_last_n=64: семантика штрафа не обязана совпадать со всеми framework.
  Фактические model parameters/template фиксируются show hash в lock.
- Adapter version **3** требует явных presence/repeat значений, положительных
  temperature/top_p/repeat_penalty, top_k>=2 и min_p<1. Отрицательные/нулевые
  num_predict, в том числе Ollama `-1`/`-2`, запрещены. Эти запреты убирают
  очевидные опасные настройки, но не являются математической защитой от циклов.
- `truncate=false` и `shift=false` запрещают скрытое урезание/сдвиг контекста.
  Предварительная консервативная проверка размера сохраняется, как и проверка
  prompt_eval_count после ответа. Никаких ручных stop на `</think>`, JSON `}`,
  строках находок или другие самодельные маркеры нет: они могут оборвать ответ.
- У матрицы контекст 16384 и output cap 1024, у исходных локальных config —
  контекст 8192. Это ограниченный короткий smoke, **не** воспроизведение
  ширококонтекстного benchmark Qwen. Карточки предлагают гораздо более длинные
  ответы для сложных reasoning-задач; автоматически увеличивать лимиты на
  ограниченной машине нельзя. Для отдельного длинного теста нужны ресурсы,
  новый config/lock и явное указание отличий. YaRN здесь не включается.
- `done_reason=length` отклоняется даже при JSON корректной формы. Превышение
  eval_count над num_predict, отсутствие счётчика генерации и неожиданный
  `message.thinking` также запрещают приём. Raw envelope/content сохраняются,
  JSON не достраивается и не ремонтируется. Length stop сам по себе не доказывает
  цикл: причиной может быть просто маленький output budget.

## Как ограничивается зависание

[run.py](run.py) задаёт wall deadline на отдельный клиентский процесс и общий
бюджет серии. Socket timeout дополняет, но не заменяет wall deadline.
Автоматических повторов, самокоррекции ответов и переключения sampler нет.
При timeout, неопределённом состоянии транспорта/child, length stop, нарушении
generation budget, thinking или context серия останавливается; причина
сохраняется в `diagnostics.json:halt_reason`, оставшиеся случаи — not_attempted.
Обычная завершённая schema/application ошибка остаётся отдельным наблюдением.

Закрытие клиентского соединения **не доказывает**, что сервер прекратил считать.
[Linux bootstrap](bootstrap_cloud.py) запускает собственный Ollama в отдельной
session/process group. В finally посылает TERM всей этой группе, затем при
необходимости KILL, в том числе если родитель уже завершился, а runner остался.
Проверяются живые члены группы; зомби не считаются вычисляющими процессами.
Результат пишется в `cloud-runtime-shutdown.json` и входит в экспорт notebook.
Не останавливаются процессы по имени, чужой daemon или процессы клиента.
Отсоединившиеся в отдельную группу процессы этим механизмом не контролируются;
поведение настоящего Ollama runner и освобождение VRAM ещё нужно измерить.

При обычном CLI, Windows server или отдельном Compose автоматического контроля
server process group нет. После timeout остановить **свой** сервер/контейнер и
проверить процессы и память до следующего запуска. Не закрывать чужие задачи.
Для бесплатной notebook VM после экспорта результатов отключить runtime.

## Следующий разрешаемый эксперимент

Cloud bootstrap теперь начинает с **recommended** 9B preset (presence=1.5),
оба неизменённых prompt получают одинаковые D/K/S/U. Отдельная `matched` матрица
с presence=0 сохраняется как контролируемое исследование; это не рекомендуемый
первый smoke и не замена 9B developer preset. Настройки между сериями фиксируются
в разных файлах и lock. Пример подготовки без inference:

```text
python -B -m experiments.qwen.portable matrix --sampler recommended --output .local/qwen-runs/recommended-v3
python -B -m experiments.qwen.portable matrix --sampler matched --output .local/qwen-runs/matched-v3
```

Порядок запуска и разрешения — в [LIVE_EVALUATION.md](LIVE_EVALUATION.md).
Первым проверить реальный digest, off switch, завершение короткого ответа,
лимиты, latency и фактическое освобождение ресурсов. Только затем расширять
число случаев/моделей. Смысловую экспертную оценку выполнять отдельно от JSON
Schema/application PASS. Ни модель, ни настройки пока не выбраны для production.
