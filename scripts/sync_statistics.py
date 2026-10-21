"""Export saved statistics and active playtime for whitelisted players only."""
import ftplib
import io
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from uuid import UUID

IDENTIFIER = re.compile(r"[a-z0-9_.-]+:[a-z0-9_./-]+")


def official_labels():
    """Cache German vanilla names; unavailable translations never block stats."""
    cache = Path("data/stat-labels.json")
    try:
        if cache.exists():
            saved = json.loads(cache.read_text(encoding="utf-8"))
            if saved.get("minecraftVersion") == "26.2" and saved.get("labels"):
                return saved["labels"]
        def get_json(url):
            with urllib.request.urlopen(url, timeout=20) as response:
                return json.load(response)
        manifest = get_json("https://piston-meta.mojang.com/mc/game/version_manifest_v2.json")
        version = next(entry for entry in manifest["versions"] if entry["id"] == "26.2")
        version_data = get_json(version["url"])
        assets = get_json(version_data["assetIndex"]["url"])
        sha = assets["objects"]["minecraft/lang/de_de.json"]["hash"]
        language = get_json(f"https://resources.download.minecraft.net/{sha[:2]}/{sha}")
        labels = {}
        for key, value in language.items():
            parts = key.split(".")
            if len(parts) == 3 and parts[0] in {"item", "block", "entity", "stat"} and parts[1] == "minecraft" and isinstance(value, str):
                labels["minecraft:" + parts[2]] = value
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"minecraftVersion": "26.2", "labels": labels}, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return labels
    except Exception as error:
        print("Optional German labels not available:", type(error).__name__)
        return {}


def download(ftp, path):
    data = io.BytesIO()
    ftp.retrbinary("RETR " + path, data.write)
    return data.getvalue().decode("utf-8-sig")


def valid_count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def clean_stats(data):
    groups = data.get("stats")
    if not isinstance(groups, dict):
        raise ValueError("Invalid Minecraft statistics file")
    result = {}
    for group, entries in groups.items():
        if not IDENTIFIER.fullmatch(group) or not isinstance(entries, dict):
            raise ValueError("Invalid statistics category")
        cleaned = {}
        for key, value in entries.items():
            if not IDENTIFIER.fullmatch(key) or not valid_count(value):
                raise ValueError("Invalid statistic")
            cleaned[key] = value
        result[group] = cleaned
    return result


def summarize(stats, active_seconds):
    custom = stats.get("minecraft:custom", {})
    mined = stats.get("minecraft:mined", {})
    return {
        "activeSeconds": active_seconds,
        "totalSeconds": custom.get("minecraft:play_time", custom.get("minecraft:play_one_minute", 0)) // 20,
        "deaths": custom.get("minecraft:deaths", 0),
        "blocksMined": sum(mined.values()),
        "mobKills": custom.get("minecraft:mob_kills", 0),
        "playerKills": custom.get("minecraft:player_kills", 0),
        "distanceCm": sum(value for key, value in custom.items() if key.startswith("minecraft:") and key.endswith("_one_cm")),
        "diamondsMined": mined.get("minecraft:diamond_ore", 0) + mined.get("minecraft:deepslate_diamond_ore", 0),
        "totemsUsed": stats.get("minecraft:used", {}).get("minecraft:totem_of_undying", 0),
        "damageDealt": custom.get("minecraft:damage_dealt", 0) / 10,
        "itemsCrafted": sum(stats.get("minecraft:crafted", {}).values()),
        "jumps": custom.get("minecraft:jump", 0),
        "elytraCm": custom.get("minecraft:aviate_one_cm", 0),
    }


def collect(ftp):
    properties = {}
    for line in download(ftp, "server.properties").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            properties[key.strip()] = value.strip()
    world = properties.get("level-name", "world")
    path = PurePosixPath(world)
    if not world or path.is_absolute() or ".." in path.parts or any(char in world for char in "\r\n\\"):
        raise ValueError("Invalid world path")
    whitelist = json.loads(download(ftp, "whitelist.json"))
    if not isinstance(whitelist, list):
        raise ValueError("Invalid whitelist")
    names = {}
    for entry in whitelist:
        if not isinstance(entry, dict) or not re.fullmatch(r"[A-Za-z0-9_]{1,16}", entry.get("name", "")):
            raise ValueError("Invalid whitelist entry")
        names[str(UUID(entry["uuid"]))] = entry["name"]

    active = None
    active_updated = None
    try:
        saved = json.loads(download(ftp, f"{world}/config/halfknife-active-playtime/playtime.json"))
    except ftplib.error_perm as error:
        if not str(error).startswith("550"):
            raise
    else:
        if saved.get("schema") != 1 or saved.get("mode") != "active" or not isinstance(saved.get("players"), list):
            raise ValueError("Invalid active playtime export")
        active_updated = saved.get("updatedAt")
        if not isinstance(active_updated, str):
            raise ValueError("Missing active-playtime timestamp")
        datetime.fromisoformat(active_updated.replace("Z", "+00:00"))
        active = {}
        for entry in saved["players"]:
            uuid = str(UUID(entry["uuid"]))
            value = entry.get("activeMillis")
            if not valid_count(value) or uuid in active:
                raise ValueError("Invalid active-playtime entry")
            active[uuid] = value // 1000

    root = ftp.pwd()
    stats_by_uuid = {}
    try:
        try:
            ftp.cwd(f"{world}/players/stats")
        except ftplib.error_perm as error:
            if not str(error).startswith("550"):
                raise
            ftp.cwd(f"{world}/stats")
        available = {PurePosixPath(name).name for name in ftp.nlst()}
        for uuid in names:
            filename = uuid + ".json"
            if filename in available:
                stats_by_uuid[uuid] = clean_stats(json.loads(download(ftp, filename)))
    finally:
        ftp.cwd(root)
    players = []
    for uuid, name in sorted(names.items(), key=lambda pair: pair[1].casefold()):
        stats = stats_by_uuid.get(uuid, {})
        seconds = None if active is None else active.get(uuid, 0)
        players.append({"uuid": uuid, "name": name, "hasStats": uuid in stats_by_uuid,
                        "stats": stats, "summary": summarize(stats, seconds)})
    return {"schema": 1, "updatedAt": datetime.now(timezone.utc).isoformat(),
            "activeMode": "pending" if active is None else "active", "activeUpdatedAt": active_updated,
            "players": players}


def main():
    ftp = ftplib.FTP(timeout=30)
    try:
        ftp.connect(os.environ["FTP_HOST"], int(os.environ.get("FTP_PORT") or "21"))
        ftp.login(os.environ["FTP_USER"], os.environ["FTP_PASSWORD"])
        result = collect(ftp)
    finally:
        ftp.close()
    names = official_labels()
    used_ids = {key for player in result["players"] for entries in player["stats"].values() for key in entries}
    result["labels"] = {key: names[key] for key in sorted(used_ids) if key in names}
    output = Path("data/statistics.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(f"Statistics synchronized: {len(result['players'])} whitelisted players; "
          f"{sum(player['hasStats'] for player in result['players'])} saved statistics files; active mode: {result['activeMode']}")


if __name__ == "__main__":
    main()
