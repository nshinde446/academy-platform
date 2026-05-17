import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class Plugin(BaseModel):
    __tablename__ = "plugins"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_point: Mapped[str] = mapped_column(String(255), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=True
    )


class PluginConfig(BaseModel):
    __tablename__ = "plugin_config"

    plugin_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("plugins.id"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PluginEvent(BaseModel):
    __tablename__ = "plugin_events"

    plugin_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("plugins.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    handler: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PluginDependency(BaseModel):
    __tablename__ = "plugin_dependencies"

    plugin_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("plugins.id"), nullable=False
    )
    depends_on_plugin_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("plugins.id"), nullable=False
    )
    min_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
