# Executed command families

From the source root with the indicated installed Python environment:

```sh
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pip check
RUN_FINBERT=1 FINBERT_CACHE_DIR=/absolute/trusted/model-cache HF_HUB_OFFLINE=1 python -m pytest -q backend/tests/test_finbert_optional.py
npm --prefix frontend ci
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend test
npm --prefix frontend run build
CONTAINER_BUILD=1 npm --prefix frontend run build
PYTHONPATH=backend python scripts/release_demo.py --database /tmp/NEW-demo.db --report /tmp/NEW-demo.json
python scripts/release_scan.py
pip-audit --cache-dir /tmp/audit-cache -r requirements-runtime.lock --format json
pip-audit --cache-dir /tmp/audit-cache --no-deps --disable-pip -r requirements.lock --format json
pip-audit --cache-dir /tmp/audit-cache --no-deps --disable-pip -r requirements.lock -r requirements-nlp.lock --format json
npm --prefix frontend audit --json
```

Full tests executed on separate Python3.12/3.14 environments. FinBERT optional smoke used Python3.12 only. Standalone build is a local Node build, not a Docker runtime result. Developer/all-NLP advisory scans query pinned package versions without reinstalling heavy dependencies; this is not a wheel-hash audit. Initial pip-audit cache access failed under the user's Library/Caches; rerun with explicit writable cache succeeded. The initial clean editable install without build isolation lacked setuptools; the documented ordinary build-isolated install succeeded.
