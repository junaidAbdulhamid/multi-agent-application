from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.repository import read_file, replace_once, safe_path
from app.run_store import get_run


def test_repository_path_stays_inside_root(tmp_path: Path):
    (tmp_path / "sample.py").write_text("value = 1\n")
    assert read_file(tmp_path, "sample.py") == "value = 1\n"
    replace_once(tmp_path, "sample.py", "1", "2")
    assert read_file(tmp_path, "sample.py") == "value = 2\n"
    try:
        safe_path(tmp_path, "../outside.py")
    except ValueError:
        pass
    else:
        raise AssertionError("Parent traversal was accepted")


def test_run_loop_repairs_failure_without_editing_source(monkeypatch, tmp_path: Path):
    (tmp_path / "calculator.py").write_text("return a - b\n")
    answers = iter([
        {"summary": "Fix addition", "steps": ["Edit calculator.py"],
         "files_to_read": ["calculator.py"], "search_terms": ["return"]},
        {"edits": [{"path": "calculator.py", "old": "a - b", "new": "a * b"}]},
        {"edits": [{"path": "calculator.py", "old": "a * b", "new": "a + b"}]},
    ])
    monkeypatch.setattr("app.workflow.ask_json", lambda *args: next(answers))
    calls = iter([1, 0])
    monkeypatch.setattr("app.workflow.run_tests", lambda *args: {
        "command": "python -m unittest discover -v", "exit_code": next(calls),
        "stdout": "failed then passed", "stderr": ""})
    client = TestClient(app)
    response = client.post("/runs", json={
        "repo_path": str(tmp_path), "request": "Make addition work"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "passed"
    assert len([event for event in body["events"] if event.get("tool") == "docker_tests"]) == 2
    assert "+return a + b" in body["diff"]
    assert (tmp_path / "calculator.py").read_text() == "return a - b\n"
    assert client.get(f"/runs/{body['run_id']}").json() == body


def test_unknown_run_returns_404():
    response = TestClient(app).get("/runs/does-not-exist")
    assert response.status_code == 404


def test_reading_a_run_cannot_change_stored_result():
    from app.run_store import save_run

    saved = save_run({"status": "passed", "events": []})
    first_read = get_run(saved["run_id"])
    first_read["events"].append({"tool": "fake"})
    assert get_run(saved["run_id"])["events"] == []
