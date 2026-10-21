"""Small source credential guard. Reports locations only; not an exhaustive secret detector."""

import re
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
    r"\bsk-proj-[A-Za-z0-9_-]{40,}\b",
]


def main() -> None:
    findings = []
    count = 0
    for path in ROOT.rglob("*"):
        if not path.is_file() or set(path.relative_to(ROOT).parts) & EXCLUDED:
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            findings.append(str(path.relative_to(ROOT)))
        if path.suffix in {".db", ".sqlite", ".pem", ".key"}:
            findings.append(str(path.relative_to(ROOT)))
        if path.stat().st_size > 5_000_000:
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
    print(f"PASS: {count} text files scanned; no configured credential signatures/private DBs")


if __name__ == "__main__":
    main()
