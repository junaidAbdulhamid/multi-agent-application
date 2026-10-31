"""Small, bounded tools for inspecting and changing a copied repository."""

from pathlib import Path
import subprocess

SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
MAX_FILE_BYTES = 80_000


def safe_path(root: Path, name: str) -> Path:
    if not name or Path(name).is_absolute():
        raise ValueError("Path must be relative to the repository")
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Path escapes the repository")
    return path


def list_files(root: Path, limit: int = 200) -> list[str]:
    files = []
    for path in root.rglob("*"):
        if any(part in SKIP for part in path.relative_to(root).parts):
            continue
        if path.is_file() and not path.is_symlink():
            files.append(path.relative_to(root).as_posix())
            if len(files) >= limit:
                break
    return sorted(files)


def read_file(root: Path, name: str) -> str:
    path = safe_path(root, name)
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("File is missing, linked, or too large")
    return path.read_text(encoding="utf-8")


def search_code(root: Path, term: str, limit: int = 40) -> list[str]:
    if not term or len(term) > 100:
        raise ValueError("Search term must contain 1–100 characters")
    matches = []
    for name in list_files(root):
        try:
            for number, line in enumerate(read_file(root, name).splitlines(), 1):
                if term.lower() in line.lower():
                    matches.append(f"{name}:{number}: {line[:200]}")
                    if len(matches) >= limit:
                        return matches
        except (UnicodeError, ValueError):
            continue
    return matches


def replace_once(root: Path, name: str, old: str, new: str) -> None:
    if not old or len(new) > MAX_FILE_BYTES:
        raise ValueError("Invalid edit")
    path = safe_path(root, name)
    current = read_file(root, name)
    if current.count(old) != 1:
        raise ValueError("Edit target must occur exactly once")
    path.write_text(current.replace(old, new, 1), encoding="utf-8")


def git_diff(root: Path) -> str:
    result = subprocess.run(["git", "diff", "--no-ext-diff"], cwd=root, text=True,
                            capture_output=True, timeout=10, check=False)
    return result.stdout[:100_000]
