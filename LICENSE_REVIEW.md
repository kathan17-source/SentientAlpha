> Historical audit/release record. The owner has now selected All Rights Reserved and authorized a private candidate upload. Current selection and verification supersede earlier pending-decision/upload statements: [publication selection](PUBLICATION_SELECTION.md), [current report](GITHUB_PORTFOLIO_PREPARATION.md). Historical results remain historical.

# Publication and licensing review — recommendation, not a license grant

**PARTIALLY VERIFIED; owner decision required before publication.** No LICENSE file or unsupported ownership assertion was added. Recommend considering the [MIT license](https://opensource.org/license/mit) for original source after confirming ownership, contributor/employer obligations and copied-material notices. MIT's notice condition applies to covered copies; a project license does not grant rights to third-party data or models. If explicit patent terms are desired, assess Apache-2.0 instead before choosing. This release does not claim that every input is cleared for redistribution.

## Separate materials and obligations

| Material | Review / release handling |
|---|---|
| Original application source | Ownership and license choice remain the owner's decision. No repository publication occurred. |
| Python/JavaScript dependencies | Installed metadata and lockfile license inventory recorded under docs/verification/post-release. Common libraries declare permissive licenses, but preserve required upstream notices for any distributed copies. Metadata is not a complete license text/exception or transitive-code audit. Wheels/node_modules are not shipped. |
| ProsusAI FinBERT weights | Current [official model card](https://huggingface.co/ProsusAI/finbert) labels model weights CC-BY-NC-SA-4.0 and explains training-data responsibilities. This differs from source-code license claims found elsewhere. Review the pinned model revision and applicable terms for actual use; do not describe the weights as generally cleared for commercial redistribution. No weights or tokenizer cache is included. |
| Financial PhraseBank / training corpora | FinBERT's upstream training-data obligations are separate from application code; no corpus is bundled or relicensed. No rights inference follows from downloading a model. |
| Alpha Vantage market data | [Official terms](https://www.alphavantage.co/terms_of_service/) impose use/licensing restrictions and distinguish personal/commercial use. Do not treat an API subscription as permission to republish raw data. Raw downloaded prices are excluded; retain numerical negative findings and source provenance without asserting legal clearance for all derived outputs. |
| Financial news and excerpts | Source feeds, headlines, descriptions and full article rights vary; no restricted raw corpus or article-text dump is included. Review any future screenshot/export manually. |
| Synthetic fixtures | Generated deterministically by project code, visibly labeled; not genuine market observations. Keep clear of real provider fallback paths. |
| Reports / screenshots / binaries | Historical outcome evidence is retained, local paths redacted. No new rendered screenshots, model binaries, private DBs, dependency directories or nested archives are included. Review any later media for personal/licensed content before public sharing. |

The official sources above were checked during this pass (2026-10-21). The recommendations do not resolve ownership or provide commercial data/model clearance. Publication readiness remains partial until the owner chooses and applies a license and reviews notices/materials. Existing GitHub workflows and container files do not themselves authorize publication.
