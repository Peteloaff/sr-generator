"""RenderCache: content-addressed cache of expensive audio renders.

Voice conversions are deterministic in (guide audio, voice profile, params,
provider version). Caching them means a gang of 10 takes for one singer runs the
conversion once, and a job retry after a transient failure reuses everything that
already succeeded (cache rows are committed independently of the render
transaction).
"""

from __future__ import annotations

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from sr.models.base import Base, Timestamps, UUIDPrimaryKey


class RenderCache(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "render_cache"

    cache_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(30), default="voice_conversion")
    provider: Mapped[str] = mapped_column(String(60))
    provider_version: Mapped[str] = mapped_column(String(60))
    file_path: Mapped[str] = mapped_column(String(500))
    duration: Mapped[float | None] = mapped_column(Float, default=None)
    hits: Mapped[int] = mapped_column(Integer, default=0)
