"""Real GitHub REST API calls — commit statuses and PR comments.

Requires `GITHUB_API_TOKEN` to be configured. Without one (the default in
this sandbox, which has no real GitHub App/PAT), every call here is a
logged no-op rather than a fabricated success — the integration code path
is real, only the credential is absent. Configure a token against any
real repo and this starts actually posting.
"""

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("envforge.github")


class GitHubAPIError(Exception):
    pass


def _client() -> httpx.AsyncClient | None:
    settings = get_settings()
    if not settings.github_api_token:
        return None
    return httpx.AsyncClient(
        base_url=settings.github_api_base_url,
        headers={
            "Authorization": f"Bearer {settings.github_api_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=15.0,
    )


async def post_commit_status(
    repo_full_name: str,
    sha: str,
    *,
    state: str,
    description: str,
    target_url: str | None = None,
    context: str = "envforge/preview",
) -> None:
    """state must be one of: pending, success, failure, error."""
    client = _client()
    if client is None:
        logger.info(
            "github.commit_status.skipped_no_token",
            repo=repo_full_name,
            sha=sha,
            state=state,
        )
        return

    payload: dict[str, str] = {"state": state, "description": description, "context": context}
    if target_url:
        payload["target_url"] = target_url

    async with client:
        try:
            resp = await client.post(f"/repos/{repo_full_name}/statuses/{sha}", json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "github.commit_status.failed", repo=repo_full_name, sha=sha, error=str(exc)
            )


async def post_pr_comment(repo_full_name: str, pr_number: int, body: str) -> None:
    client = _client()
    if client is None:
        logger.info("github.pr_comment.skipped_no_token", repo=repo_full_name, pr=pr_number)
        return

    async with client:
        try:
            resp = await client.post(
                f"/repos/{repo_full_name}/issues/{pr_number}/comments", json={"body": body}
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "github.pr_comment.failed", repo=repo_full_name, pr=pr_number, error=str(exc)
            )
