"""Publish only names and saved play time from whitelisted Minecraft players."""

import ftplib
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from uuid import UUID


def download(ftp, path):
    buffer = io.BytesIO()
    ftp.retrbinary(f"RETR {path}", buffer.write)
    return buffer.getvalue().decode("utf-8-sig")


def read_players(ftp):
    properties = {}
    for line in download(ftp, "server.properties").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            properties[key.strip()] = value.strip()
    world = properties.get("level-name", "world")
    world_path = PurePosixPath(world)
    if not world or world_path.is_absolute() or ".." in world_path.parts or any(c in world for c in "\r\n\\"):
        raise ValueError("Invalid world path in server.properties")
    whitelist = json.loads(download(ftp, "whitelist.json"))
    if not isinstance(whitelist, list):
        raise ValueError("Invalid whitelist")

    # Listing the directory first distinguishes a missing player's stats from
    # an inaccessible world, which must fail instead of erasing the ranking.
    try:
        ftp.cwd(f"{world}/players/stats")
    except ftplib.error_perm as error:
        if not str(error).startswith("550"):
            raise
        ftp.cwd(f"{world}/stats")
    available = {PurePosixPath(name).name for name in ftp.nlst()}
    players = []
    seen = set()
    for player in whitelist:
        name = player.get("name", "")
        uuid = str(UUID(player["uuid"]))
        if not re.fullmatch(r"[A-Za-z0-9_]{1,16}", name) or uuid in seen:
            continue
        seen.add(uuid)
        filename = f"{uuid}.json"
        if filename not in available:
            continue
        # A transfer/JSON error aborts the update, retaining the previous file.
        stats = json.loads(download(ftp, filename))
        custom = stats.get("stats", {}).get("minecraft:custom", {})
        ticks = custom.get("minecraft:play_time", custom.get("minecraft:play_one_minute", 0))
        if isinstance(ticks, bool) or not isinstance(ticks, int) or ticks < 0:
            raise ValueError(f"Invalid play time for {name}")
        if ticks > 0:
            players.append({"name": name, "seconds": ticks // 20})
    return sorted(players, key=lambda player: (-player["seconds"], player["name"].casefold()))


def main():
    ftp = ftplib.FTP(timeout=30)
    try:
        ftp.connect(os.environ["FTP_HOST"], int(os.environ.get("FTP_PORT") or "21"))
        ftp.login(os.environ["FTP_USER"], os.environ["FTP_PASSWORD"])
        players = read_players(ftp)
    finally:
        ftp.close()
    result = {"players": players, "updatedAt": datetime.now(timezone.utc).isoformat()}
    output = Path("data/playtime.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(f"Playtime for {len(players)} players synchronized.")


if __name__ == "__main__":
    main()
