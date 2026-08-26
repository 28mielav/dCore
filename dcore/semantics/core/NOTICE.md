# DenizenCore-lite provenance

This directory is a clean Python reimplementation of selected behavior from
Denizen-Core: `ScriptBuilder`, `ScriptEntry`, `ScriptQueue`, `TagManager`, and
the queue control commands `define`, `if`, `choose`, `repeat`, `while`, and
`stop`.

Reference source: [DenizenScript/Denizen-Core](https://github.com/DenizenScript/Denizen-Core),
commit `273ad9fc7eaf2e4d63de0332adb062449a9252f0`, inspected 2026-08-10.

Copyright (c) 2019-2026 The Denizen Script Team. The reference project is
licensed under the MIT License. This derived work retains the required notice;
see `LICENSE.md`.

It intentionally does not port Bukkit/NMS access, scheduling, objects, or all
commands/tags. Those are platform adapters and remain runtime/JAR proof work.
