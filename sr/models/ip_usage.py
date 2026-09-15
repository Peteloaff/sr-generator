"""IpUsage: a per-IP, per-day counter for paid generation calls.

Stopgap rate limit for the open-testing period before real accounts/login
exist - a stuck loop or one bad actor shouldn't be able to run up the
Replicate bill. Stored in the DB (not in-process memory) so the limit holds
across Cloud Run's multiple instances.
"""

from __future__ import annotations

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sr.models.base import Base, Timestamps, UUIDPrimaryKey


class IpUsage(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "ip_usage"
    __table_args__ = (UniqueConstraint("ip", "day", "kind", name="uq_ip_usage_ip_day_kind"),)

    ip: Mapped[str] = mapped_column(String(64), index=True)
    day: Mapped[str] = mapped_column(String(10))  # "YYYY-MM-DD", UTC
    kind: Mapped[str] = mapped_column(String(30), default="generation")
    count: Mapped[int] = mapped_column(Integer, default=0)
