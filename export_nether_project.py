"""Create the public website snapshot from the Nether Project server files."""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


ITEM_NAMES = {
    "minecraft:obsidian": "Obsidian",
    "minecraft:iron_ingot": "Eisenbarren",
    "minecraft:gold_ingot": "Goldbarren",
    "minecraft:diamond": "Diamanten",
    "minecraft:redstone": "Redstone",
    "minecraft:lapis_lazuli": "Lapislazuli",
}
MAX_SAFE_INTEGER = 2**53 - 1


def integer(value, label, minimum=0):
    if type(value) is not int or not minimum <= value <= MAX_SAFE_INTEGER:
        raise ValueError(f"{label}: invalid nonnegative integer")
    return value


def mapping(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label}: expected an object")
    return value


def snapshot(config, progress, now=None):
    mapping(config, "config")
    mapping(progress, "progress")
    requirements = mapping(config.get("requirements"), "requirements")
    donated = mapping(progress.get("donated"), "donated")
    points = mapping(progress.get("playerPoints"), "playerPoints")
    names = mapping(progress.get("playerNames"), "playerNames")
    if not requirements:
        raise ValueError("requirements must not be empty")
    for field in ("active", "paused", "completed"):
        if type(progress.get(field)) is not bool:
            raise ValueError(f"{field}: expected a boolean")

    resources = []
    for item, target in requirements.items():
        integer(target, f"requirements.{item}", minimum=1)
        # Missing materials are not silently presented as zero.
        count = integer(donated.get(item), f"donated.{item}")
        resources.append({
            "id": item,
            "name": ITEM_NAMES.get(item, item),
            "donated": count,
            "required": target,
        })

    leaderboard = []
    for player_id, score in points.items():
        integer(score, f"playerPoints.{player_id}")
        if score == 0:
            continue
        name = names.get(player_id)
        if name is None or name == "":
            name = "Unbekannter Spieler"
        if not isinstance(name, str) or len(name) > 100:
            raise ValueError(f"Invalid player name for {player_id}")
        leaderboard.append({"name": name, "points": score})
    leaderboard.sort(key=lambda player: (-player["points"], player["name"].casefold()))
    previous_points = None
    rank = 0
    for position, player in enumerate(leaderboard, 1):
        if player["points"] != previous_points:
            rank = position
        player["rank"] = rank
        previous_points = player["points"]

    status = (
        "completed" if progress["completed"] else
        "paused" if progress["paused"] else
        "active" if progress["active"] else "not_started"
    )
    return {
        "schemaVersion": 1,
        "syncedAt": (now or datetime.now(timezone.utc)).isoformat(),
        "status": status,
        "resources": resources,
        "leaderboard": leaderboard,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--progress", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    progress = json.loads(args.progress.read_text(encoding="utf-8-sig"))
    result = snapshot(config, progress)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, args.output)
    print(f"Nether-Projekt: {result['status']}, {len(result['leaderboard'])} Spieler")


if __name__ == "__main__":
    main()
