"""Minimal typed slice of GitHub's `pull_request` webhook payload — only
the fields EnvForge actually uses. GitHub's real payload has many more
fields; Pydantic's default `extra='ignore'` behavior means we don't need
to model them to accept real webhook deliveries.
"""

from pydantic import BaseModel


class PullRequestHead(BaseModel):
    ref: str
    sha: str


class PullRequestPayload(BaseModel):
    number: int
    head: PullRequestHead
    html_url: str


class Repository(BaseModel):
    full_name: str


class PullRequestEvent(BaseModel):
    action: str
    number: int
    pull_request: PullRequestPayload
    repository: Repository
