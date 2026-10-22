"""Small source credential guard. Reports locations only; not an exhaustive secret detector."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {
    "node_modules",
    ".next",
    ".git",
    "__pycache__",
    ".venv",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
}
PATTERNS = [
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"\bAKIA[0-9A-Z]{16}\b",
    r"\bgh[pousr]_[A-Za-z0-9]{30,}\b",
    r"\bgithub_pat_[A-Za-z0-9_]{40,}\b",
    r"\bsk-proj-[A-Za-z0-9_-]{40,}\b",
]


PRIVATE_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".duckdb",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".safetensors",
    ".pt",
    ".pth",
    ".ckpt",
    ".onnx",
    ".bin",
    ".h5",
    ".hdf5",
    ".pkl",
    ".pickle",
    ".joblib",
    ".npz",
    ".parquet",
    ".feather",
    ".zip",
    ".gz",
    ".tgz",
    ".tar",
    ".7z",
    ".rar",
    ".log",
    ".pyc",
    ".tsbuildinfo",
}
PRIVATE_NAMES = {".netrc", ".npmrc", ".pypirc", "playwright-results.json"}
PRIVATE_DIRECTORIES = EXCLUDED - {".git"} | {".cache", "test-results", "playwright-report"}


def source_paths() -> list[Path]:
    # Scan tracked bytes even if ignore rules would now hide those paths.
    if (ROOT / ".git").exists():
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        return [ROOT / name for name in result.stdout.decode().split("\0") if name]
    return [path for path in ROOT.rglob("*") if not set(path.relative_to(ROOT).parts) & EXCLUDED]


def main() -> None:
    findings = []
    count = 0
    for path in source_paths():
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if (
            path.name.startswith(".env")
            or path.name in PRIVATE_NAMES
            or path.suffix.lower() in PRIVATE_SUFFIXES
            or re.search(r"\.(?:db|sqlite3?)-(?:wal|shm|journal)$", path.name, re.IGNORECASE)
            or set(relative.parts[:-1]) & PRIVATE_DIRECTORIES
        ):
            findings.append(str(relative))
        if path.stat().st_size > 5_000_000:
            findings.append(str(relative))
            continue
        try:
            value = path.read_text()
        except (UnicodeError, OSError):
            continue
        count += 1
        if any(re.search(pattern, value) for pattern in PATTERNS):
            findings.append(str(path.relative_to(ROOT)))
    if findings:
        raise SystemExit("Credential/private artifact review required: " + ", ".join(findings))
    print(
        f"PASS: {count} text files scanned; no configured credential signatures/private artifacts"
    )


if __name__ == "__main__":
    main()
