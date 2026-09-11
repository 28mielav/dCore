"""Conservative carrier checks over parsed commands, not comments or names."""
import re


def lint_visual_carriers(ir, minecraft=None):
    results = []
    if minecraft and re.fullmatch(r"1\.\d+(?:\.\d+)?", minecraft):
        version = tuple(int(n) for n in minecraft.split("."))
        if version < (1, 19, 4):
            for command in ir.commands:
                if command.name in {"spawn", "fakespawn"} and re.match(r"(?:e@|minecraft:)?(?:item_display|text_display|block_display|interaction)\b", command.arguments.casefold()):
                    results.append({"code": "visual_entity_version_unavailable", "severity": "error", "line": command.line,
                        "layer": "api", "source": "Minecraft Java 1.19.4 release notes",
                        "message": f"Display and interaction entities were introduced in 1.19.4; Minecraft {minecraft} does not provide them.",
                        "suggestion": "Choose a target-appropriate carrier/API; changing the Denizen build alone cannot add this vanilla entity type."})
    for section in ir.containers:
        saves, carriers = set(), set()
        loops = []
        for command in ir.commands:
            if not section.source.line < command.line <= section.end_line:
                continue
            while loops and loops[-1] >= command.source.column:
                loops.pop()
            args = command.arguments.casefold()
            if command.name in {"repeat", "foreach", "while"} and args.rstrip().endswith(":"):
                loops.append(command.source.column)
            saved = re.search(r"\bsave:([\w-]+)", args)
            if saved:
                saves.discard(saved[1])
                if command.name in {"spawn", "fakespawn"} and re.match(r"(?:item|text|block)_display\b", args):
                    saves.add(saved[1])
            if command.name == "define":
                name, _, value = args.partition(" ")
                carriers.discard(name)
                saved = re.fullmatch(r"<entry\[([\w-]+)\]\.spawned_entity>", value.strip())
                if saved and saved[1] in saves:
                    carriers.add(name)
            first = re.match(r"<\[([\w-]+)\]>", args)
            if not first or first[1] not in carriers:
                continue
            if command.name == "teleport" and loops and re.search(r"<[^\s]*\.eye_location\b", args):
                results.append({"code": "screen_carrier_tick_follow", "severity": "warning", "line": command.line,
                    "layer": "visual", "source": "parsed display spawn/save/define and loop",
                    "message": "A display follows eye_location inside a server loop; packet updates cannot guarantee frame-synchronous screen attachment.",
                    "suggestion": "Keep carrier visibility/culling separate from client screen placement. Verify rapid camera turns, FOV 30/110, F1/F5 and movement; a larger view_range alone does not solve this."})
            if command.name == "mount":
                results.append({"code": "display_mount_projection_unverified", "severity": "information", "line": command.line,
                    "layer": "visual", "source": "parsed display carrier mount",
                    "message": "Mount binds the display to an entity, not to the rendered camera or screen. Pivot/translation do not prove fullscreen coverage.",
                    "suggestion": "For a screen effect verify the actual shader route, pre-draw culling and viewer isolation independently; preserve ordinary world-mounted displays when that is the intended result."})
    return results
