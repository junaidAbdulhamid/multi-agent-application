"""Run a preselected test command in a constrained Docker container."""

from pathlib import Path
import subprocess

ALLOWED_COMMANDS = {
    "python -m unittest discover -v": ["python", "-m", "unittest", "discover", "-v"],
}
ALLOWED_IMAGES = {"python:3.12-slim"}


def run_tests(root: Path, command: str, image: str) -> dict:
    if command not in ALLOWED_COMMANDS:
        raise ValueError("Test command is not allowlisted")
    if image not in ALLOWED_IMAGES:
        raise ValueError("Docker image is not allowlisted")
    docker_command = [
        "docker", "run", "--rm", "--network", "none", "--read-only",
        "--memory", "512m", "--cpus", "1", "--pids-limit", "128",
        "--user", "65534:65534", "--tmpfs", "/tmp:rw,size=64m",
        "--mount", f"type=bind,src={root},dst=/workspace,readonly",
        "--workdir", "/workspace", image, *ALLOWED_COMMANDS[command],
    ]
    try:
        result = subprocess.run(docker_command, text=True, capture_output=True,
                                timeout=120, check=False)
        return {"command": command, "exit_code": result.returncode,
                "stdout": result.stdout[-12_000:], "stderr": result.stderr[-12_000:]}
    except subprocess.TimeoutExpired:
        return {"command": command, "exit_code": -1, "stdout": "", "stderr": "Test timed out after 120 seconds"}
