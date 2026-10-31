from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.executor import ALLOWED_COMMANDS, ALLOWED_IMAGES
from app.repository import git_diff, list_files, read_file, search_code
from app.workflow import run_job
from pathlib import Path
from typing import Optional

app = FastAPI(title="Learning Coding Agent")


class RunRequest(BaseModel):
    repo_path: str
    request: str = Field(min_length=1, max_length=4000)
    test_command: str = "python -m unittest discover -v"
    docker_image: str = "python:3.12-slim"
    max_attempts: int = Field(default=3, ge=1, le=3)


class InspectRequest(BaseModel):
    repo_path: str
    path: Optional[str] = None
    search: Optional[str] = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/inspect")
def inspect(body: InspectRequest) -> dict:
    try:
        root = Path(body.repo_path).expanduser().resolve()
        if not root.is_dir():
            raise ValueError("repo_path must be a directory")
        return {"files": list_files(root),
                "content": read_file(root, body.path) if body.path else None,
                "matches": search_code(root, body.search) if body.search else [],
                "diff": git_diff(root)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/runs")
def runs(body: RunRequest) -> dict:
    if body.test_command not in ALLOWED_COMMANDS:
        raise HTTPException(400, "Unsupported test command")
    if body.docker_image not in ALLOWED_IMAGES:
        raise HTTPException(400, "Unsupported Docker image")
    try:
        return run_job(body.repo_path, body.request, body.test_command,
                       body.docker_image, body.max_attempts)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
