# STEP 1 — Архитектура БД, сущности, потоки данных

## Архитектура приложения

```
backend/
  app/
    application/       # Use-cases, сервисы, DTO
    domain/            # Доменные модели, интерфейсы (порты)
    infrastructure/    # Реализации: DB, Kafka, S3, Telegram, Express
```

---

## Профили запуска

| # | Профиль | Роль |
|---|---------|------|
| 1 | **tg-poll-worker** | aiogram long-polling -> сохраняет в `to_express` -> публикует в Kafka `TO_EXPRESS` |
| 2 | **express-webhook-worker** | FastAPI принимает webhooks от pybotx -> сохраняет в `to_telegram` -> публикует в Kafka `TO_TELEGRAM` |
| 3 | **express-send-worker** | Читает Kafka `TO_EXPRESS` -> отправляет в Express через pybotx -> обновляет `to_express.express_sync_id` |
| 4 | **tg-send-worker** | Читает Kafka `TO_TELEGRAM` -> отправляет в Telegram через aiogram -> обновляет `to_telegram.tg_message_id` |
| 5 | **admin-api** | FastAPI — управление channel_pairs, employees, апрув каналов |

---

## Схема БД (PostgreSQL)

> **Enum-типы хранятся как VARCHAR в БД**, определяются только на уровне Python (str Enum).
> Это упрощает миграции и избегает `ALTER TYPE` при добавлении значений.

### 1. `channel_pairs` — связка TG-чат <-> Express-чат (1:1)

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | UUID PK | — |
| `tg_chat_id` | BIGINT NOT NULL UNIQUE | Telegram chat.id |
| `express_chat_id` | UUID UNIQUE NULL | Express chat.id (NULL до одобрения, заполняется автоматически при approve) |
| `is_approved` | BOOLEAN NOT NULL DEFAULT FALSE | Апрув админом |
| `name` | VARCHAR(255) | Человекочитаемое имя связки |
| `created_at` | TIMESTAMPTZ NOT NULL | — |
| `updated_at` | TIMESTAMPTZ NOT NULL | — |

**Индексы:** UNIQUE(tg_chat_id), UNIQUE(express_chat_id)

---

### 2. `employees` — сотрудники с позициями

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | UUID PK | — |
| `tg_user_id` | BIGINT UNIQUE NULL | Telegram user.id |
| `express_huid` | UUID UNIQUE NULL | Express user HUID |
| `full_name` | VARCHAR(255) NULL | ФИО (задаётся в админке) |
| `position` | VARCHAR(255) NULL | Позиция: "Системный Аналитик", "Архитектор" и т.д. |
| `created_at` | TIMESTAMPTZ NOT NULL | — |
| `updated_at` | TIMESTAMPTZ NOT NULL | — |

**Constraint:** CHECK (tg_user_id IS NOT NULL OR express_huid IS NOT NULL)

**Логика форматирования (текст всегда с новой строки после заголовка):**

**TG -> Express** (позиция + имя):
```
[Архитектор, Иван Иванов]:
Вот документация по проекту
```
- Если position и full_name заданы в БД: `[Позиция, Имя]`
- Если только position: `[Позиция]`
- Если только full_name: `[Имя]`
- Если ничего не задано: `[TG first_name last_name]`

**Express -> TG** (только позиция, без ФИО):
```
[Архитектор]:
Обновил требования к API
```
- Если position задана в БД: `[Позиция]`
- Если не задана: без заголовка, просто текст

**Формат файловых вложений (TG -> Express):**
Ссылки на файлы добавляются в конец сообщения. Работает одинаково для одного файла и media_group.
```
[Архитектор, Иван Иванов]:
Вот документация по проекту

Вложения:
1. https://our-host/api/files/a1b2c3d4/.../spec.pdf
2. https://our-host/api/files/e5f6a7b8/.../diagram.png
```
Если текста нет (media_group без caption):
```
[Архитектор, Иван Иванов]:

Вложения:
1. https://our-host/api/files/a1b2c3d4/.../photo1.jpg
```

### Разбиение длинных сообщений (MAX = 4096 символов)

> Лимит одинаков для обеих платформ: **Telegram = 4096**, **Express (pybotx) = 4096**.
> После добавления заголовка и блока вложений текст может превысить лимит.

**Стратегия: разбиение на несколько сообщений.**

```python
# application/message_splitter.py

MAX_MESSAGE_LENGTH = 4096

def split_to_express(header: str, body: str | None, attachments_block: str | None) -> list[str]:
    """Разбивает сообщение для Express. Возвращает список частей <= 4096 символов.

    Часть 1: header + начало body
    Часть N: продолжение body
    Последняя часть: конец body + attachments_block (если не влезает — отдельной частью)
    """

def split_to_telegram(header: str | None, body: str | None) -> list[str]:
    """Разбивает сообщение для Telegram. Возвращает список частей <= 4096 символов.

    Часть 1: header + начало body
    Часть N: продолжение body
    """
```

**Правила разбиения:**
1. Заголовок `[Позиция, Имя]:\n` — всегда в первом сообщении
2. Текст разбивается по границе строк (не рвём слова, ищем `\n` или пробел)
3. Блок `Вложения:\n1. URL\n...` — в последнем сообщении; если не влезает вместе с текстом — отдельным сообщением
4. Все части отправляются последовательно в правильном порядке
5. Reply привязывается только к первому сообщению

**Пример разбиения (TG -> Express, длинный текст + файлы):**
```
Сообщение 1/3:
[Архитектор, Иван Иванов]:
Начало длинного текста...
...продолжение до 4096 символов

Сообщение 2/3:
...продолжение текста...

Сообщение 3/3:
...конец текста

Вложения:
1. https://our-host/api/files/.../doc.pdf
```

> **В БД сохраняется только `express_sync_id` / `tg_message_id` первого сообщения** —
> оно используется для reply-резолва. Дополнительные части не маппятся.

---

### 3. `to_express` — сообщения TG -> Express

> **Telegram media_group:** каждый файл — отдельное сообщение со своим `message_id`,
> но все сообщения группы имеют общий `media_group_id`. Мы создаём отдельную запись
> в `to_express` для каждого TG-сообщения (т.е. для каждого файла в группе).
> `media_group_id` сохраняем для группировки на стороне Express.

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | UUID PK | — |
| `channel_pair_id` | UUID FK -> channel_pairs | — |
| `tg_message_id` | BIGINT NOT NULL | Telegram message_id |
| `tg_chat_id` | BIGINT NOT NULL | Telegram chat.id |
| `tg_user_id` | BIGINT NOT NULL | Отправитель в TG |
| `tg_media_group_id` | VARCHAR(255) NULL | Telegram media_group_id (связывает файлы в группу) |
| `express_sync_id` | UUID NULL | Заполняется send-worker после отправки |
| `reply_to_tg_message_id` | BIGINT NULL | TG message_id на который ответили |
| `event_type` | kafka_event_type NOT NULL DEFAULT 'new_message' | Тип события |
| `status` | message_status NOT NULL DEFAULT 'pending' | — |
| `created_at` | TIMESTAMPTZ NOT NULL | — |
| `updated_at` | TIMESTAMPTZ NOT NULL | — |

**Индексы:**
- UNIQUE(tg_chat_id, tg_message_id, event_type) — идемпотентность
- INDEX(channel_pair_id)
- INDEX(express_sync_id) — для поиска при reply-резолве
- INDEX(tg_media_group_id) WHERE tg_media_group_id IS NOT NULL — группировка файлов
- INDEX(status) WHERE status = 'pending'

---

### 4. `to_telegram` — сообщения Express -> TG

> **pybotx:** строго один attachment на сообщение. Каждому входящему сообщению
> с файлом соответствует ровно одна запись.

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | UUID PK | — |
| `channel_pair_id` | UUID FK -> channel_pairs | — |
| `express_sync_id` | UUID NOT NULL | Express message sync_id |
| `express_chat_id` | UUID NOT NULL | Express chat.id |
| `express_user_huid` | UUID NOT NULL | Отправитель в Express |
| `tg_message_id` | BIGINT NULL | Заполняется send-worker после отправки |
| `tg_chat_id` | BIGINT NULL | Заполняется send-worker |
| `reply_to_express_sync_id` | UUID NULL | Express sync_id на который ответили (source_sync_id) |
| `event_type` | kafka_event_type NOT NULL DEFAULT 'new_message' | Тип события |
| `status` | message_status NOT NULL DEFAULT 'pending' | — |
| `created_at` | TIMESTAMPTZ NOT NULL | — |
| `updated_at` | TIMESTAMPTZ NOT NULL | — |

**Индексы:**
- UNIQUE(express_sync_id, event_type) — идемпотентность
- INDEX(channel_pair_id)
- INDEX(tg_chat_id, tg_message_id) — для поиска при reply-резолве
- INDEX(status) WHERE status = 'pending'

---

### 5. `message_files` — файлы, привязанные к сообщениям

> Единая таблица для файлов обоих направлений. Позволяет хранить несколько файлов
> на одно сообщение (media_group в TG) и один файл на сообщение Express.

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | UUID PK | — |
| `direction` | message_direction NOT NULL | tg_to_express / express_to_tg |
| `message_record_id` | UUID NOT NULL | FK -> to_express.id или to_telegram.id (по direction) |
| `file_type` | VARCHAR(31) NOT NULL | image / video / document / voice / audio / video_note |
| `file_name` | VARCHAR(255) NULL | Оригинальное имя файла |
| `file_content_type` | VARCHAR(127) NULL | MIME-тип |
| `file_size` | BIGINT NULL | Размер в байтах |
| `s3_key` | VARCHAR(1024) NULL | Ключ в S3/Minio (только для direction=tg_to_express) |
| `express_file_id` | UUID NULL | ID файла в Express (только для direction=express_to_tg) |
| `express_file_url` | VARCHAR(2048) NULL | URL файла в Express (только для direction=express_to_tg) |
| `express_file_hash` | VARCHAR(255) NULL | Hash файла в Express |
| `created_at` | TIMESTAMPTZ NOT NULL | — |

**Индексы:**
- INDEX(message_record_id, direction)
- INDEX(s3_key) WHERE s3_key IS NOT NULL

---

## Классификация типов сообщений

> Поллим ВСЕ сообщения, но обрабатываем только определённые типы.
> Остальные — пересылаем в System Channel (если настроен) или пропускаем.

### Telegram -> Express: обрабатываемые типы

| aiogram ContentType     | Действие        | Примечание                                    |
|-------------------------|-----------------|-----------------------------------------------|
| `TEXT`                  | **FORWARD**     | Текстовое сообщение                           |
| `PHOTO`                | **FORWARD**     | Фото -> S3 -> ссылка в Express               |
| `DOCUMENT`             | **FORWARD**     | Документ -> S3 -> ссылка в Express            |
| `VIDEO`                | **FORWARD**     | Видео -> S3 -> ссылка в Express               |
| `VOICE`                | **FORWARD**     | Голосовое -> S3 -> ссылка в Express            |
| `AUDIO`                | **FORWARD**     | Аудио -> S3 -> ссылка в Express               |
| `VIDEO_NOTE`           | **FORWARD**     | Кружок -> S3 -> ссылка в Express              |
| `CONTACT`              | **FORWARD**     | Контакт -> транслируем как текст (имя + телефон) |
| `ANIMATION`            | **SKIP**        | GIF — не транслируем                          |
| `STICKER`              | **SKIP**        | Не транслируем                                |
| `DICE`                 | **SKIP**        | Не транслируем                                |
| `GAME`                 | **SKIP**        | Не транслируем                                |
| `STORY`                | **SKIP**        | Не транслируем                                |
| все chat events         | **SKIP**        | Системные события TG — игнорируем             |
| `LOCATION`             | **SYSTEM**      | -> Kafka SYSTEM_CHANNEL (мета без body)       |
| `VENUE`                | **SYSTEM**      | -> Kafka SYSTEM_CHANNEL (мета без body)       |
| `POLL`                 | **SYSTEM**      | -> Kafka SYSTEM_CHANNEL (мета без body)       |
| все остальные          | **SYSTEM**      | -> Kafka SYSTEM_CHANNEL (неизвестный тип)     |

**Действия:**
- **FORWARD** — санитизация + сохранение в БД + Kafka TO_EXPRESS + трансляция
- **SYSTEM** — только Kafka SYSTEM_CHANNEL (без body, без записи в БД). Express-send-worker отправляет мета-уведомление в System Channel
- **SKIP** — полностью игнорируем

### Express -> Telegram: обрабатываемые типы

| pybotx поле            | Действие        | Примечание                                    |
|-------------------------|-----------------|-----------------------------------------------|
| `body` (только текст)  | **FORWARD**     | Текстовое сообщение                           |
| `file` (image)         | **FORWARD**     | Скачиваем -> send_photo в TG                  |
| `file` (video)         | **FORWARD**     | Скачиваем -> send_video в TG                  |
| `file` (document)      | **FORWARD**     | Скачиваем -> send_document в TG               |
| `file` (voice)         | **FORWARD**     | Скачиваем -> send_voice в TG                  |
| `sticker`              | **SKIP**        | Не транслируем                                |
| `location`             | **SKIP**        | Не транслируем (нет System Channel в TG)      |
| `contact`              | **FORWARD**     | Транслируем как текст (имя)                   |
| `link`                 | **FORWARD**     | Транслируем как текст (url)                   |

### Функции фильтрации и санитизации

```python
# application/message_filter.py

class TgMessageAction(str, Enum):
    FORWARD = "forward"      # Транслировать в Express
    SYSTEM = "system"        # Отправить в System Channel
    SKIP = "skip"            # Игнорировать

FORWARD_CONTENT_TYPES = {
    ContentType.TEXT, ContentType.PHOTO, ContentType.DOCUMENT,
    ContentType.VIDEO, ContentType.VOICE, ContentType.AUDIO,
    ContentType.VIDEO_NOTE, ContentType.CONTACT,
}

SKIP_CONTENT_TYPES = {
    ContentType.STICKER, ContentType.ANIMATION, ContentType.DICE,
    ContentType.GAME, ContentType.STORY,
    # + все chat events (NEW_CHAT_MEMBERS, LEFT_CHAT_MEMBER, etc.)
    ContentType.NEW_CHAT_MEMBERS, ContentType.LEFT_CHAT_MEMBER,
    ContentType.NEW_CHAT_TITLE, ContentType.NEW_CHAT_PHOTO,
    ContentType.DELETE_CHAT_PHOTO, ContentType.PINNED_MESSAGE,
    # ... и другие системные
}

def classify_tg_message(content_type: str) -> TgMessageAction:
    """Определяет действие для TG-сообщения.
    Принимает примитив content_type (str), не aiogram Message — легко тестировать."""
    if content_type in FORWARD_CONTENT_TYPES:
        return TgMessageAction.FORWARD
    if content_type in SKIP_CONTENT_TYPES:
        return TgMessageAction.SKIP
    return TgMessageAction.SYSTEM  # всё неизвестное -> System Channel

def should_forward_express_message(*, has_sticker: bool, has_location: bool) -> bool:
    """True если Express-сообщение нужно транслировать в TG.
    Принимает примитивы, не pybotx IncomingMessage — легко тестировать."""
    if has_sticker:
        return False
    if has_location:
        return False
    return True  # текст, файл, контакт, ссылка


# application/sanitize.py

def sanitize_to_express(text: str | None, entities: list | None = None) -> str | None:
    """Очистка текста из Telegram перед отправкой в Express.
    1. strip_tg_formatting(text, entities) — удаляет форматирование Telegram:
       - MarkdownV2: *bold*, _italic_, `code`, ```pre```, ~strikethrough~, ||spoiler||, [link](url)
       - Markdown v1: *bold*, _italic_, `code`, ```pre```, [link](url)
       - HTML: <b>, <i>, <code>, <pre>, <a href>, <s>, <u>, <tg-spoiler>, <blockquote>
       Используем message.entities (MessageEntity) для точного удаления —
       aiogram предоставляет offset+length каждой entity, вырезаем разметку, оставляем plain text.
    2. strip_emoji(text) — удаляет все Unicode emoji
    3. strip() — убирает пустые строки по краям
    4. Если результат пуст — возвращает None
    """

def sanitize_to_telegram(text: str | None) -> str | None:
    """Очистка текста из Express перед отправкой в Telegram.
    1. strip_express_formatting(text) — Express может присылать HTML-подобную разметку,
       удаляем все HTML-теги
    2. strip_emoji(text) — удаляет все Unicode emoji
    3. strip()
    4. Если результат пуст — возвращает None
    """
```

> **Применение:** classify/sanitize вызываются в poll/webhook worker-ах ДО записи в Kafka.
> FORWARD -> санитизация + БД + Kafka.
> SYSTEM -> только System Channel (без БД).
> SKIP -> игнорируем.

---

## Мастер-система групп и System Channel

### Telegram — мастер по группам

1. Бот добавляется в TG-группу и назначается **Admin**
2. При первом сообщении в группе — tg-poll-worker проверяет:
   - Есть ли `channel_pair` для этого `tg_chat_id`?
   - Если нет — автоматически создаёт `channel_pair(tg_chat_id=..., is_approved=FALSE, express_chat_id=NULL)`
   - Если есть, но `is_approved = FALSE` — сообщение **не транслируется в Express**
3. Администратор одобряет связку через frontend (admin-api):
   - Нажимает "Одобрить" на `channel_pair`
   - **admin-api автоматически:**
     1. Создаёт чат в Express: `express_chat_id = await bot.create_chat(bot_id, name, chat_type=GROUP_CHAT, huids=[...])`
     2. Обновляет запись: `UPDATE channel_pairs SET express_chat_id=?, is_approved=TRUE`
   - Оператору не нужно вручную указывать `express_chat_id`
4. После одобрения — сообщения начинают транслироваться

### API одобрения (admin-api)

```python
# POST /api/admin/channel-pairs/{pair_id}/approve

async def approve_channel_pair(pair_id: UUID, body: ApproveRequest):
    """
    body:
      name: str           # Имя чата в Express (по умолчанию = TG chat title)
      member_huids: list[UUID]  # Участники Express-чата (опционально)
    """

    async with session_factory() as session:
        pair = await channel_pair_repo.get(session, pair_id)
        if pair.is_approved:
            raise HTTPException(400, "Already approved")

    # 1. Создание чата в Express (ВНЕ транзакции — внешний API)
    express_chat_id = await express_bot.create_chat(
        bot_id=settings.express_bot_id,
        name=body.name or pair.name,
        chat_type=ChatTypes.GROUP_CHAT,
        huids=body.member_huids or [],
    )

    # 2. ┌─ BEGIN TRANSACTION ─────────────────────────────────────┐
    async with session_factory() as session:
        async with session.begin():
            await channel_pair_repo.approve(
                session, pair_id,
                express_chat_id=express_chat_id,
            )
    #    └─ COMMIT ────────────────────────────────────────────────┘
```

> **Примечание:** `express_chat_id` в таблице `channel_pairs` теперь `UUID NULL`
> (NULL пока не одобрена). При одобрении заполняется автоматически.

### System Channel (Express) — отдельный Kafka-топик

> System Channel — специальный чат в Express для уведомлений о:
> 1. Сообщениях из неодобренных TG-групп (все типы кроме SKIP)
> 2. Сообщениях типа SYSTEM из одобренных групп (location, poll, venue, неизвестные)
>
> **Без body, без записи в БД, без mark_sent** — чисто мета-уведомление.

**Kafka-топик:** `SYSTEM_CHANNEL`
- **Partition key:** `str(tg_chat_id)`
- **Value (JSON):**
```json
{
  "tg_chat_id": -100123456,
  "tg_chat_title": "Проект Альфа",
  "tg_user_name": "Иван Иванов",
  "content_type": "LOCATION",
  "reason": "unapproved_channel | unsupported_type"
}
```

> **Без body** — транслируем только тип сообщения, канал и имя автора.
> Это безопасно и не сломается на любом типе контента.

**Обработка:** express-send-worker читает из `SYSTEM_CHANNEL` и отправляет в Express:
```
Формат: "[TG: {tg_chat_title}] {tg_user_name}: {content_type}"
Пример: "[TG: Проект Альфа] Иван Иванов: LOCATION"
         "[TG: Проект Альфа] Иван Иванов: TEXT (unapproved)"
```

**Логика в tg-poll-worker:**
```
action = classify_tg_message(message)

if action == SKIP:
    -> игнорируем

if channel_pair not found or is_approved = FALSE:
    -> publish to Kafka SYSTEM_CHANNEL (все FORWARD + SYSTEM сообщения)
    -> RETURN

if action == SYSTEM:
    -> publish to Kafka SYSTEM_CHANNEL
    -> RETURN

if action == FORWARD:
    -> санитизация + БД + Kafka TO_EXPRESS
```

---

## Резолв reply-контекста

При пересылке ответа нужно найти соответствующее сообщение на целевой платформе.

**TG -> Express (reply):**
Сообщение в TG отвечает на `reply_to_tg_message_id = X`. Ищем `express_sync_id`:
1. `SELECT express_sync_id FROM to_express WHERE tg_message_id = X AND tg_chat_id = ? AND event_type = 'new_message'`
2. Если не найдено: `SELECT express_sync_id FROM to_telegram WHERE tg_message_id = X AND tg_chat_id = ? AND event_type = 'new_message'`

**Express -> TG (reply):**
Сообщение в Express отвечает на `reply_to_express_sync_id = Y`. Ищем `tg_message_id`:
1. `SELECT tg_message_id, tg_chat_id FROM to_telegram WHERE express_sync_id = Y AND event_type = 'new_message'`
2. Если не найдено: `SELECT tg_message_id, tg_chat_id FROM to_express WHERE express_sync_id = Y AND event_type = 'new_message'`

---

## Резолв edit/delete

**Edit TG -> Express:**
`SELECT express_sync_id FROM to_express WHERE tg_message_id = X AND tg_chat_id = ? AND event_type = 'new_message'`

**Edit Express -> TG:**
`SELECT tg_message_id, tg_chat_id FROM to_telegram WHERE express_sync_id = Y AND event_type = 'new_message'`

**Delete Express -> TG (только в эту сторону):**
`SELECT tg_message_id, tg_chat_id FROM to_telegram WHERE express_sync_id = Y AND event_type = 'new_message'`

---

## Kafka-топики и формат событий

### Топик `TO_EXPRESS`
- **Partition key:** `str(tg_chat_id)` — гарантирует порядок в рамках чата
- **Value (JSON):**
```json
{
  "event_type": "new_message | edit_message",
  "record_id": "uuid — PK из to_express",
  "channel_pair_id": "uuid",
  "tg_message_id": 12345,
  "tg_chat_id": -100123456,
  "tg_user_id": 98765,
  "tg_media_group_id": "13579 | null",
  "body": "текст сообщения | null (для файлов в media_group без caption)",
  "reply_to_tg_message_id": null,
  "files": [
    {
      "file_id": "uuid — PK из message_files",
      "s3_key": "a1b2c3d4-e5f6-7890-abcd-ef1234567890/doc.pdf",
      "file_name": "doc.pdf",
      "file_content_type": "application/pdf",
      "file_type": "document"
    }
  ]
}
```

### Топик `TO_TELEGRAM`
- **Partition key:** `str(express_chat_id)` — гарантирует порядок в рамках чата
- **Value (JSON):**
```json
{
  "event_type": "new_message | edit_message | delete_message",
  "record_id": "uuid — PK из to_telegram",
  "channel_pair_id": "uuid",
  "express_sync_id": "uuid",
  "express_chat_id": "uuid",
  "express_user_huid": "uuid",
  "body": "текст сообщения",
  "reply_to_express_sync_id": null,
  "file": {
    "file_id": "uuid — PK из message_files",
    "express_file_url": "https://express-host/file/...",
    "file_name": "photo.jpg",
    "file_type": "image",
    "file_content_type": "image/jpeg"
  }
}
```

> **Примечание:** `TO_EXPRESS.files` — массив (media_group может содержать 2-10 файлов).
> `TO_TELEGRAM.file` — один объект или null (pybotx: один attachment на сообщение).

> **Тело сообщения (`body`) передаётся через Kafka, но НЕ сохраняется в БД** — в БД хранятся только идентификаторы и мета-информация.

### Топик `SYSTEM_CHANNEL`
- **Partition key:** `str(tg_chat_id)`
- **Обработчик:** express-send-worker
- **Без записи в БД, без mark_sent** — fire-and-forget уведомление
- **Value (JSON):**
```json
{
  "tg_chat_id": -100123456,
  "tg_chat_title": "Проект Альфа",
  "tg_user_name": "Иван Иванов",
  "content_type": "LOCATION",
  "reason": "unapproved_channel | unsupported_type"
}
```

> **Без body** — только мета-информация: откуда, от кого, какой тип.
> express-send-worker форматирует и отправляет в `express_system_channel_id`:
> `"[TG: Проект Альфа] Иван Иванов: LOCATION"`
> Если `reason=unapproved_channel`: `"[TG: Проект Альфа] (не одобрен) Иван Иванов: TEXT"`
> Если `reason=unsupported_type`: `"[TG: Проект Альфа] Иван Иванов: LOCATION (не поддерживается)"`

---

## Потоки данных (с явными границами транзакций)

### Flow 1: Telegram -> Express (new message / batch)

```
TG User -> [Telegram API]
  -> tg-poll-worker (aiogram long-polling, получает batch updates)

    0. Классификация каждого сообщения:
       action = classify_tg_message(message)
       - SKIP -> игнорируем (стикеры, dice, системные события TG)
       - SYSTEM -> отправить в System Channel (локации, опросы, неизвестные типы)
       - FORWARD -> продолжаем обработку

    0.1. Проверка одобрения группы (для FORWARD и SYSTEM):
       SELECT * FROM channel_pairs WHERE tg_chat_id = ?
       - Если нет записи -> CREATE channel_pair(is_approved=FALSE)
       - Если is_approved = FALSE:
           -> ВСЕ (FORWARD + SYSTEM) -> publish to Kafka SYSTEM_CHANNEL
              (мета без body: tg_chat_id, chat_title, user_name, content_type, is_approved=false)
           -> RETURN (не сохраняем в to_express, не публикуем в TO_EXPRESS)
       - Если is_approved = TRUE, но action = SYSTEM:
           -> publish to Kafka SYSTEM_CHANNEL (is_approved=true)
           -> RETURN (не сохраняем в to_express)

    0.2. Санитизация текста для FORWARD-сообщений:
       sanitize_to_express(body): strip markdown + strip emoji

    1. Скачать файлы в S3 (вне транзакции, идемпотентно по s3_key={uuid4}/{filename})
       for each message with file:
           bot.download(file_id) -> boto3.upload_fileobj(bucket, s3_key)

    2. ┌─ BEGIN TRANSACTION ──────────────────────────────────────────┐
       │ for each message in batch:                                   │
       │   INSERT INTO to_express (..., status='pending')             │
       │     ON CONFLICT (tg_chat_id, tg_message_id, event_type)     │
       │     DO NOTHING                                               │
       │     RETURNING id  -- NULL если дубликат                      │
       │   if inserted:                                               │
       │     INSERT INTO message_files (...) для каждого файла        │
       └─ COMMIT ─────────────────────────────────────────────────────┘

    3. После коммита: для каждого inserted (не дубликата):
       publish to Kafka TO_EXPRESS (key=str(tg_chat_id))
```

### Flow 2: Express -> Telegram (new message / webhook batch)

```
Express User -> [Express BotX webhook -> pybotx handler]
  -> express-webhook-worker

    1. ┌─ BEGIN TRANSACTION ──────────────────────────────────────────┐
       │ for each message in webhook batch:                           │
       │   INSERT INTO to_telegram (..., status='pending')            │
       │     ON CONFLICT (express_sync_id, event_type)                │
       │     DO NOTHING                                               │
       │     RETURNING id                                             │
       │   if inserted:                                               │
       │     INSERT INTO message_files (...) если есть файл           │
       └─ COMMIT ─────────────────────────────────────────────────────┘

    2. После коммита: для каждого inserted:
       publish to Kafka TO_TELEGRAM (key=str(express_chat_id))
```

### Flow 3: express-send-worker (Kafka TO_EXPRESS -> Express API)

```
faststream consumer читает из TO_EXPRESS:

    1. Проверка идемпотентности:
       SELECT status FROM to_express WHERE id = record_id
       if status = 'sent' -> skip, commit offset

    2. Резолв reply (если reply_to_tg_message_id != null):
       find_express_sync_id(tg_chat_id, reply_to_tg_message_id)

    3. Получить Employee по tg_user_id -> форматирование "[Позиция, Имя]: текст"

    4. Для файлов: сформировать download URL (наша HTTP-ручка /files/{s3_key})

    5. Отправка в Express API:
       express_sync_id = bot.send_message(bot_id, chat_id, body, ...)

    6. ┌─ BEGIN TRANSACTION ──────────────────────────────────────────┐
       │ UPDATE to_express                                            │
       │   SET express_sync_id = ?, status = 'sent', updated_at = now│
       │   WHERE id = record_id AND status = 'pending'               │
       └─ COMMIT ─────────────────────────────────────────────────────┘

    7. Если Express API вернул ошибку -> НЕ коммитим Kafka offset
       (сообщение будет повторно доставлено)
```

### Flow 4: tg-send-worker (Kafka TO_TELEGRAM -> Telegram API)

```
faststream consumer читает из TO_TELEGRAM:

    1. Проверка идемпотентности:
       SELECT status FROM to_telegram WHERE id = record_id
       if status = 'sent' -> skip, commit offset

    2. Резолв reply (если reply_to_express_sync_id != null):
       find_tg_message(reply_to_express_sync_id)

    3. Получить Employee по express_huid -> форматирование "[Позиция]: текст"

    4. По event_type:
       - new_message:
           if file: скачать из Express -> BufferedInputFile
           tg_message = bot.send_message/send_document/send_photo(...)
       - edit_message:
           Найти tg_message_id оригинала
           bot.edit_message_text(chat_id, message_id, new_text)
       - delete_message:
           Найти tg_message_id оригинала
           bot.delete_message(chat_id, message_id)

    5. ┌─ BEGIN TRANSACTION ──────────────────────────────────────────┐
       │ UPDATE to_telegram                                           │
       │   SET tg_message_id = ?, tg_chat_id = ?,                    │
       │       status = 'sent', updated_at = now()                   │
       │   WHERE id = record_id AND status = 'pending'               │
       └─ COMMIT ─────────────────────────────────────────────────────┘

    6. Если Telegram API вернул ошибку -> НЕ коммитим Kafka offset
```

### Flow 5: Edit TG -> Express

```
TG edited_message -> tg-poll-worker
  (та же логика что Flow 1, но event_type='edit_message')
  -> express-send-worker:
    -> Найти express_sync_id оригинала в to_express
    -> Express API edit
    -> UPDATE status='sent' в транзакции
```

### Flow 6: Edit/Delete Express -> Telegram

```
Express event_edit/event_deleted -> express-webhook-worker
  (та же логика что Flow 2, но event_type='edit_message'/'delete_message')
  -> tg-send-worker:
    -> Найти tg_message_id оригинала в to_telegram
    -> bot.edit_message_text() / bot.delete_message()
    -> UPDATE status='sent' в транзакции
```

---

## Идемпотентность

**Poll/Webhook workers:**
- UNIQUE constraint на `(tg_chat_id, tg_message_id, event_type)` и `(express_sync_id, event_type)`
- `INSERT ... ON CONFLICT DO NOTHING RETURNING id` — если `id IS NULL` — дубликат, Kafka-событие НЕ публикуется

**Send workers:**
- Перед отправкой: `SELECT status WHERE id = record_id` — если `status = 'sent'` — пропуск, offset коммитится
- `UPDATE ... WHERE status = 'pending'` — защита от гонки при повторной доставке
- Ошибка API -> offset НЕ коммитится -> Kafka повторно доставит

---

## Файлы

### TG -> Express (S3/Minio)

1. tg-poll-worker скачивает файл через `bot.download(file_id)` (макс 20MB)
2. Загружает в Minio через boto3: `s3.upload_fileobj(file, bucket, key)`
3. S3 key формат: `{uuid4}/{filename}` — UUID генерируется при загрузке, обеспечивает уникальность и неугадываемость URL (авторизации на ручке нет)
4. Запись в `message_files` с `direction=tg_to_express`, `s3_key`
5. **Media group:** каждый файл — отдельное TG-сообщение с общим `media_group_id`.
   Poll-worker создаёт отдельную запись `to_express` + `message_files` для каждого.
   Send-worker группирует по `tg_media_group_id` и отправляет текст + все download URL в одном сообщении Express.
6. express-send-worker формирует download URL: `/api/files/{uuid4}/{filename}` и добавляет ссылки в тело сообщения

### Express -> Telegram

1. pybotx: один attachment на сообщение (`IncomingMessage.file`)
2. Webhook-worker сохраняет мета в `message_files` с `direction=express_to_tg`, `express_file_url`
3. tg-send-worker скачивает файл (async file: `await file.open()`, или base64 decode)
4. Отправляет в TG через `bot.send_document()` / `bot.send_photo()` и т.д. используя `BufferedInputFile`

---

## Доменные сущности (domain layer)

```python
# domain/models.py

class EventType(str, Enum):
    NEW_MESSAGE = "new_message"
    EDIT_MESSAGE = "edit_message"
    DELETE_MESSAGE = "delete_message"

class MessageStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"

@dataclass
class ChannelPair:
    id: UUID
    tg_chat_id: int
    express_chat_id: UUID
    is_approved: bool
    name: str | None

@dataclass
class Employee:
    id: UUID
    tg_user_id: int | None
    express_huid: UUID | None
    full_name: str | None
    position: str | None

@dataclass
class FileAttachment:
    """Мета-информация о файле."""
    file_id: UUID
    file_type: str          # image, video, document, voice, audio, animation
    file_name: str | None
    file_content_type: str | None

@dataclass
class S3FileAttachment(FileAttachment):
    """Файл, загруженный в S3 (TG -> Express)."""
    s3_key: str

@dataclass
class ExpressFileAttachment(FileAttachment):
    """Файл из Express (Express -> TG)."""
    express_file_url: str

# --- Kafka DTO: два раздельных типа для каждого направления ---

@dataclass
class ToExpressEvent:
    """Событие из Kafka топика TO_EXPRESS (отправить в Express)."""
    event_type: EventType
    record_id: UUID
    channel_pair_id: UUID
    tg_message_id: int
    tg_chat_id: int
    tg_user_id: int
    tg_media_group_id: str | None
    body: str | None
    reply_to_tg_message_id: int | None
    files: list[S3FileAttachment]       # 0..N файлов (media_group)

@dataclass
class ToTelegramEvent:
    """Событие из Kafka топика TO_TELEGRAM (отправить в Telegram)."""
    event_type: EventType
    record_id: UUID
    channel_pair_id: UUID
    express_sync_id: UUID
    express_chat_id: UUID
    express_user_huid: UUID
    body: str | None
    reply_to_express_sync_id: UUID | None
    file: ExpressFileAttachment | None  # 0..1 файл (pybotx: один на сообщение)

class SystemChannelReason(str, Enum):
    UNAPPROVED_CHANNEL = "unapproved_channel"   # Группа ещё не одобрена администратором
    UNSUPPORTED_TYPE = "unsupported_type"        # Тип сообщения не поддерживается для трансляции

@dataclass
class SystemChannelEvent:
    """Событие из Kafka топика SYSTEM_CHANNEL.
    Без body — только мета-информация. Без записи в БД."""
    tg_chat_id: int
    tg_chat_title: str
    tg_user_name: str
    content_type: str             # "TEXT", "LOCATION", "POLL", etc.
    reason: SystemChannelReason
```

---

## Слой infrastructure — реализации (без Protocol)

> Вместо абстрактных Protocol-интерфейсов — сразу конкретные классы в `infrastructure/`.
> Слои разделены по пакетам, но без лишней индирекции.

```
backend/app/
  infrastructure/
    db/
      session.py          # AsyncSession factory (SQLAlchemy + psycopg)
      models.py           # ORM-модели (Table definitions)
      to_express_repo.py  # CRUD для to_express + message_files
      to_telegram_repo.py # CRUD для to_telegram + message_files
      mapping_queries.py  # Запросы reply/edit/delete резолва (обе таблицы)
      employee_repo.py    # CRUD employees
      channel_pair_repo.py# CRUD channel_pairs
    kafka/
      broker.py           # FastStream broker, publish_to_express / publish_to_telegram
    s3/
      storage.py          # boto3 client: upload, get_presigned_url, download_url
    telegram/
      bot.py              # aiogram Bot + Dispatcher setup, proxy config
    express/
      bot.py              # pybotx Bot + HandlerCollector setup
```

**Все repo-методы принимают `AsyncSession` явно** — транзакции управляются
на уровне application-сервисов (`async with session.begin(): ...`).

```python
# Пример: infrastructure/db/to_express_repo.py

class ToExpressRepo:
    async def bulk_insert(
        self, session: AsyncSession, records: list[ToExpressInsert],
    ) -> list[UUID]:
        """INSERT ... ON CONFLICT DO NOTHING RETURNING id.
        Возвращает список id вставленных записей (без дубликатов)."""

    async def bulk_insert_files(
        self, session: AsyncSession, files: list[MessageFileInsert],
    ) -> None: ...

    async def get_status(self, session: AsyncSession, record_id: UUID) -> MessageStatus: ...

    async def mark_sent(
        self, session: AsyncSession, record_id: UUID, express_sync_id: UUID,
    ) -> None:
        """UPDATE ... SET status='sent', express_sync_id=? WHERE id=? AND status='pending'"""

# Пример: infrastructure/db/mapping_queries.py

class MappingQueries:
    async def find_express_sync_id(
        self, session: AsyncSession, tg_chat_id: int, tg_message_id: int,
    ) -> UUID | None:
        """Ищет в to_express, затем в to_telegram."""

    async def find_tg_message(
        self, session: AsyncSession, express_sync_id: UUID,
    ) -> tuple[int, int] | None:
        """Ищет в to_telegram, затем в to_express."""

# Пример: infrastructure/s3/storage.py

class S3Storage:
    def __init__(self, client: S3Client, bucket: str): ...

    async def upload(self, key: str, data: bytes, content_type: str) -> None: ...
    def get_download_url(self, key: str) -> str:
        """Возвращает URL нашей HTTP-ручки: /api/files/{key}"""
```

---

## HTTP-ручка для скачивания файлов

> Файлы из TG загружены в S3/Minio. Express получает ссылку вида
> `https://our-host/api/files/{file_uuid}/{filename}`.
> UUID генерируется при загрузке — неугадываемый, авторизации на ручке нет.
> Ручка проксирует из S3.

```
GET /api/files/{file_uuid}/{filename}
```

**Логика:**
1. `s3_key = f"{file_uuid}/{filename}"`
2. Получить объект из S3 через boto3: `s3.get_object(Bucket, Key=s3_key)`
3. Если объект не найден — 404
4. Вернуть `StreamingResponse` с правильным `Content-Type` и `Content-Disposition`

**Размещение:** `express-send-worker` профиль (рядом с отправкой в Express, т.к. Express
будет скачивать файлы по этим ссылкам при получении сообщения).

```python
# infrastructure/http/files_router.py

router = APIRouter(prefix="/api/files")

@router.get("/{file_uuid}/{filename}")
async def download_file(file_uuid: UUID, filename: str):
    s3_key = f"{file_uuid}/{filename}"
    # 1. s3.get_object(Bucket=bucket, Key=s3_key)  -- 404 если нет
    # 2. return StreamingResponse(body, media_type=content_type,
    #        headers={"Content-Disposition": f"attachment; filename={filename}"})
```

---

## Application-слой (use-cases с явными транзакциями)

```
backend/app/
  application/
    tg_poll_service.py        # Use-case: batch TG messages -> DB + Kafka
    express_webhook_service.py # Use-case: batch Express messages -> DB + Kafka
    express_send_service.py   # Use-case: Kafka TO_EXPRESS -> Express API + DB
    tg_send_service.py        # Use-case: Kafka TO_TELEGRAM -> Telegram API + DB
```

```python
# application/tg_poll_service.py

class TgPollService:
    def __init__(self, session_factory, to_express_repo, channel_pair_repo,
                 s3_storage, kafka_broker, settings): ...

    async def handle_batch(self, messages: list[TgIncomingMessage]) -> None:
        """Обработка пачки сообщений из Telegram polling."""

        # 0. Классификация: FORWARD / SYSTEM / SKIP
        classified = [(m, classify_tg_message(m)) for m in messages]
        forward_msgs = [m for m, a in classified if a == TgMessageAction.FORWARD]
        system_msgs = [m for m, a in classified if a == TgMessageAction.SYSTEM]
        # SKIP — игнорируем

        # 0.1. Проверка одобрения группы
        async with self.session_factory() as session:
            channel_pair = await self.channel_pair_repo.find_by_tg_chat_id(
                session, messages[0].tg_chat_id)
            if channel_pair is None:
                channel_pair = await self.channel_pair_repo.create_unapproved(
                    session, tg_chat_id=messages[0].tg_chat_id, name=messages[0].chat_title)
                await session.commit()

        # 0.2. Если НЕ одобрена -> всё в Kafka SYSTEM_CHANNEL
        if not channel_pair.is_approved:
            for msg in forward_msgs + system_msgs:
                await self.kafka_broker.publish_system_channel({
                    "tg_chat_id": msg.tg_chat_id,
                    "tg_chat_title": msg.chat_title,
                    "tg_user_name": msg.sender_name,
                    "content_type": msg.content_type,
                    "reason": "unapproved_channel",
                })
            return

        # 0.3. Одобрена, но SYSTEM-сообщения -> Kafka SYSTEM_CHANNEL
        for msg in system_msgs:
            await self.kafka_broker.publish_system_channel({
                "tg_chat_id": msg.tg_chat_id,
                "tg_chat_title": msg.chat_title,
                "tg_user_name": msg.sender_name,
                "content_type": msg.content_type,
                "reason": "unsupported_type",
            })

        if not forward_msgs:
            return

        # 0.4. Санитизация текста для FORWARD-сообщений
        for msg in forward_msgs:
            msg.body = sanitize_to_express(msg.body)

        # 1. Загрузка файлов в S3 (ВНЕ транзакции, идемпотентно по s3_key)
        for msg in messages:
            if msg.file:
                await self.s3_storage.upload(msg.s3_key, msg.file_data, msg.content_type)

        # 2. ┌─ BEGIN TRANSACTION ─────────────────────────────────────┐
        async with self.session_factory() as session:
            async with session.begin():
                inserted_ids = await self.to_express_repo.bulk_insert(session, records)
                await self.to_express_repo.bulk_insert_files(session, files)
        #    └─ COMMIT ────────────────────────────────────────────────┘

        # 3. Публикация в Kafka (ПОСЛЕ коммита, только для inserted)
        for record_id, event in zip(inserted_ids, events):
            if record_id is not None:  # не дубликат
                await self.kafka_broker.publish_to_express(event)


# application/express_webhook_service.py

class ExpressWebhookService:
    def __init__(self, session_factory, to_telegram_repo, kafka_broker): ...

    async def handle_batch(self, messages: list[ExpressIncomingMessage]) -> None:
        """Обработка пачки сообщений из Express webhook."""

        # 0. Фильтрация: only forward-eligible messages
        messages = [m for m in messages if should_forward_express_message(m)]
        if not messages:
            return

        # 0.1. Санитизация текста
        for msg in messages:
            msg.body = sanitize_to_telegram(msg.body)

        # 1. ┌─ BEGIN TRANSACTION ─────────────────────────────────────┐
        async with self.session_factory() as session:
            async with session.begin():
                inserted_ids = await self.to_telegram_repo.bulk_insert(session, records)
                await self.to_telegram_repo.bulk_insert_files(session, files)
        #    └─ COMMIT ────────────────────────────────────────────────┘

        # 2. Публикация в Kafka (ПОСЛЕ коммита, только для inserted)
        for record_id, event in zip(inserted_ids, events):
            if record_id is not None:
                await self.kafka_broker.publish_to_telegram(event)


# application/express_send_service.py

class ExpressSendService:
    def __init__(self, session_factory, to_express_repo, mapping_queries,
                 employee_repo, express_bot, s3_storage): ...

    async def handle_event(self, event: ToExpressEvent) -> None:
        """Обработка одного события из Kafka TO_EXPRESS."""

        async with self.session_factory() as session:
            # 1. Проверка идемпотентности
            status = await self.to_express_repo.get_status(session, event.record_id)
            if status == MessageStatus.SENT:
                return  # уже отправлено, Kafka offset будет закоммичен

            # 2. Резолв reply
            reply_sync_id = None
            if event.reply_to_tg_message_id:
                reply_sync_id = await self.mapping_queries.find_express_sync_id(
                    session, event.tg_chat_id, event.reply_to_tg_message_id)

            # 3. Форматирование: employee lookup + "[Позиция, Имя]: текст"
            employee = await self.employee_repo.find_by_tg_user_id(session, event.tg_user_id)
            body = format_to_express(employee, event.body)

            # 4. Формирование ссылок на файлы
            file_urls = [self.s3_storage.get_download_url(f.s3_key) for f in event.files]

        # 5. Отправка в Express API (ВНЕ транзакции)
        express_sync_id = await self.express_bot.send_message(
            chat_id=..., body=body, ...)

        # 6. ┌─ BEGIN TRANSACTION ─────────────────────────────────────┐
        async with self.session_factory() as session:
            async with session.begin():
                await self.to_express_repo.mark_sent(
                    session, event.record_id, express_sync_id)
        #    └─ COMMIT ────────────────────────────────────────────────┘

        # 7. Если Express API бросил exception -> не дошли до mark_sent
        #    -> Kafka offset НЕ коммитится -> повторная доставка


# application/tg_send_service.py

class TgSendService:
    def __init__(self, session_factory, to_telegram_repo, mapping_queries,
                 employee_repo, tg_bot): ...

    async def handle_event(self, event: ToTelegramEvent) -> None:
        """Обработка одного события из Kafka TO_TELEGRAM."""

        async with self.session_factory() as session:
            # 1. Проверка идемпотентности
            status = await self.to_telegram_repo.get_status(session, event.record_id)
            if status == MessageStatus.SENT:
                return

            # 2. Резолв reply
            reply_to_message_id = None
            if event.reply_to_express_sync_id:
                result = await self.mapping_queries.find_tg_message(
                    session, event.reply_to_express_sync_id)
                if result:
                    reply_to_message_id = result[0]

            # 3. Форматирование
            employee = await self.employee_repo.find_by_express_huid(
                session, event.express_user_huid)
            body = format_to_telegram(employee, event.body)

            # 4. Определение целевого tg_chat_id из channel_pair
            channel_pair = await self.channel_pair_repo.get(session, event.channel_pair_id)

        # 5. Отправка в Telegram API (ВНЕ транзакции)
        #    new_message / edit_message / delete_message
        tg_msg = await self.tg_bot.send_message(
            chat_id=channel_pair.tg_chat_id, text=body, ...)

        # 6. ┌─ BEGIN TRANSACTION ─────────────────────────────────────┐
        async with self.session_factory() as session:
            async with session.begin():
                await self.to_telegram_repo.mark_sent(
                    session, event.record_id, tg_msg.message_id, tg_msg.chat.id)
        #    └─ COMMIT ────────────────────────────────────────────────┘
```

---

## Настройки (pydantic-settings)

```python
class Settings(BaseSettings):
    # Telegram
    tg_bot_token: str
    tg_proxy_url: str | None = None  # HTTP proxy для TG API

    # Express (pybotx)
    express_bot_id: UUID
    express_cts_url: str
    express_secret_key: str

    # Kafka
    kafka_bootstrap_servers: str
    kafka_topic_to_express: str = "TO_EXPRESS"
    kafka_topic_to_telegram: str = "TO_TELEGRAM"
    kafka_topic_system_channel: str = "SYSTEM_CHANNEL"

    # PostgreSQL
    database_url: str  # postgresql+psycopg://...

    # S3 / Minio
    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str = "tg-express-files"

    # File download
    file_download_base_url: str  # https://our-host — базовый URL для формирования ссылок на файлы

    # System Channel (Express) — сюда идут сообщения из неодобренных TG-групп
    express_system_channel_id: UUID | None = None

    # Admin
    admin_secret_key: str  # для JWT/сессий
```

---

## Замечания по pybotx

1. **Webhook-only** — Express отправляет POST на наш FastAPI-эндпоинт, мы вызываем `bot.async_execute_raw_bot_command(raw_json)`.
2. **Все ID — UUID** (sync_id, chat.id, sender.huid).
3. **Файлы:** входящие — `IncomingMessage.file` (может быть base64 или async). Исходящие — `OutgoingAttachment(content, filename)`.
4. **Reply:** `IncomingMessage.source_sync_id` — sync_id сообщения на которое отвечают.
5. **Edit:** `@collector.event_edit()` — `EventEdit` event.
6. **Delete:** `@collector.event_deleted()` — `EventDeleted` event.
7. **Отправка:** `bot.send_message(bot_id, chat_id, body, ...)` возвращает `UUID` (sync_id отправленного).

---

## Docker Compose сервисы

| Сервис | Образ / Build |
|--------|---------------|
| postgres | postgres:17-alpine |
| kafka | confluentinc/cp-kafka (KRaft, без Zookeeper) |
| minio | minio/minio |
| tg-poll-worker | build: ./backend |
| express-webhook-worker | build: ./backend |
| express-send-worker | build: ./backend |
| tg-send-worker | build: ./backend |
| admin-api | build: ./backend |
