# Learning Coding Agent

An educational FastAPI backend that plans a small code change, edits a **temporary copy** of a repository, runs its tests in Docker, and retries after a failure. It does not commit or open a pull request yet.

## Setup

Use Python 3.10 or newer and a running Docker daemon.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="your-key"
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API.

## Try it

The example repository deliberately has a failing addition test. Before an AI run, try `POST /inspect` with `repo_path` set to the absolute path of `examples/tiny_repo`.

```sh
curl -X POST http://127.0.0.1:8000/runs \
  -H 'Content-Type: application/json' \
  -d '{"repo_path":"/ABSOLUTE/PATH/TO/multi-agent-application/examples/tiny_repo","request":"Fix add so it returns the sum of two integers. The existing test should pass.","test_command":"python -m unittest discover -v","docker_image":"python:3.12-slim"}'
```

Pull the image once while you have network access: `docker pull python:3.12-slim`. The test container runs without network access, as an unprivileged user, with a read-only repository mount and resource limits. It uses the packages already in the image; it does not install target-repository dependencies. This first version therefore supports simple Python `unittest` tests with the standard library, or projects whose dependencies are baked into an approved image.

The API returns the plan, tool events, test output, and a Git diff. The temporary copy is deleted when the request ends. Review the diff and make the desired change yourself in the original repository.

## Architecture

1. `app/main.py` defines the HTTP request and response boundary.
2. `app/repository.py` lists, searches, reads, and edits files while checking paths.
3. `app/ai.py` sends the planner and coder prompts to the model.
4. `app/workflow.py` copies the repository, makes a starting Git snapshot, coordinates the planner/coder/fixer loop, and records events.
5. `app/executor.py` runs one allowlisted test command in Docker and returns exit code, stdout, and stderr.

Run local checks with `python -m pytest -q`. The workflow test substitutes a deterministic model and test result so it can verify the retry logic without an API key or Docker.

## Current limits

- Requests run synchronously; large jobs need a background queue later.
- The model can replace text in existing files only; file creation and deletion come later.
- The run sees up to 200 files, reads up to five small files, and retries at most three times.
- Docker isolation here is a learning baseline. Do not run untrusted public repositories until you have stronger isolation, dependency handling, and authorization controls.
