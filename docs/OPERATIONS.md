# Operations

## Routine maintenance

The private workflow runs Monday at 04:23 UTC and on manual dispatch. A green run either confirms the current bundle or publishes/replaces the private release named `YYYY-MM-DD`.

Visual repositories are monitored, not blindly ingested. `visual_review_required=true` means a registered repository moved beyond its curated commit. Existing knowledge remains usable and pinned; review the upstream diff before advancing its indexed SHA or copying code.

## Install or update the Custom GPT

1. Call `getLatestDcoreRelease` and compare `bundle_sha256` with the attached `manifest.json`.
2. If different, download and unpack the latest private dated release.
3. Remove the old seven Knowledge attachments.
4. Upload the seven files inside `GPT_Knowledge`.
5. Replace the GPT Instructions field with `GPT_Instructions/DCORE_INSTRUCTIONS.txt`.
6. If `Custom_GPT_Action/openapi.yaml` has a newer schema version than the installed Action, re-import it; keep the existing authentication key.
7. Save the GPT; test `checkDcoreBridge`, `getLatestDcoreRelease`, one DenizenM Meta query, one route comparison and one lint invocation.

Do not upload `update_knowledge.py`, source clones, secrets or local work directories as GPT Knowledge.

## Force a release

Open **Actions -> Maintain dCore knowledge -> Run workflow**, enable **Publish today's verified bundle**, and run it. A second run on the same UTC date replaces that date's release.

## Required secrets

GitHub repository secrets:

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

Cloudflare Worker and Custom GPT Action share only the Bearer value `DCORE_ACTION_KEY`. Never commit it or put it in a release/Knowledge file.

## Failure recovery

- **Before validation:** rerun later; canonical Knowledge was not touched.
- **Validation failure:** download the diagnostic artifact, fix the failing invariant/test, and rerun. Do not force-install the candidate.
- **Worker deploy failure:** database/release may be valid, but Action freshness stays on the previous deployed manifest until a successful deploy.
- **Action 401:** rotate `DCORE_ACTION_KEY` in the Worker and GPT Action authentication.
- **Manifest mismatch:** rerun maintenance; never claim current Knowledge from bridge health alone.
- **Database corruption:** restore `knowledge/dcore.sqlite` and `manifest.json` from the latest verified private release, then run all validation before pushing.

## Local release check

Use the bundled/current Python runtime:

```text
python -m unittest tools/test_dcore_lint.py tools/test_dcore_design.py tools/test_dcore_rp_lint.py tools/test_update_knowledge.py tools/test_build_gpt_bundle.py
python tools/test_retrieval.py --db knowledge/dcore.sqlite
python tools/verify_knowledge.py --db knowledge/dcore.sqlite --output knowledge/manifest.json [all seven artifact arguments]
```

Static success is not server/client runtime proof. Preserve the runtime checklist produced by the relevant tool.
