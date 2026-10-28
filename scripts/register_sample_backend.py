#!/usr/bin/env python3
"""Registers Sample App A (sample-apps/backend) with a running EnvForge API
as a team + application, so `POST /environments` can provision a real
preview environment for it. Used by the Phase 3+ manual smoke test and the
full demo script (scripts/demo.sh).

Usage:
    python scripts/register_sample_backend.py \\
        --base-url http://localhost:8010 \\
        --email admin@envforge.dev --password supersecret123
"""
import argparse
import json
import sys
import urllib.error
import urllib.request


def _request(method: str, url: str, token: str | None = None, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        print(f"{method} {url} -> {exc.code}: {exc.read().decode()}", file=sys.stderr)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8010")
    parser.add_argument("--email", default="admin@envforge.dev")
    parser.add_argument("--password", default="supersecret123")
    parser.add_argument("--image", default="envforge/sample-backend:dev")
    args = parser.parse_args()

    api = f"{args.base_url}/api/v1"

    try:
        _request(
            "POST",
            f"{api}/auth/register",
            body={"email": args.email, "full_name": "Platform Admin", "password": args.password},
        )
    except urllib.error.HTTPError:
        pass  # already registered — fine, this script is idempotent

    tokens = _request(
        "POST", f"{api}/auth/login", body={"email": args.email, "password": args.password}
    )
    token = tokens["access_token"]

    teams = _request("GET", f"{api}/teams", token=token)
    team = next((t for t in teams["items"] if t["slug"] == "platform-team"), None)
    if team is None:
        team = _request(
            "POST",
            f"{api}/teams",
            token=token,
            body={"name": "Platform Team", "slug": "platform-team", "max_active_environments": 10},
        )
    print(f"team: {team['id']} ({team['slug']})")

    applications = _request("GET", f"{api}/applications", token=token)
    app = next((a for a in applications["items"] if a["slug"] == "sample-backend"), None)
    if app is None:
        app = _request(
            "POST",
            f"{api}/applications",
            token=token,
            body={
                "name": "Sample Backend",
                "slug": "sample-backend",
                "team_id": team["id"],
                "github_repo": "envforge/sample-apps-backend",
                "deployment_config": {
                    "image": args.image,
                    "port": 8000,
                    "dependencies": [
                        {
                            "name": "postgres",
                            "image": "postgres:16-alpine",
                            "port": 5432,
                            "env_vars": {
                                "POSTGRES_PASSWORD": "postgres",
                                "POSTGRES_DB": "postgres",
                            },
                        },
                        {"name": "redis", "image": "redis:7-alpine", "port": 6379, "env_vars": {}},
                    ],
                },
                "env_vars": {
                    "DATABASE_URL": "postgresql://postgres:postgres@postgres:5432/postgres",
                    "REDIS_URL": "redis://redis:6379/0",
                },
                "health_check_config": {"path": "/health"},
                "environment_ttl_hours": 48,
            },
        )
    print(f"application: {app['id']} ({app['slug']})")
    print("\nCreate an environment for it with:")
    print(
        f'  curl -X POST {api}/environments -H "Authorization: Bearer <token>" '
        f'-H "Content-Type: application/json" -d \'{{"application_id": "{app["id"]}"}}\''
    )


if __name__ == "__main__":
    main()
