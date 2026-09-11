dCore 0.82 improves script checks, historical API lookup and resource-pack analysis, and ships three standalone packages.

| Download | Contents |
| :--- | :--- |
| `dcore-cli-0.82.zip` | CLI launcher, Python runtime and knowledge database |
| `dcore-skill-0.82.zip` | Installable Skill with runtime, database, guides and editor adapters |
| `dcore-gpt-0.82.zip` | Custom GPT instructions, bootstrap and Knowledge files |
| `SHA256SUMS.txt` | SHA-256 hashes of the three archives |

CLI and Skill require Python 3.12+. Keep each extracted directory together. For GPT, follow `START_HERE.txt` and enable Code Interpreter & Data Analysis.

### Changes

- Version-aware shader interface inventories for all 34 stable Minecraft clients from 1.16.5 through 26.2; 1.21.11 and 1.21.8 are priority targets.
- Pack metadata, active overlays, built-in shader paths and post-processing interfaces checked against the selected client.
- Improved cancellation and loop diagnostics, plus display-entity version and camera-follow advice.
- Historical Denizen source profiles and version-selected code cards. Uncertain dependencies stay explicit.
- Self-contained CLI, Skill and GPT packages using the same core, tested outside the source checkout.
- Safer archive restoration, private POSIX key-file permissions and exclusion of Python caches from Skill builds.

### Upgrading from 0.70–0.76

The old MCP delivery was removed in 0.75. Use the CLI, installed Skill or GPT bundle. Replace the complete old Skill directory with the extracted `dcore/` directory; copying `SKILL.md` alone does not install its runtime. Project targets can now be stored in `dcore.toml`.

### Verification and limits

Automated regression tests, database integrity, source manifest checks and independent delivery execution are release gates. SHA-256 sums describe the actual attached files. Basic analysis has no external Python dependency; encrypted packing uses the optional cryptography extra.

Minecraft/Paper runtime, GPU rendering and the hosted GPT upload interface were not exercised. A clean static result is not a gameplay guarantee. See the [release audit](https://github.com/28mielav/dCore/blob/v0.82.0/docs/AUDIT-0.82.md) for scope and remaining limitations.
