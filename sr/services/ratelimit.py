"""Per-IP daily cap on paid-model generation calls.

Stopgap for the open-testing period before real accounts/login exist - a
runaway script or one bad actor shouldn't be able to run up the Replicate
bill. Counts are stored in the DB (not in-process memory) so the limit holds
across Cloud Run's multiple instances. Remove this once real auth lands.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from sr.config import get_settings
from sr.models.ip_usage import IpUsage


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_daily_limit(db: Session, request: Request, *, kind: str = "generation") -> None:
    limit = get_settings().max_generations_per_ip_per_day
    if limit <= 0:
        return
    ip = client_ip(request)
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    row = db.scalar(
        select(IpUsage).where(IpUsage.ip == ip, IpUsage.day == day, IpUsage.kind == kind)
    )
    if row is None:
        row = IpUsage(ip=ip, day=day, kind=kind, count=0)
        db.add(row)
    if row.count >= limit:
        raise HTTPException(
            429,
            f"Generation limit reached ({limit}/day per IP) while this app is in "
            "open testing - come back tomorrow, or ask the owner to raise the limit.",
        )
    row.count += 1
    db.commit()
