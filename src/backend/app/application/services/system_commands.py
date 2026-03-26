"""System channel command handler for Express bot."""

from __future__ import annotations

import csv
import io
import logging
from typing import TYPE_CHECKING
from uuid import UUID

from pybotx.models.attachments import OutgoingAttachment

from app.application.services.approve_service import approve_channel_pair

if TYPE_CHECKING:
    from pybotx import Bot
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.infrastructure.db.channel_pair_repo import ChannelPairRepo
    from app.infrastructure.db.employee_repo import EmployeeRepo
    from app.infrastructure.s3.storage import S3Storage

logger = logging.getLogger(__name__)

MAX_POSITION_LENGTH = 48
MAX_FULLNAME_LENGTH = 128


class SystemCommandHandler:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        channel_pair_repo: ChannelPairRepo,
        employee_repo: EmployeeRepo,
        s3_storage: S3Storage,
        express_bot: Bot,
        bot_id: UUID,
        system_channel_id: UUID,
        group_prefix: str,
        admin_huids: list[UUID],
        wait_callback: bool = False,
    ) -> None:
        self._session_factory = session_factory
        self._channel_pair_repo = channel_pair_repo
        self._employee_repo = employee_repo
        self._s3_storage = s3_storage
        self._bot = express_bot
        self._bot_id = bot_id
        self._system_channel_id = system_channel_id
        self._group_prefix = group_prefix
        self._admin_huids = admin_huids
        self._wait_callback = wait_callback

    async def handle(self, body: str) -> None:
        """Handle a message from the system channel."""
        text = body.strip()
        if not text.startswith("/"):
            return

        cmd, _, rest = text.partition(" ")
        rest = rest.strip()

        match cmd:
            case "/approve":
                await self._cmd_approve(rest)
            case "/express_position":
                await self._cmd_express_position(rest)
            case "/express_fullname":
                await self._cmd_express_fullname(rest)
            case "/telegram_position":
                await self._cmd_telegram_position(rest)
            case "/telegram_fullname":
                await self._cmd_telegram_fullname(rest)
            case "/group_pair_list":
                await self._cmd_group_pair_list()
            case "/users_list":
                await self._cmd_users_list()
            case "/file_download":
                await self._cmd_file_download(rest)
            case _:
                await self._reply(f"Неизвестная команда: {cmd}")

    async def _reply(self, text: str) -> None:
        await self._bot.send_message(
            bot_id=self._bot_id,
            chat_id=self._system_channel_id,
            body=text,
            wait_callback=self._wait_callback,
        )

    async def _reply_file(self, text: str, *, content: bytes, filename: str) -> None:
        await self._bot.send_message(
            bot_id=self._bot_id,
            chat_id=self._system_channel_id,
            body=text,
            file=OutgoingAttachment(content=content, filename=filename),
            wait_callback=self._wait_callback,
        )

    # --- /approve ---

    async def _cmd_approve(self, args: str) -> None:
        if not args:
            await self._reply("Неверный формат: /approve tg_chat_id")
            return

        try:
            tg_chat_id = int(args.split(maxsplit=1)[0])
        except ValueError:
            await self._reply("Неверный формат: /approve tg_chat_id")
            return

        async with self._session_factory() as session, session.begin():
            pair = await self._channel_pair_repo.find_by_tg_chat_id(session, tg_chat_id)
            if pair is None:
                await self._reply(f"Группа с tg_chat_id={tg_chat_id} не найдена")
                return

            if pair.is_approved:
                await self._reply(f"Группа {pair.name} уже одобрена")
                return

            result = await approve_channel_pair(
                session=session,
                channel_pair_repo=self._channel_pair_repo,
                express_bot=self._bot,
                bot_id=self._bot_id,
                pair_id=pair.id,
                group_prefix=self._group_prefix,
                admin_huids=self._admin_huids,
            )

        if result is not None:
            await self._reply(f"Группа {result.name} одобрена, Express chat_id={result.express_chat_id}")
        else:
            await self._reply("Группа уже была одобрена (concurrent)")

    # --- /express_position ---

    async def _cmd_express_position(self, args: str) -> None:
        if not args:
            await self._reply("Неверный формат: /express_position express_huid position")
            return

        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            await self._reply("Неверный формат: /express_position express_huid position")
            return

        try:
            express_huid = UUID(parts[0])
        except ValueError:
            await self._reply("Неверный формат: /express_position express_huid position")
            return

        position = parts[1].strip()
        if len(position) > MAX_POSITION_LENGTH:
            await self._reply(f"Position не может быть длиннее {MAX_POSITION_LENGTH} символов")
            return

        async with self._session_factory() as session, session.begin():
            employee = await self._employee_repo.find_by_express_huid(session, express_huid)
            if employee is None:
                await self._reply(f"Пользователь с express_huid={express_huid} не найден")
                return
            await self._employee_repo.update(session, employee.id, position=position)

        await self._reply(f"Position для {express_huid} установлен: {position}")

    # --- /express_fullname ---

    async def _cmd_express_fullname(self, args: str) -> None:
        if not args:
            await self._reply("Неверный формат: /express_fullname express_huid full_name")
            return

        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            await self._reply("Неверный формат: /express_fullname express_huid full_name")
            return

        try:
            express_huid = UUID(parts[0])
        except ValueError:
            await self._reply("Неверный формат: /express_fullname express_huid full_name")
            return

        full_name = parts[1].strip()
        if len(full_name) > MAX_FULLNAME_LENGTH:
            await self._reply(f"Full Name не может быть длиннее {MAX_FULLNAME_LENGTH} символов")
            return

        async with self._session_factory() as session, session.begin():
            employee = await self._employee_repo.find_by_express_huid(session, express_huid)
            if employee is None:
                await self._reply(f"Пользователь с express_huid={express_huid} не найден")
                return
            await self._employee_repo.update(session, employee.id, full_name=full_name)

        await self._reply(f"Full Name для {express_huid} установлен: {full_name}")

    # --- /telegram_position ---

    async def _cmd_telegram_position(self, args: str) -> None:
        if not args:
            await self._reply("Неверный формат: /telegram_position tg_user_id position")
            return

        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            await self._reply("Неверный формат: /telegram_position tg_user_id position")
            return

        try:
            tg_user_id = int(parts[0])
        except ValueError:
            await self._reply("Неверный формат: /telegram_position tg_user_id position")
            return

        position = parts[1].strip()
        if len(position) > MAX_POSITION_LENGTH:
            await self._reply(f"Position не может быть длиннее {MAX_POSITION_LENGTH} символов")
            return

        async with self._session_factory() as session, session.begin():
            employee = await self._employee_repo.find_by_tg_user_id(session, tg_user_id)
            if employee is None:
                await self._reply(f"Пользователь с tg_user_id={tg_user_id} не найден")
                return
            await self._employee_repo.update(session, employee.id, position=position)

        await self._reply(f"Position для tg_user_id={tg_user_id} установлен: {position}")

    # --- /telegram_fullname ---

    async def _cmd_telegram_fullname(self, args: str) -> None:
        if not args:
            await self._reply("Неверный формат: /telegram_fullname tg_user_id full_name")
            return

        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            await self._reply("Неверный формат: /telegram_fullname tg_user_id full_name")
            return

        try:
            tg_user_id = int(parts[0])
        except ValueError:
            await self._reply("Неверный формат: /telegram_fullname tg_user_id full_name")
            return

        full_name = parts[1].strip()
        if len(full_name) > MAX_FULLNAME_LENGTH:
            await self._reply(f"Full Name не может быть длиннее {MAX_FULLNAME_LENGTH} символов")
            return

        async with self._session_factory() as session, session.begin():
            employee = await self._employee_repo.find_by_tg_user_id(session, tg_user_id)
            if employee is None:
                await self._reply(f"Пользователь с tg_user_id={tg_user_id} не найден")
                return
            await self._employee_repo.update(session, employee.id, full_name=full_name)

        await self._reply(f"Full Name для tg_user_id={tg_user_id} установлен: {full_name}")

    # --- /group_pair_list ---

    async def _cmd_group_pair_list(self) -> None:
        async with self._session_factory() as session, session.begin():
            pairs = await self._channel_pair_repo.list_all(session)

        if not pairs:
            await self._reply("Список групп пуст")
            return

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "name", "tg_chat_id", "express_chat_id", "is_approved"])
        for p in pairs:
            express_id = str(p.express_chat_id) if p.express_chat_id else ""
            writer.writerow([str(p.id), p.name or "", p.tg_chat_id, express_id, p.is_approved])

        csv_bytes = buf.getvalue().encode("utf-8")
        await self._reply_file(f"Список групп ({len(pairs)})", content=csv_bytes, filename="group_pairs.csv")

    # --- /users_list ---

    async def _cmd_users_list(self) -> None:
        async with self._session_factory() as session, session.begin():
            employees = await self._employee_repo.list_all(session)

        if not employees:
            await self._reply("Список пользователей пуст")
            return

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "tg_user_id", "tg_name", "express_huid", "express_name", "full_name", "position"])
        for e in employees:
            writer.writerow(
                [
                    str(e.id),
                    e.tg_user_id or "",
                    e.tg_name or "",
                    str(e.express_huid) if e.express_huid else "",
                    e.express_name or "",
                    e.full_name or "",
                    e.position or "",
                ]
            )

        csv_bytes = buf.getvalue().encode("utf-8")
        await self._reply_file(f"Список пользователей ({len(employees)})", content=csv_bytes, filename="employees.csv")

    # --- /file_download ---

    async def _cmd_file_download(self, args: str) -> None:
        if not args:
            await self._reply("Неверный формат: /file_download UUID")
            return

        s3_key = args.split(maxsplit=1)[0]

        try:
            metadata = await self._s3_storage.head_object(s3_key)
        except Exception:
            await self._reply(f"Файл {s3_key} не найден в S3")
            return

        filename = metadata.get("filename", s3_key)
        file_data, _ = await self._s3_storage.download(s3_key)
        await self._reply_file(f"Файл: {filename}", content=file_data, filename=filename)
