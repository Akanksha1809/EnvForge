"""Resource-optimization recommendations — every suggestion here is
derived from a real query against live platform state, never a canned or
fabricated tip. Each recommendation names the specific resource it's
about, so a UI can deep-link straight to it.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.enums import JobStatus
from app.models.environment import Environment
from app.models.job import Job
from app.models.team import Team
from app.services.quotas import TERMINAL_STATES, count_active_environments_for_team

_LONG_LIVED_THRESHOLD_DAYS = 7


def _naive_safe(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


async def get_recommendations(db: AsyncSession) -> list[dict]:
    recommendations: list[dict] = []

    # 1. Teams approaching their active-environment quota.
    teams = (await db.execute(select(Team))).scalars().all()
    for team in teams:
        active_count = await count_active_environments_for_team(db, team.id)
        if team.max_active_environments > 0 and active_count / team.max_active_environments >= 0.8:
            recommendations.append(
                {
                    "severity": "warning"
                    if active_count < team.max_active_environments
                    else "critical",
                    "category": "quota",
                    "message": (
                        f"Team '{team.name}' is at {active_count}/{team.max_active_environments} "
                        "active environments. Consider raising its quota or cleaning up unused "
                        "ones."
                    ),
                    "resource_type": "team",
                    "resource_id": team.id,
                }
            )

    # 2. Applications with no resource requirements configured — cost
    # estimates for their environments are "simulated", not "estimated".
    apps = (
        (await db.execute(select(Application).where(Application.is_active.is_(True))))
        .scalars()
        .all()
    )
    for application in apps:
        if not application.resource_requirements:
            recommendations.append(
                {
                    "severity": "info",
                    "category": "cost_accuracy",
                    "message": (
                        f"Application '{application.name}' has no resource requirements "
                        "configured — its environments' cost estimates use a simulated baseline "
                        "rather than its actual shape. Set resource_requirements for accuracy."
                    ),
                    "resource_type": "application",
                    "resource_id": application.id,
                }
            )
        if application.environment_template_id is None:
            recommendations.append(
                {
                    "severity": "info",
                    "category": "consistency",
                    "message": (
                        f"Application '{application.name}' has no environment template assigned. "
                        "Assigning one keeps its environments provisioned consistently."
                    ),
                    "resource_type": "application",
                    "resource_id": application.id,
                }
            )

    # 3. Long-lived active environments — easy to forget about, and the
    # whole point of this platform is that environments are ephemeral.
    cutoff = datetime.now(UTC) - timedelta(days=_LONG_LIVED_THRESHOLD_DAYS)
    environments = (
        (await db.execute(select(Environment).where(Environment.state.not_in(TERMINAL_STATES))))
        .scalars()
        .all()
    )
    for environment in environments:
        if _naive_safe(environment.created_at) < cutoff:
            age_days = (datetime.now(UTC) - _naive_safe(environment.created_at)).days
            recommendations.append(
                {
                    "severity": "info",
                    "category": "staleness",
                    "message": (
                        f"Environment '{environment.name}' has been active for {age_days} days. "
                        "Confirm it's still needed, or let it expire."
                    ),
                    "resource_type": "environment",
                    "resource_id": environment.id,
                }
            )

    # 4. Jobs that have exhausted their retries and need a human.
    exhausted_jobs = (
        (
            await db.execute(
                select(Job).where(
                    Job.status == JobStatus.FAILED.value, Job.attempts >= Job.max_attempts
                )
            )
        )
        .scalars()
        .all()
    )
    if exhausted_jobs:
        recommendations.append(
            {
                "severity": "warning",
                "category": "failed_jobs",
                "message": (
                    f"{len(exhausted_jobs)} job(s) have exhausted their retry attempts and need "
                    "manual investigation (see GET /api/v1/jobs?status=failed)."
                ),
                "resource_type": "job",
                "resource_id": None,
            }
        )

    return recommendations
