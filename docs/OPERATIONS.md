# Operations

## Routine maintenance

No weekly action is required. The workflow runs every Monday at 04:23 UTC.

A successful run can produce either:

- no release: upstream commits and Knowledge were already current;
- a `YYYY-MM-DD` release: a changed candidate passed validation.

## Force a fresh dated bundle

Open **Actions → Maintain dCore knowledge → Run workflow**, enable **Publish today's verified bundle**, and run it. A second run on the same UTC date replaces that day's release instead of creating duplicates.

## Update Custom GPT Knowledge

1. Ask dCore to call `getLatestDcoreRelease`.
2. Compare the returned SHA-256 with the attached `manifest.json`.
3. If identical, do nothing.
4. If different, download the newest private dated release.
5. Replace the Custom GPT instruction field with `DCORE_INSTRUCTIONS.txt`.
6. Replace Knowledge attachments with `dcore.sqlite`, `manifest.json`, `dcore_lint.py` and `DCORE_LINT_CONTRACT.example.json`.
7. Keep `update_knowledge.py` only in local/admin environments; the Custom GPT Action checks freshness but cannot persistently rewrite its own attachments.
8. Save/update the GPT and repeat both Action tests.

The platform does not permit the Action to perform step 5 automatically.

## Required secrets

GitHub Actions repository secrets:

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

Cloudflare Worker secret:

- `DCORE_ACTION_KEY`

Custom GPT Action authentication uses the same `DCORE_ACTION_KEY` as a Bearer API key. Never put any secret in the repository, release archive or GPT Knowledge.

## Recovery

### Workflow fails before validation

Leave the repository untouched and rerun later. The last committed database is still the last known-good version.

### Workflow fails during Worker deployment

Inspect `Deploy freshness bridge`. Fix credentials or deployment configuration and rerun. The previously deployed manifest remains readable.

### Action returns 401

The GPT and Worker keys differ. Generate one replacement key, update the Worker secret, then update GPT Action authentication.

### Action reports an older SHA than GitHub

Rerun the workflow. Worker deployment is deliberately after candidate validation/commit.

### Database corruption suspected

Do not overwrite the repository seed. Download the last dated release whose manifest has `status: verified`, confirm its published SHA-256 file, restore `knowledge/dcore.sqlite`, then run the workflow.

## Key rotation

Rotate `DCORE_ACTION_KEY` if it is exposed. Rotate `CLOUDFLARE_API_TOKEN` if GitHub deployment credentials are exposed. They have different authority and must never be reused.
