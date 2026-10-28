#!/usr/bin/env python3
"""Simulates GitHub delivering `pull_request` webhooks to a running
EnvForge API — this sandbox has no public URL for github.com to actually
call, so this script stands in for GitHub's delivery, with correctly
HMAC-signed payloads hitting the real `/api/v1/webhooks/github` endpoint.
The handler code (signature verification, idempotency, PR state
handling) is the same real code path either way; only the transport is
simulated.

Usage:
    python scripts/simulate_webhook.py opened --repo acme/sample-backend --pr 42
    python scripts/simulate_webhook.py synchronize --repo acme/sample-backend --pr 42 --sha def456
    python scripts/simulate_webhook.py closed --repo acme/sample-backend --pr 42
"""
import argparse
import hashlib
import hmac
import json
import time
import urllib.request
import uuid


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _pull_request_payload(action: str, repo: str, pr_number: int, branch: str, sha: str) -> dict:
    return {
        "action": action,
        "number": pr_number,
        "pull_request": {
            "number": pr_number,
            "head": {"ref": branch, "sha": sha},
            "html_url": f"https://github.com/{repo}/pull/{pr_number}",
        },
        "repository": {"full_name": repo},
    }


def send(base_url: str, secret: str, event_type: str, payload: dict) -> None:
    body = json.dumps(payload).encode()
    delivery_id = str(uuid.uuid4())
    req = urllib.request.Request(
        f"{base_url}/api/v1/webhooks/github",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": event_type,
            "X-GitHub-Delivery": delivery_id,
            "X-Hub-Signature-256": _sign(secret, body),
        },
    )
    with urllib.request.urlopen(req) as resp:
        print(f"[{event_type}] delivery={delivery_id} -> {resp.status} {resp.read().decode()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["opened", "synchronize", "closed"])
    parser.add_argument("--base-url", default="http://localhost:8010")
    parser.add_argument("--secret", default="dev-only-change-me", help="Must match GITHUB_WEBHOOK_SECRET")
    parser.add_argument("--repo", required=True, help="owner/repo, must match a registered Application")
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--branch", default="feature/demo")
    parser.add_argument("--sha", default=None, help="Defaults to a fresh fake SHA each run")
    args = parser.parse_args()

    sha = args.sha or hashlib.sha1(str(time.time()).encode()).hexdigest()
    payload = _pull_request_payload(args.action, args.repo, args.pr, args.branch, sha)
    send(args.base_url, args.secret, "pull_request", payload)


if __name__ == "__main__":
    main()
