# STEP 2 — План реализации (декомпозиция по шагам)

> Python 3.14, максимальная типизация, атомарность операций.
> Инструменты: `uv` (пакеты), `ruff` (линтер + форматтер), `ty` (type checker).
> Каждый шаг — автономный, проверяемый `ruff check`, `ruff format --check`, `ty check`.

---

## Шаг 0: Подготовка проекта и тулинг

### 0.1. Структура каталогов
```bash
mkdir -p backend/app/{domain,application,infrastructure/{db,kafka,s3,telegram,express,http}}
mkdir -p backend/tests/{unit,integration}
touch backend/app/__init__.py
touch backend/app/domain/__init__.py
touch backend/app/application/__init__.py
touch backend/app/infrastructure/__init__.py
touch backend/app/infrastructure/{db,kafka,s3,telegram,express,http}/__init__.py
```

### 0.2. Настройка pyproject.toml
- `target-version = "py314"` в ruff
- `requires-python = ">=3.14"`
- Добавить секцию `[tool.ty]` если нужны настройки
- Добавить `alembic` в зависимости для миграций

### 0.3. Конфиги линтеров
- `ruff.toml` или секция в `pyproject.toml` — уже настроен
- Проверить что `ty` работает: `uv run ty check`
- Настроить `pre-commit` с ruff + ty

### 0.4. Docker-файлы
- `backend/Dockerfile` — multi-stage: uv install -> slim runtime
- `docker-compose.yml` в корне проекта

**Проверка:** `ruff check backend/app/ && ruff format --check backend/app/` — пустой проект, 0 ошибок.

---

## Шаг 1: Domain layer — модели и enum-ы

### Файл: `backend/app/domain/models.py`

```
Содержимое:
- EventType(str, Enum): new_message, edit_message, delete_message
- MessageStatus(str, Enum): pending, sent, failed
- MessageDirection(str, Enum): tg_to_express, express_to_tg
- TgMessageAction(str, Enum): forward, system, skip
- SystemChannelReason(str, Enum): unapproved_channel, unsupported_type
- ChannelPair (dataclass, frozen=True, slots=True)
- Employee (dataclass, frozen=True, slots=True)
- FileAttachment (dataclass, frozen=True, slots=True)
- S3FileAttachment (dataclass, frozen=True, slots=True)
- ExpressFileAttachment (dataclass, frozen=True, slots=True)
- ToExpressEvent (dataclass, frozen=True, slots=True)
- ToTelegramEvent (dataclass, frozen=True, slots=True)
- SystemChannelEvent (dataclass, frozen=True, slots=True)
```

> Все dataclass — `frozen=True, slots=True` (Python 3.14).
> Все поля типизированы. UUID из `uuid`, не строки.

**Проверка:** `ruff check`, `ty check` — 0 ошибок.

---

## Шаг 2: Settings — pydantic-settings

### Файл: `backend/app/infrastructure/settings.py`

```
Содержимое:
- class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")

    # Telegram
    tg_bot_token: str
    tg_proxy_url: str | None = None

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
    database_url: str

    # S3 / Minio
    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str = "tg-express-files"

    # System Channel
    express_system_channel_id: UUID | None = None

    # Admin
    admin_secret_key: str

    # File download
    file_download_base_url: str  # https://our-host для формирования ссылок
```

### Файл: `backend/.env.example`

**Проверка:** `ruff check`, `ty check`, `uv run python -c "from app.infrastructure.settings import Settings"`.

---

## Шаг 3: Infrastructure — Database (SQLAlchemy ORM)

### 3.1. Файл: `backend/app/infrastructure/db/session.py`
```
- async_engine factory (create_async_engine с psycopg)
- async_session_factory (async_sessionmaker)
- функция get_session() -> AsyncGenerator[AsyncSession]
```

### 3.2. Файл: `backend/app/infrastructure/db/models.py`
```
SQLAlchemy ORM-модели (Mapped, mapped_column):
- ChannelPairModel
  - id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
  - tg_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
  - express_chat_id: Mapped[UUID | None] = mapped_column(unique=True)
  - is_approved: Mapped[bool] = mapped_column(default=False)
  - name: Mapped[str | None] = mapped_column(String(255))
  - created_at: Mapped[datetime] = mapped_column(server_default=func.now())
  - updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

- EmployeeModel
  - id, tg_user_id, express_huid, full_name, position, created_at, updated_at
  - CheckConstraint("tg_user_id IS NOT NULL OR express_huid IS NOT NULL")

- ToExpressModel
  - id, channel_pair_id (FK), tg_message_id, tg_chat_id, tg_user_id
  - tg_media_group_id, express_sync_id, reply_to_tg_message_id
  - event_type (String(31)), status (String(15))
  - UniqueConstraint("tg_chat_id", "tg_message_id", "event_type")
  - Partial indexes через Index(..., postgresql_where=...)

- ToTelegramModel
  - id, channel_pair_id (FK), express_sync_id, express_chat_id, express_user_huid
  - tg_message_id, tg_chat_id, reply_to_express_sync_id
  - event_type, status
  - UniqueConstraint("express_sync_id", "event_type")

- MessageFileModel
  - id, direction (String(15)), message_record_id
  - file_type, file_name, file_content_type, file_size
  - s3_key, express_file_id, express_file_url, express_file_hash
  - created_at
```

### 3.3. Alembic init
```bash
cd backend && uv run alembic init alembic
```
- Настроить `alembic/env.py` с async engine
- Создать initial migration: `uv run alembic revision --autogenerate -m "initial"`
- Проверить SQL: `uv run alembic upgrade head` (на локальном postgres)

**Проверка:** `ruff check`, `ty check`, миграция применяется без ошибок.

---

## Шаг 4: Infrastructure — Repositories (DB)

### 4.1. Файл: `backend/app/infrastructure/db/channel_pair_repo.py`
```
class ChannelPairRepo:
    async def find_by_tg_chat_id(session, tg_chat_id: int) -> ChannelPair | None
    async def get(session, pair_id: UUID) -> ChannelPair
    async def create_unapproved(session, tg_chat_id: int, name: str | None) -> ChannelPair
    async def approve(session, pair_id: UUID, express_chat_id: UUID) -> None
    async def list_all(session) -> list[ChannelPair]
    async def find_by_express_chat_id(session, express_chat_id: UUID) -> ChannelPair | None
```

### 4.2. Файл: `backend/app/infrastructure/db/employee_repo.py`
```
class EmployeeRepo:
    async def find_by_tg_user_id(session, tg_user_id: int) -> Employee | None
    async def find_by_express_huid(session, express_huid: UUID) -> Employee | None
    async def create(session, ...) -> Employee
    async def update(session, employee_id: UUID, ...) -> None
    async def list_all(session) -> list[Employee]
```

### 4.3. Файл: `backend/app/infrastructure/db/to_express_repo.py`
```
class ToExpressRepo:
    async def bulk_insert(session, records: list[ToExpressInsert]) -> list[UUID | None]
    async def bulk_insert_files(session, files: list[MessageFileInsert]) -> None
    async def get_status(session, record_id: UUID) -> MessageStatus
    async def mark_sent(session, record_id: UUID, express_sync_id: UUID) -> None
```

> `ToExpressInsert`, `MessageFileInsert` — TypedDict или dataclass для insert payload.

### 4.4. Файл: `backend/app/infrastructure/db/to_telegram_repo.py`
```
class ToTelegramRepo:
    async def bulk_insert(session, records: list[ToTelegramInsert]) -> list[UUID | None]
    async def bulk_insert_files(session, files: list[MessageFileInsert]) -> None
    async def get_status(session, record_id: UUID) -> MessageStatus
    async def mark_sent(session, record_id: UUID, tg_message_id: int, tg_chat_id: int) -> None
```

### 4.5. Файл: `backend/app/infrastructure/db/mapping_queries.py`
```
class MappingQueries:
    async def find_express_sync_id(session, tg_chat_id: int, tg_message_id: int) -> UUID | None
    async def find_tg_message(session, express_sync_id: UUID) -> tuple[int, int] | None
```

**Проверка:** `ruff check`, `ty check`. Unit-тесты с in-memory или testcontainers postgres.

---

## Шаг 5: Infrastructure — S3 Storage

### Файл: `backend/app/infrastructure/s3/storage.py`
```
class S3Storage:
    def __init__(self, client: S3Client, bucket: str, base_url: str) -> None

    async def upload(self, key: str, data: bytes, content_type: str) -> None
    async def download(self, key: str) -> tuple[bytes, str]  # (data, content_type)
    async def get_object_stream(self, key: str) -> StreamingBody  # для StreamingResponse
    def get_download_url(self, s3_key: str) -> str
        # return f"{self.base_url}/api/files/{s3_key}"

    @staticmethod
    def generate_s3_key(filename: str) -> str:
        # return f"{uuid4()}/{filename}"
```

> boto3 — синхронный. Обернуть в `asyncio.to_thread()` или использовать напрямую
> (boto3 работает быстро для small objects). Явно типизировать через `mypy-boto3-s3`.

**Проверка:** `ruff check`, `ty check`. Unit-тест с mock S3 или Minio testcontainer.

---

## Шаг 6: Infrastructure — Kafka (FastStream)

### Файл: `backend/app/infrastructure/kafka/broker.py`
```
- ConfluentBroker setup
- Три publisher-а:
    to_express_publisher: AsyncAPIPublisher  (topic=TO_EXPRESS)
    to_telegram_publisher: AsyncAPIPublisher (topic=TO_TELEGRAM)
    system_channel_publisher: AsyncAPIPublisher (topic=SYSTEM_CHANNEL)

class KafkaBroker:
    async def publish_to_express(self, event: ToExpressEvent, key: str) -> None
    async def publish_to_telegram(self, event: ToTelegramEvent, key: str) -> None
    async def publish_system_channel(self, event: SystemChannelEvent, key: str) -> None
```

> Сериализация: `pydantic` или `dataclasses-json`. Key = str(chat_id).

**Проверка:** `ruff check`, `ty check`.

---

## Шаг 7: Application — Утилиты (sanitize, filter, splitter, formatter)

### 7.1. Файл: `backend/app/application/message_filter.py`
```
FORWARD_CONTENT_TYPES: frozenset[str]
SKIP_CONTENT_TYPES: frozenset[str]

def classify_tg_message(content_type: str) -> TgMessageAction
def should_forward_express_message(has_sticker: bool, has_location: bool) -> bool
```

> Принимают примитивы, не aiogram/pybotx объекты — легко тестировать.

### 7.2. Файл: `backend/app/application/sanitize.py`
```
# --- Telegram formatting removal (TG -> Express) ---

def strip_tg_formatting(text: str, entities: list[TgEntityDTO] | None) -> str:
    """Удаляет форматирование Telegram, используя entities (offset+length).
    Поддерживаемые форматы (все три parse_mode Telegram):

    MarkdownV2: *bold*, _italic_, __underline__, ~strikethrough~,
                ||spoiler||, `inline code`, ```pre block```, [text](url)
    Markdown v1: *bold*, _italic_, `code`, ```pre```, [text](url)
    HTML: <b>, <strong>, <i>, <em>, <u>, <ins>, <s>, <strike>, <del>,
          <code>, <pre>, <a href="...">, <tg-spoiler>, <blockquote>

    Подход: aiogram предоставляет message.entities — список MessageEntity
    с type, offset, length. Извлекаем plain text, вырезая разметку.
    Для ссылок [text](url) — оставляем text, удаляем url.
    """

def strip_express_formatting(text: str) -> str:
    """Удаляет HTML-подобную разметку Express."""

def strip_emoji(text: str) -> str:
    """Удаляет все Unicode emoji (regex по Unicode blocks)."""

def sanitize_to_express(text: str | None, entities: list[TgEntityDTO] | None = None) -> str | None:
    """1. strip_tg_formatting  2. strip_emoji  3. strip()  4. None если пусто"""

def sanitize_to_telegram(text: str | None) -> str | None:
    """1. strip_express_formatting  2. strip_emoji  3. strip()  4. None если пусто"""
```

> **TgEntityDTO** — упрощённый DTO из aiogram `MessageEntity` (type, offset, length, url).
> Передаётся из infrastructure через `TgIncomingDTO.entities`.

### 7.3. Файл: `backend/app/application/message_formatter.py`
```
def format_header_to_express(employee: Employee | None, tg_sender_name: str) -> str
    # "[Позиция, Имя]:" или "[TG first_name last_name]:"

def format_header_to_telegram(employee: Employee | None) -> str | None
    # "[Позиция]:" или None

def format_attachments_block(file_urls: list[str]) -> str
    # "Вложения:\n1. url1\n2. url2"
```

### 7.4. Файл: `backend/app/application/message_splitter.py`
```
MAX_MESSAGE_LENGTH: Final[int] = 4096

def split_to_express(header: str, body: str | None, attachments_block: str | None) -> list[str]
def split_to_telegram(header: str | None, body: str | None) -> list[str]
```

> Разбиение по `\n`, затем по пробелам. Заголовок в первом, вложения в последнем.

**Проверка:** `ruff check`, `ty check`. **Обязательно unit-тесты** для каждой функции — это чистая логика, 100% покрытие.

---

## Шаг 8: Application — Service: TgPollService

### Файл: `backend/app/application/tg_poll_service.py`
```
class TgPollService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        to_express_repo: ToExpressRepo,
        channel_pair_repo: ChannelPairRepo,
        s3_storage: S3Storage,
        kafka_broker: KafkaBroker,
        settings: Settings,
    ) -> None

    async def handle_batch(self, messages: list[TgIncomingDTO]) -> None
        # 0. classify -> FORWARD / SYSTEM / SKIP
        # 0.1. lookup/create channel_pair
        # 0.2. unapproved -> publish SYSTEM_CHANNEL, return
        # 0.3. SYSTEM msgs -> publish SYSTEM_CHANNEL
        # 0.4. sanitize FORWARD msgs
        # 1. upload files to S3
        # 2. BEGIN TRANSACTION -> bulk_insert + bulk_insert_files -> COMMIT
        # 3. publish to Kafka TO_EXPRESS
```

### Файл: `backend/app/application/dto.py`
```
@dataclass(frozen=True, slots=True)
class TgEntityDTO:
    """Упрощённый MessageEntity из aiogram для передачи в sanitize."""
    type: str                  # "bold", "italic", "code", "pre", "text_link", "url", etc.
    offset: int
    length: int
    url: str | None = None     # для type="text_link"

@dataclass(frozen=True, slots=True)
class TgIncomingDTO:
    tg_message_id: int
    tg_chat_id: int
    tg_user_id: int
    content_type: str
    body: str | None
    entities: tuple[TgEntityDTO, ...] | None  # форматирование текста (MarkdownV2/HTML/Markdown)
    chat_title: str | None
    sender_name: str
    reply_to_message_id: int | None
    media_group_id: str | None
    file_id: str | None        # TG file_id для скачивания
    file_name: str | None
    file_content_type: str | None
    file_size: int | None
    # Contact fields
    contact_name: str | None
    contact_phone: str | None

@dataclass(frozen=True, slots=True)
class ExpressIncomingDTO:
    sync_id: UUID
    chat_id: UUID
    user_huid: UUID
    body: str | None
    source_sync_id: UUID | None   # reply
    has_file: bool
    file_type: str | None
    file_name: str | None
    file_content_type: str | None
    has_sticker: bool
    has_location: bool
    has_contact: bool
    contact_name: str | None
    link_url: str | None
```

> DTO — промежуточные объекты между infrastructure (aiogram/pybotx) и application.
> Не зависят от внешних библиотек.

**Проверка:** `ruff check`, `ty check`.

---

## Шаг 9: Application — Service: ExpressWebhookService

### Файл: `backend/app/application/express_webhook_service.py`
```
class ExpressWebhookService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        to_telegram_repo: ToTelegramRepo,
        channel_pair_repo: ChannelPairRepo,
        kafka_broker: KafkaBroker,
    ) -> None

    async def handle_batch(self, messages: list[ExpressIncomingDTO]) -> None
        # 0. filter: should_forward_express_message
        # 0.1. sanitize
        # 0.2. lookup channel_pair by express_chat_id (для получения channel_pair_id)
        # 1. BEGIN TRANSACTION -> bulk_insert + bulk_insert_files -> COMMIT
        # 2. publish to Kafka TO_TELEGRAM
```

**Проверка:** `ruff check`, `ty check`.

---

## Шаг 10: Application — Service: ExpressSendService

### Файл: `backend/app/application/express_send_service.py`
```
class ExpressSendService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        to_express_repo: ToExpressRepo,
        mapping_queries: MappingQueries,
        employee_repo: EmployeeRepo,
        s3_storage: S3Storage,
        settings: Settings,
    ) -> None

    async def handle_event(self, event: ToExpressEvent, send_fn: SendToExpressFn) -> None
        # 1. idempotency check
        # 2. resolve reply
        # 3. format header + body + attachments
        # 4. split_to_express() if > 4096
        # 5. send via send_fn (injected, не прямой вызов pybotx)
        # 6. BEGIN TRANSACTION -> mark_sent -> COMMIT

    async def handle_system_channel(self, event: SystemChannelEvent, send_fn: SendToExpressFn) -> None
        # format "[TG: {title}] {user}: {content_type}"
        # send to system_channel_id
        # no DB writes
```

> `send_fn` — callable, чтобы service не зависел от pybotx напрямую.

**Проверка:** `ruff check`, `ty check`.

---

## Шаг 11: Application — Service: TgSendService

### Файл: `backend/app/application/tg_send_service.py`
```
class TgSendService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        to_telegram_repo: ToTelegramRepo,
        mapping_queries: MappingQueries,
        employee_repo: EmployeeRepo,
        channel_pair_repo: ChannelPairRepo,
    ) -> None

    async def handle_event(self, event: ToTelegramEvent, send_fn: SendToTelegramFn) -> None
        # 1. idempotency check
        # 2. resolve reply
        # 3. format header + body
        # 4. split_to_telegram() if > 4096
        # 5. dispatch by event_type: new_message / edit_message / delete_message
        # 6. BEGIN TRANSACTION -> mark_sent -> COMMIT
```

**Проверка:** `ruff check`, `ty check`.

---

## Шаг 12: Infrastructure — Telegram bot (aiogram)

### Файл: `backend/app/infrastructure/telegram/bot.py`
```
def create_tg_bot(settings: Settings) -> Bot:
    # proxy setup через AiohttpSession если settings.tg_proxy_url
    # return Bot(token=..., session=session)

def create_dispatcher() -> Dispatcher:
    # Dispatcher с router-ами
```

### Файл: `backend/app/infrastructure/telegram/converters.py`
```
def message_to_dto(message: aiogram.types.Message) -> TgIncomingDTO
    # Конвертация aiogram Message -> TgIncomingDTO
    # Извлечение file_id, content_type, contact fields, etc.
```

**Проверка:** `ruff check`, `ty check`.

---

## Шаг 13: Infrastructure — Express bot (pybotx)

### Файл: `backend/app/infrastructure/express/bot.py`
```
def create_express_bot(settings: Settings) -> Bot:
    # BotAccountWithSecret, HandlerCollector
    # return Bot(collectors=[collector], bot_accounts=[account])

collector = HandlerCollector()

@collector.default_message_handler()
async def handle_message(message: IncomingMessage, bot: Bot) -> None:
    # Конвертировать в ExpressIncomingDTO
    # Вызвать ExpressWebhookService.handle_batch([dto])
```

### Файл: `backend/app/infrastructure/express/converters.py`
```
def incoming_to_dto(message: IncomingMessage) -> ExpressIncomingDTO
```

### Файл: `backend/app/infrastructure/express/handlers.py`
```
# event_edit, event_deleted handlers
# Конвертация в DTO с event_type=edit_message / delete_message
```

**Проверка:** `ruff check`, `ty check`.

---

## Шаг 14: Infrastructure — HTTP (FastAPI routers)

### 14.1. Файл: `backend/app/infrastructure/http/files_router.py`
```
router = APIRouter(prefix="/api/files")

@router.get("/{file_uuid}/{filename}")
async def download_file(file_uuid: UUID, filename: str) -> StreamingResponse
```

### 14.2. Файл: `backend/app/infrastructure/http/admin_router.py`
```
router = APIRouter(prefix="/api/admin")

# Channel pairs CRUD
POST   /channel-pairs/{pair_id}/approve  -> approve (create Express chat + update DB)
GET    /channel-pairs                     -> list
GET    /channel-pairs/{pair_id}           -> get

# Employees CRUD
POST   /employees                         -> create
PUT    /employees/{employee_id}           -> update
GET    /employees                         -> list
DELETE /employees/{employee_id}           -> delete
```

### 14.3. Файл: `backend/app/infrastructure/http/express_webhook_router.py`
```
router = APIRouter()

@router.post("/express/webhook")
async def express_webhook(request: Request) -> JSONResponse:
    # raw_body = await request.json()
    # await bot.async_execute_raw_bot_command(raw_body, ...)
    # return build_command_accepted_response()
```

**Проверка:** `ruff check`, `ty check`.

---

## Шаг 15: Entrypoints — 5 профилей запуска

### 15.1. Файл: `backend/app/workers/tg_poll_worker.py`
```
async def main() -> None:
    # 1. Init: settings, db session, repos, s3, kafka, aiogram bot
    # 2. Register message handler -> TgPollService.handle_batch
    # 3. dp.start_polling(bot)
```

### 15.2. Файл: `backend/app/workers/express_webhook_worker.py`
```
async def main() -> None:
    # 1. Init: settings, db session, repos, kafka, pybotx bot
    # 2. FastAPI app with express_webhook_router
    # 3. pybotx lifespan_wrapper
    # 4. uvicorn.run(app)
```

### 15.3. Файл: `backend/app/workers/express_send_worker.py`
```
async def main() -> None:
    # 1. Init: settings, db session, repos, s3, pybotx bot, kafka consumer
    # 2. FastStream app with consumer TO_EXPRESS + SYSTEM_CHANNEL
    # 3. FastAPI app with files_router (для скачивания файлов Express-ом)
    # 4. Запуск обоих: faststream + uvicorn
```

### 15.4. Файл: `backend/app/workers/tg_send_worker.py`
```
async def main() -> None:
    # 1. Init: settings, db session, repos, aiogram bot, kafka consumer
    # 2. FastStream app with consumer TO_TELEGRAM
```

### 15.5. Файл: `backend/app/workers/admin_api.py`
```
async def main() -> None:
    # 1. Init: settings, db session, repos, pybotx bot (для create_chat)
    # 2. FastAPI app with admin_router
    # 3. uvicorn.run(app)
```

**Проверка:** `ruff check`, `ty check`. Каждый запускается без ошибок (с mock-зависимостями).

---

## Шаг 16: Docker Compose

### Файл: `docker-compose.yml`
```yaml
services:
  postgres:
    image: postgres:17-alpine
    environment:
      POSTGRES_DB: tg_express
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
    ports: ["5432:5432"]
    volumes: [postgres_data:/var/lib/postgresql/data]

  kafka:
    image: confluentinc/cp-kafka:7.9.0
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      CLUSTER_ID: "tg-express-local"
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    ports: ["9092:9092"]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports: ["9000:9000", "9001:9001"]
    volumes: [minio_data:/data]

  tg-poll-worker:
    build: { context: ./backend }
    command: ["uv", "run", "python", "-m", "app.workers.tg_poll_worker"]
    env_file: .env
    depends_on: [postgres, kafka, minio]

  express-webhook-worker:
    build: { context: ./backend }
    command: ["uv", "run", "python", "-m", "app.workers.express_webhook_worker"]
    env_file: .env
    ports: ["8001:8000"]
    depends_on: [postgres, kafka]

  express-send-worker:
    build: { context: ./backend }
    command: ["uv", "run", "python", "-m", "app.workers.express_send_worker"]
    env_file: .env
    ports: ["8002:8000"]
    depends_on: [postgres, kafka, minio]

  tg-send-worker:
    build: { context: ./backend }
    command: ["uv", "run", "python", "-m", "app.workers.tg_send_worker"]
    env_file: .env
    depends_on: [postgres, kafka]

  admin-api:
    build: { context: ./backend }
    command: ["uv", "run", "python", "-m", "app.workers.admin_api"]
    env_file: .env
    ports: ["8000:8000"]
    depends_on: [postgres]

volumes:
  postgres_data:
  minio_data:
```

### Файл: `backend/Dockerfile`
```dockerfile
FROM python:3.14-slim AS base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
```

**Проверка:** `docker compose build`, `docker compose up -d postgres kafka minio`, миграция проходит.

---

## Шаг 17: Тесты

### 17.1. Unit-тесты (без внешних зависимостей)
```
tests/unit/
  test_message_filter.py      # classify_tg_message, should_forward_express_message
  test_sanitize.py            # strip_tg_formatting, strip_express_formatting, strip_emoji, sanitize_*
  test_message_formatter.py   # format_header_*, format_attachments_block
  test_message_splitter.py    # split_to_express, split_to_telegram (граничные случаи 4096)
  test_models.py              # dataclass creation, enum values
```

### 17.2. Integration-тесты (с postgres, kafka, minio)
```
tests/integration/
  conftest.py                 # fixtures: db session, kafka broker, minio client
  test_to_express_repo.py     # bulk_insert, idempotency, mark_sent
  test_to_telegram_repo.py    # bulk_insert, idempotency, mark_sent
  test_mapping_queries.py     # find_express_sync_id, find_tg_message
  test_channel_pair_repo.py   # create_unapproved, approve
  test_tg_poll_service.py     # полный flow: classify -> DB -> Kafka
  test_express_send_service.py # полный flow: Kafka event -> send -> mark_sent
```

**Проверка:** `uv run pytest tests/unit/` — 0 fail. `uv run pytest tests/integration/` (с docker compose up).

---

## Шаг 18: CI-проверки (pre-commit + Makefile)

### Файл: `Makefile`
```makefile
.PHONY: lint format typecheck test

lint:
	cd backend && uv run ruff check app/ tests/

format:
	cd backend && uv run ruff format --check app/ tests/

typecheck:
	cd backend && uv run ty check

test:
	cd backend && uv run pytest tests/unit/

test-all:
	cd backend && uv run pytest

check: lint format typecheck test
```

### Файл: `.pre-commit-config.yaml`
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.5
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

**Проверка:** `make check` — 0 ошибок.

---

## Порядок выполнения (зависимости)

```
Шаг 0  (структура, тулинг)
  ↓
Шаг 1  (domain models)
  ↓
Шаг 2  (settings)
  ↓
Шаг 3  (DB ORM + alembic)
  ↓
Шаг 4  (repositories)          Шаг 5  (S3 storage)       Шаг 6  (Kafka broker)
  ↓                               ↓                         ↓
Шаг 7  (sanitize, filter, splitter, formatter)  ←──────────────────
  ↓
Шаг 8  (TgPollService)
Шаг 9  (ExpressWebhookService)
Шаг 10 (ExpressSendService)
Шаг 11 (TgSendService)
  ↓
Шаг 12 (TG bot infra)          Шаг 13 (Express bot infra)   Шаг 14 (HTTP routers)
  ↓                               ↓                            ↓
Шаг 15 (entrypoints — 5 workers)
  ↓
Шаг 16 (Docker Compose)
  ↓
Шаг 17 (тесты)
  ↓
Шаг 18 (CI / pre-commit)
```

> Шаги 4, 5, 6 — параллельны.
> Шаги 8–11 — параллельны (но зависят от 4–7).
> Шаги 12, 13, 14 — параллельны.
