"""Publish whitelisted players' active time; never fall back to AFK-inclusive stats."""
import ftplib
import io
import json
import os
import re
from datetime import datetime
from pathlib import Path, PurePosixPath
from uuid import UUID


def download(ftp, path):
    buffer = io.BytesIO()
    ftp.retrbinary(f"RETR {path}", buffer.write)
    return buffer.getvalue().decode("utf-8-sig")


def read_ranking(ftp):
    properties = {}
    for line in download(ftp, "server.properties").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            properties[key.strip()] = value.strip()
    world = properties.get("level-name", "world")
    world_path = PurePosixPath(world)
    if not world or world_path.is_absolute() or ".." in world_path.parts or any(c in world for c in "\r\n\\"):
        raise ValueError("Invalid world path")
    whitelist = json.loads(download(ftp, "whitelist.json"))
    if not isinstance(whitelist, list):
        raise ValueError("Invalid whitelist")
    names = {}
    for player in whitelist:
        if isinstance(player, dict) and re.fullmatch(r"[A-Za-z0-9_]{1,16}", player.get("name", "")):
            names[str(UUID(player["uuid"]))] = player["name"]
    path = f"{world}/config/halfknife-active-playtime/playtime.json"
    try:
        data = json.loads(download(ftp, path))
    except ftplib.error_perm as error:
        if not str(error).startswith("550"):
            raise
        print("Active-playtime export not available yet; waiting for the mod to start.")
        return {"mode": "pending", "players": [], "updatedAt": None, "afkTimeoutSeconds": 300}
    if data.get("schema") != 1 or data.get("mode") != "active" or data.get("afkTimeoutSeconds") != 300 or not isinstance(data.get("players"), list):
        raise ValueError("Invalid active-playtime export")
    updated_at = data.get("updatedAt")
    if not isinstance(updated_at, str):
        raise ValueError("Missing export timestamp")
    datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    players = []
    seen = set()
    for entry in data["players"]:
        uuid = str(UUID(entry["uuid"]))
        if uuid in seen:
            raise ValueError("Duplicate active-playtime entry")
        seen.add(uuid)
        active = entry.get("activeMillis")
        if isinstance(active, bool) or not isinstance(active, int) or active < 0:
            raise ValueError("Invalid active playtime")
        if uuid in names and active >= 1000:
            players.append({"name": names[uuid], "seconds": active // 1000})
    players.sort(key=lambda player: (-player["seconds"], player["name"].casefold()))
    return {"mode": "active", "players": players, "updatedAt": updated_at, "afkTimeoutSeconds": 300}


def main():
    ftp = ftplib.FTP(timeout=30)
    try:
        ftp.connect(os.environ["FTP_HOST"], int(os.environ.get("FTP_PORT") or "21"))
        ftp.login(os.environ["FTP_USER"], os.environ["FTP_PASSWORD"])
        result = read_ranking(ftp)
    finally:
        ftp.close()
    output = Path("data/playtime.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if not output.exists() or output.read_text(encoding="utf-8") != content:
        temporary = output.with_suffix(".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(output)
    print(f"Active playtime: {result['mode']}; players: {len(result['players'])}")


if __name__ == "__main__":
    main()
