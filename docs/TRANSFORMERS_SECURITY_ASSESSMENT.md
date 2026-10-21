# Optional NLP security assessment — 2026-10-21

**VERIFIED targeted update and compatibility; no general artifact-safety certification.** Previous stack: Transformers4.57.6, huggingface-hub0.36.2 and tokenizers0.22.2. New optional pins: Transformers5.20.2, huggingface-hub2.2.0 and tokenizers0.23.3, with resolver-required CLI/HTTP dependencies pinned in requirements-nlp.lock. Default core/Docker/demo still exclude NLP.

## Old advisory paths and supported exposure

| Old advisory ID | Affected functionality described by scanner | Supported-configuration exposure | Reported fix metadata / disposition |
|---|---|---|---|
| PYSEC-2025-217 | X-CLIP checkpoint conversion deserialization | Conversion utility is not intentionally invoked by fixed BERT classification; malicious artifacts still prohibited | Old record lacked fix metadata;5.20.2 final scan has no advisory match |
| PYSEC-2026-2288 | Trainer RNG-state torch.load | Application does not train Transformers or resume Trainer checkpoints | Records cite5.0.0/rc3; updated |
| PYSEC-2026-2289 | Model configuration attention implementation code path | from_pretrained is used; fixed repository/revision and trust_remote_code=False reduce exposure, but altered untrusted cache is unsafe | Record cites5.3.0; updated |
| PYSEC-2026-2290 | LightGlue initialization remote code | Fixed BERT classifier does not intentionally select LightGlue | One record lacks fixes, another cites5.5.0; updated |
| PYSEC-2026-3929 | save_pretrained chat-template path traversal | Application does not intentionally save tokenizer/processor templates from user-controlled artifacts | Record cites5.10.0; updated beyond threshold |
| PYSEC-2026-4174 | Generative load_custom_generate writes/downloads | No generative custom_generate invocation in financial classification | Old record lacks fix metadata;5.20.2 scan no match |

The original scan contains nine records but six unique IDs. This is source-path reachability assessment, not exploit reproduction or proof that every transitive path is unreachable. Full original advisory descriptions remain in milestone12 evidence. [Upstream security guidance](https://github.com/huggingface/transformers/security) and [reviewed path-traversal advisory](https://github.com/advisories/GHSA-xrqw-3rrv-vx5w) supplement the version scan.

## Candidate selection and tests

- Queried actual package-index metadata;5.10.0 is yanked, so it was rejected rather than adopted merely because one advisory names it as a fix.
- Installed5.20.2 and required dependencies in an isolated candidate directory first. Existing actual cached FinBERT test passed with local_files_only and offline hub access.
- Compared seven texts (positive, negative, neutral/mixed examples and truncation case) using old/new stacks on the same trusted pinned CPU model: maximum absolute probability difference **0.0**, tolerance1e-5. This is a small compatibility sample, not every model/platform/input.
- Adopted exact candidate pins only after those checks; installed resolver closure has no pip-check conflicts. Full3.12 suite with optional real model enabled:606 passed +11 subtests. Unchanged3.14 core:605 passed,1 optional skip,+11 subtests.
- Final pip-audit of actual developer+optional NLP lock versions reports **zero known advisories**, no ignore-list. npm scan also zero. This is a point-in-time advisory database result, not certification or a guarantee against unknown defects.

Dependency versions intentionally participate in FinBERT model metadata/key. Existing old-model provenance must remain identifiable; don't relabel old predictions as produced by5.20.2. The update changes optional dependency provenance, not strategy logic or mathematical conventions. No backend financial code, test assertion or model weights were changed. Keep caches trusted, initialization local-only, news as inert text, and arbitrary remote/user model artifacts disallowed. See root SECURITY.md.
