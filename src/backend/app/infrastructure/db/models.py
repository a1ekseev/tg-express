from __future__ import annotations

from datetime import datetime  # noqa: TC003 - required at runtime for SQLAlchemy Mapped types
from uuid import UUID, uuid4  # noqa: TC003 - required at runtime for SQLAlchemy mapped_column defaults

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column  # noqa: TC002 - Mapped required at runtime

_TZ = DateTime(timezone=True)


class Base(DeclarativeBase):
    pass


class ChannelPairModel(Base):
    __tablename__ = "channel_pairs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tg_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    express_chat_id: Mapped[UUID | None] = mapped_column(unique=True, default=None)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    name: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now(), onupdate=func.now())


class EmployeeModel(Base):
    __tablename__ = "employees"
    __table_args__ = (CheckConstraint("tg_user_id IS NOT NULL OR express_huid IS NOT NULL", name="ck_employee_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tg_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, default=None)
    express_huid: Mapped[UUID | None] = mapped_column(unique=True, default=None)
    full_name: Mapped[str | None] = mapped_column(String(255), default=None)
    position: Mapped[str | None] = mapped_column(String(255), default=None)
    tg_name: Mapped[str | None] = mapped_column(String(255), default=None)
    express_name: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now(), onupdate=func.now())


class ToExpressModel(Base):
    __tablename__ = "to_express"
    __table_args__ = (
        UniqueConstraint("tg_chat_id", "tg_message_id", "event_type", name="uq_to_express_idempotency"),
        Index("ix_to_express_channel_pair_id", "channel_pair_id"),
        Index("ix_to_express_express_sync_id", "express_sync_id"),
        Index(
            "ix_to_express_media_group",
            "tg_media_group_id",
            postgresql_where="tg_media_group_id IS NOT NULL",
        ),
        Index(
            "ix_to_express_status_pending",
            "status",
            postgresql_where="status = 'pending'",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    channel_pair_id: Mapped[UUID] = mapped_column(ForeignKey("channel_pairs.id"))
    tg_message_id: Mapped[int] = mapped_column(BigInteger)
    tg_chat_id: Mapped[int] = mapped_column(BigInteger)
    tg_user_id: Mapped[int] = mapped_column(BigInteger)
    tg_media_group_id: Mapped[str | None] = mapped_column(String(255), default=None)
    express_sync_id: Mapped[UUID | None] = mapped_column(default=None)
    reply_to_tg_message_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    event_type: Mapped[str] = mapped_column(String(31), default="new_message")
    status: Mapped[str] = mapped_column(String(15), default="pending")
    created_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now(), onupdate=func.now())


class ToTelegramModel(Base):
    __tablename__ = "to_telegram"
    __table_args__ = (
        UniqueConstraint("express_sync_id", "event_type", name="uq_to_telegram_idempotency"),
        Index("ix_to_telegram_channel_pair_id", "channel_pair_id"),
        Index("ix_to_telegram_tg_message", "tg_chat_id", "tg_message_id"),
        Index(
            "ix_to_telegram_status_pending",
            "status",
            postgresql_where="status = 'pending'",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    channel_pair_id: Mapped[UUID] = mapped_column(ForeignKey("channel_pairs.id"))
    express_sync_id: Mapped[UUID] = mapped_column()
    express_chat_id: Mapped[UUID] = mapped_column()
    express_user_huid: Mapped[UUID] = mapped_column()
    tg_message_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    tg_chat_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    reply_to_express_sync_id: Mapped[UUID | None] = mapped_column(default=None)
    event_type: Mapped[str] = mapped_column(String(31), default="new_message")
    status: Mapped[str] = mapped_column(String(15), default="pending")
    created_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now(), onupdate=func.now())


class MessageFileModel(Base):
    __tablename__ = "message_files"
    __table_args__ = (
        Index("ix_message_files_record", "message_record_id", "direction"),
        Index(
            "ix_message_files_s3_key",
            "s3_key",
            postgresql_where="s3_key IS NOT NULL",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    direction: Mapped[str] = mapped_column(String(15))
    message_record_id: Mapped[UUID] = mapped_column()
    file_type: Mapped[str] = mapped_column(String(31))
    file_name: Mapped[str | None] = mapped_column(String(255), default=None)
    file_content_type: Mapped[str | None] = mapped_column(String(127), default=None)
    file_size: Mapped[int | None] = mapped_column(BigInteger, default=None)
    s3_key: Mapped[str | None] = mapped_column(String(1024), default=None)
    created_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now())
