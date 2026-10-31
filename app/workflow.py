"""The five milestones assembled into one bounded request → test loop."""

from pathlib import Path
import shutil
import subprocess
import tempfile

from app.ai import ask_json
from app.executor import run_tests
from app.repository import git_diff, list_files, read_file, replace_once, search_code


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                   timeout=15, check=True)


def _snapshot(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "-c", "user.name=Local Agent", "-c", "user.email=agent@example.invalid",
         "commit", "-qm", "Starting snapshot")


def _select_files(root: Path, names: list) -> dict[str, str]:
    selected = {}
    for name in names[:5]:
        if isinstance(name, str):
            selected[name] = read_file(root, name)
    return selected


def run_job(repo_path: str, request: str, test_command: str, image: str,
            max_attempts: int = 3) -> dict:
    source = Path(repo_path).expanduser().resolve()
    if not source.is_dir() or source.is_symlink():
        raise ValueError("repo_path must be an existing directory")
    if not request.strip() or len(request) > 4000:
        raise ValueError("request must contain 1–4000 characters")
    if not 1 <= max_attempts <= 3:
        raise ValueError("max_attempts must be between 1 and 3")
    events = []
    with tempfile.TemporaryDirectory(prefix="coding-agent-") as temp:
        root = Path(temp) / "repo"
        shutil.copytree(source, root, symlinks=True, ignore=shutil.ignore_patterns(
            ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"))
        _snapshot(root)
        files = list_files(root)
        events.append({"tool": "list_files", "result": files})
        plan = ask_json(
            "You are a coding planner. Return keys: summary (string), steps (list of strings), "
            "files_to_read (list of existing paths), search_terms (list of short strings). "
            "Choose at most five files. Do not request shell commands.",
            {"request": request, "files": files, "test_command": test_command})
        events.append({"agent": "planner", "result": plan})
        searches = {}
        for term in plan.get("search_terms", [])[:3]:
            if isinstance(term, str):
                searches[term] = search_code(root, term)
        events.append({"tool": "search_code", "result": searches})
        chosen = _select_files(root, plan.get("files_to_read", []))
        events.append({"tool": "read_file", "paths": list(chosen)})
        last_test = None
        for attempt in range(1, max_attempts + 1):
            proposal = ask_json(
                "You are a coding agent. Return an edits list. Each edit has path, old, new "
                "strings. Each old string must appear exactly once in an existing file. "
                "Keep edits small. Do not create files. Use the failure output to repair your change.",
                {"request": request, "plan": plan, "files": chosen,
                 "previous_test": last_test, "current_diff": git_diff(root)})
            edits = proposal.get("edits", [])
            if not isinstance(edits, list) or not 1 <= len(edits) <= 5:
                raise ValueError("Model must propose 1–5 edits")
            for edit in edits:
                path = edit["path"]
                if path not in chosen:
                    raise ValueError("Model edited a file it did not read")
                replace_once(root, path, edit["old"], edit["new"])
                chosen[path] = read_file(root, path)
            events.append({"agent": "coder" if attempt == 1 else "fixer",
                           "attempt": attempt, "edits": [e["path"] for e in edits],
                           "diff": git_diff(root)})
            last_test = run_tests(root, test_command, image)
            events.append({"tool": "docker_tests", "attempt": attempt, "result": last_test})
            if last_test["exit_code"] == 0:
                break
        return {"status": "passed" if last_test["exit_code"] == 0 else "failed",
                "plan": plan, "events": events, "test": last_test,
                "diff": git_diff(root),
                "note": "Changes were made in a temporary copy and were not applied to the source repository."}
