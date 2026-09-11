# Security policy

## Reporting a vulnerability

Please do not open a public issue for a suspected security vulnerability.

Use GitHub private vulnerability reporting for this repository. Include affected version, reproduction steps, impact, and any relevant proof or logs. The maintainer will acknowledge the report, reproduce it where possible, and coordinate a fix before public disclosure.

## Scope

dCore analysis findings are engineering guidance. They do not replace security testing of a Minecraft server, plugin, addon, client, or resource pack.

Security fixes target the latest release, currently 0.82. Older builds should be upgraded.

Basic lint and lookup run offline and do not execute the submitted Denizen scripts. Update/import commands deliberately fetch upstream sources or call local Git. Only execute GPT bootstrap files and install Skills from a trusted release: they contain Python code.

Keep packing master keys outside your project and server. New keys use owner-only permissions on POSIX; on Windows, store them in a user-private directory protected by Windows ACLs. Never include keys, credentials or private server logs in bug reports.
