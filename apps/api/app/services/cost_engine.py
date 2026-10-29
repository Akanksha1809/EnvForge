"""Cost estimation — never real billing data, always one of two labeled
kinds:

- "estimated": the application explicitly configured cpu/memory
  requirements (`Application.resource_requirements`), so the number is
  computed from the user's own stated resource shape.
- "simulated": no resource requirements were configured, so a baseline
  assumption is used instead — a synthetic number, not even derived from
  the user's own config.

Pricing itself (`cost_cpu_core_hour_usd` etc., in app/core/config.py) is a
configurable assumption, not pulled from any cloud billing API — there is
no real billing integration in this build, and the spec explicitly
prohibits claiming actual AWS billing data without one.
"""

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.application import Application
from app.models.environment import Environment
from app.models.team import Team

_DEFAULT_CPU_CORES = 0.5
_DEFAULT_MEMORY_GB = 0.5

_CPU_MILLI_RE = re.compile(r"^(\d+(?:\.\d+)?)m$")
_MEMORY_RE = re.compile(r"^(\d+(?:\.\d+)?)(Ei|Pi|Ti|Gi|Mi|Ki|E|P|T|G|M|K)?$")

_MEMORY_UNIT_TO_BYTES: dict[str, float] = {
    "Ki": 1024,
    "Mi": 1024**2,
    "Gi": 1024**3,
    "Ti": 1024**4,
    "Pi": 1024**5,
    "Ei": 1024**6,
    "K": 1000,
    "M": 1000**2,
    "G": 1000**3,
    "T": 1000**4,
    "P": 1000**5,
    "E": 1000**6,
}


def _parse_cpu_cores(value: str | float | int | None) -> float | None:
    """Parses a Kubernetes-style CPU quantity ("500m", "0.5", 2) into cores."""
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    match = _CPU_MILLI_RE.match(value)
    if match:
        return float(match.group(1)) / 1000
    try:
        return float(value)
    except ValueError:
        return None


def _parse_memory_gb(value: str | float | int | None) -> float | None:
    """Parses a Kubernetes-style memory quantity ("512Mi", "1Gi") into GB."""
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value) / 1024**3
    match = _MEMORY_RE.match(value)
    if not match:
        return None
    amount, unit = match.groups()
    multiplier = _MEMORY_UNIT_TO_BYTES.get(unit, 1) if unit else 1
    return (float(amount) * multiplier) / 1024**3


def estimate_environment_cost(environment: Environment, application: Application) -> dict:
    settings = get_settings()
    resources = application.resource_requirements or {}

    cpu_cores = _parse_cpu_cores(resources.get("cpu") or resources.get("cpu_limit"))
    memory_gb = _parse_memory_gb(resources.get("memory") or resources.get("memory_limit"))

    basis = "estimated"
    if cpu_cores is None:
        cpu_cores = _DEFAULT_CPU_CORES
        basis = "simulated"
    if memory_gb is None:
        memory_gb = _DEFAULT_MEMORY_GB
        basis = "simulated"

    # SQLite (used by the test suite) silently drops tzinfo on round-trip
    # through a DateTime(timezone=True) column, unlike Postgres — treat a
    # naive datetime as UTC rather than letting the subtraction below
    # raise, since every datetime this app writes is UTC regardless of
    # whether the driver preserved that fact.
    start = environment.created_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    end = environment.destroyed_at or datetime.now(UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    hours_active = max((end - start).total_seconds() / 3600, 0.0)

    cpu_cost = cpu_cores * settings.cost_cpu_core_hour_usd * hours_active
    memory_cost = memory_gb * settings.cost_memory_gb_hour_usd * hours_active
    total_cost = round(cpu_cost + memory_cost, 4)

    return {
        "environment_id": environment.id,
        "basis": basis,
        "hours_active": round(hours_active, 2),
        "cpu_cores": cpu_cores,
        "memory_gb": memory_gb,
        "estimated_cost_usd": total_cost,
        "is_still_active": environment.destroyed_at is None,
    }


async def estimate_cost_summary(db: AsyncSession) -> dict:
    """Totals every environment that has ever existed (even deleted ones
    accrued real-shaped cost for however long they were up) grouped by
    team and by application, plus an overall total. Any `simulated`
    environment anywhere in the input taints the whole summary's
    `basis` to `simulated`, so the UI never implies a cleaner number than
    it has."""
    rows = (
        await db.execute(
            select(Environment, Application, Team)
            .join(Application, Application.id == Environment.application_id)
            .join(Team, Team.id == Application.team_id)
        )
    ).all()

    by_team: dict[str, dict] = {}
    by_application: dict[str, dict] = {}
    total_cost = 0.0
    any_simulated = False

    for environment, application, team in rows:
        result = estimate_environment_cost(environment, application)
        total_cost += result["estimated_cost_usd"]
        any_simulated = any_simulated or result["basis"] == "simulated"

        team_bucket = by_team.setdefault(
            team.id, {"name": team.name, "slug": team.slug, "estimated_cost_usd": 0.0}
        )
        team_bucket["estimated_cost_usd"] += result["estimated_cost_usd"]

        app_bucket = by_application.setdefault(
            application.id,
            {"name": application.name, "slug": application.slug, "estimated_cost_usd": 0.0},
        )
        app_bucket["estimated_cost_usd"] += result["estimated_cost_usd"]

    for bucket in (*by_team.values(), *by_application.values()):
        bucket["estimated_cost_usd"] = round(bucket["estimated_cost_usd"], 4)

    return {
        "basis": "simulated" if any_simulated else "estimated",
        "total_estimated_cost_usd": round(total_cost, 4),
        "by_team": sorted(by_team.values(), key=lambda b: b["estimated_cost_usd"], reverse=True),
        "by_application": sorted(
            by_application.values(), key=lambda b: b["estimated_cost_usd"], reverse=True
        ),
    }
