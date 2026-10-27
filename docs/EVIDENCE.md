# Evidence retained and reproduction boundaries

This recruiter-facing source tree retains working code, tests, migration history, developer/verification scripts, the required OpenAPI schema, module design guides and meaningful research reports. Historical diagnostic outputs and superseded inventories are archived locally rather than presented as current test results.

Before removal, every one of the 536 tracked files at initial main `e36d976` was copied and SHA-256 verified in the owner's separate local archival directory, `recruiter-archive/main-e36d976`. After the owner merged browser repair PR #3, updated main `527ef48` was separately archived and verified under `recruiter-archive/main-527ef48`; all 225 removed payloads were unchanged between those snapshots. Its `snapshot/` retains exact original relative paths; `CLASSIFICATION.json` records every original file, disposition, reason, hash and reviewed source consumers. The owner can provide permissible evidence for private technical review. The archive is outside this Git working tree and is not committed. The original SentientAlpha-Post-Release-Verified.zip is separately preserved.

The GitHub tree removes 225 individually reviewed historical/generated files and adds three concise documentation pages. Removing files from this tree does not erase them from existing Git history. No history was rewritten. No application source, test assertion, migration, dependency, required schema, license or verification script was removed. Retained source can regenerate fresh synthetic demonstrations, tests and numerical checks; historical hardware timings and original IDs are not promised to reproduce bit-for-bit.

## What remains reviewable

- Architecture and module guides explain temporal eligibility, training/calibration/holdout boundaries, numerical conventions, risk vetoes and persistent accounting.
- The M3–M9 research reports preserve genuine-data limitations and negative findings. They are dated research records, not current deployment/CI claims.
- [Research results](RESEARCH_RESULTS.md) summarizes the primary empirical boundaries; [verification](VERIFICATION.md) separates executed checks from infrastructure gaps.
- Original test/demo generators remain, including synthetic scenarios, failure injection, event replay and restart reconciliation. `docs/openapi.json` remains because frontend API generation consumes it.

Historical exported data, screenshots, advisory diagnostics, repeated inventories and milestone console output are retained locally. References to archived outputs are marked in the retained guides. They are not substituted with invented values or silently relabeled as new results. Genuine-market reruns require independently entitled source data; the clean source does not redistribute provider datasets, model weights or the previously held exports.

## Rights boundary

The existing LICENSE is unchanged. Third-party notices remain independent. The seven previously recommended exclusions and seventeen held materials were never introduced into this publication history; archived path/hash inventories do not grant rights in their referenced data. Permitted Federal Reserve headline examples from the earlier source are also archived rather than needed for the offline demo. Download optional dependencies/models separately under their own terms; model commercial use and redistribution of built bundles/images require their own review.
