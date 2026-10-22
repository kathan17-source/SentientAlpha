> Historical audit/release record. The owner has now selected All Rights Reserved and authorized a private candidate upload. Current selection and verification supersede earlier pending-decision/upload statements: [publication selection](PUBLICATION_SELECTION.md), [current report](GITHUB_PORTFOLIO_PREPARATION.md). Historical results remain historical.

# Publication decisions — four owner decisions only

Nothing has been licensed, excluded from disk, published or deployed. These decisions concern the proposed source publication; they do not authorize a public web service. Exact per-file actions: [proposed selection](docs/ownership-audit/PROPOSED_PUBLIC_FILES.json).

## D1 — Confirm what you are entitled to publish

- **Decide:** whether original/AI-assisted contributions are yours to release, and identify any employer/client/coauthor obligations or copied/adapted snippets not visible in provenance.
- **Options:** confirm the identified scope; disclose additional rights holders and obtain permission; hold/restrict affected files.
- **Consequence:** determines which contributions you can license or publicly display. AI-assisted generation and missing headers do not prove exclusive title.
- **Recommendation:** confirm ownership/authority only for the contributions you can substantiate, and list any exceptions. No need to assert ownership of dependency/model/data rights.
- **Exact scope:** backend/**; frontend project app/components/lib/tests/e2e; scripts/**; config/**; migrations project portions; project docs/config. Framework-generated exceptions are identified in MATERIAL_INVENTORY.json.
- **Blocks publication:** **Yes**, for any uncleared contribution included.

## D2 — Choose the original-code grant and copyright identity

- **Decide:** MIT, Apache-2.0, or deliberately public source-available without an open-source grant; specify copyright holder/name and applicable year(s) and scope.
- **Options/consequences:** MIT is simple permissive reuse with notice preservation; Apache2 adds express contributor patent provisions and notice/modification administration; no grant reserves general reuse rights while GitHub public view/fork terms still apply. None licenses third-party data/models on your behalf.
- **Recommendation:** MIT for a straightforward permissive portfolio release if D1 is confirmed and broad reuse is intended; Apache2 if you specifically want its patent terms; no grant if you intend review rather than general reuse.
- **Exact files affected after approval:** future root LICENSE (if chosen), README.md, pyproject.toml and frontend/package.json licensing declarations as appropriate, and third-party notice references. No such edits were applied.
- **Blocks publication:** **Yes until intent is recorded** for this gate; not a claim that a public repository must legally use an open-source license.

## D3 — Approve the material scope

- **Decide:** lean source/synthetic publication or a richer evidence/media package backed by the relevant permissions.
- **Options:** (a) approve the conservative selection; (b) supply permission/source-specific clearance for held items; (c) omit all optional screenshots/exports.
- **Recommendation:** retain code, tests, migrations, generators and written negative findings; exclude the genuine numeric provider example and unnecessary bulk snapshots; withhold 17 items pending review (including 5 genuine-derived screenshots). Three empty/synthetic screenshots can be retained with project/icon rights/notices. Retain the 3 Board headlines only with existing attribution and no contrary item notice, or omit them too if you prefer minimum external content.
- **Exact files:** seven recommended exclusions and 17 held paths are enumerated in PROPOSED_PUBLIC_FILES.json. Key examples: docs/verification/public-provider.json; docs/M5_FROZEN_DEMO.json; docs/M6_FROZEN_DEMO.json; five named genuine-derived PNGs; genuine/mixed research JSON exports. No local original will be deleted. The established IBM −8.70% versus −4.69% comparison stays in written reports.
- **Consequence:** changes the future public staging set and requires link/manifest reconciliation before packaging; it does not change calculations or tests. Dependency directories, model caches/weights, private DB/env/log files remain excluded regardless of presentation choice.
- **Blocks publication:** **Yes**, until the files to publish are chosen and applicable notices/permissions are satisfied. You need not obtain optional model/data redistribution rights if you do not redistribute those materials.

## D4 — Authorize an actual publication destination later

- **Decide:** intended GitHub account/repository, visibility and whether to authorize creation/initial push after the approved staging set is reviewed.
- **Options:** remain local/private; approve a named private repository first; approve a named public source repository after D1–D3.
- **Recommendation:** review the selected files and notice/license text before authorizing upload. No hosting/deployment permission is implied.
- **Exact affected items:** future Git initialization/remote configuration and approved source files only; none exists or was changed by this audit.
- **Blocks publication:** **Yes for upload authorization**; separate from whether code is technically fit for review.

Infrastructure/browser checks remain disclosed limits, not extra licensing decisions. Routine notice assembly and broken-link cleanup after your scope choice are implementation work, not decisions you need to make now.
