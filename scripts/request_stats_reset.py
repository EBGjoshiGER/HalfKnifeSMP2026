"""Send a reset to the live mod. Never edit counters behind its in-memory state."""
import ftplib
import io
import json
import os
import re
import time
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone

from sync_playtime import download
from pathlib import PurePosixPath


def prepare_request(ftp, target, scope):
    if scope not in {"active", "all"}:
        raise ValueError("Unknown reset scope")
    properties = dict(line.split("=", 1) for line in download(ftp, "server.properties").splitlines()
                      if "=" in line and not line.lstrip().startswith("#"))
    world = properties.get("level-name", "world").strip()
    path = PurePosixPath(world)
    if not world or path.is_absolute() or ".." in path.parts or any(c in world for c in "\r\n\\"):
        raise ValueError("Invalid world path")
    names = json.loads(download(ftp, "whitelist.json"))
    if not isinstance(names, list):
        raise ValueError("Invalid whitelist")
    if target != "ALL":
        if not re.fullmatch(r"[A-Za-z0-9_]{1,16}", target):
            raise ValueError("Enter an exact Minecraft name or ALL")
        matches = [entry for entry in names if entry.get("name", "").casefold() == target.casefold()]
        if len(matches) != 1:
            raise ValueError("Player name is not uniquely whitelisted")
        target = str(UUID(matches[0]["uuid"]))
    folder = f"{world}/config/halfknife-active-playtime"
    store = json.loads(download(ftp, folder + "/playtime.json"))
    if store.get("resetProtocol") != 1:
        raise RuntimeError("Reset support is not active. Install mod 1.2.0 and restart the server first.")
    expires = datetime.now(timezone.utc) + timedelta(seconds=90)
    return folder, {"id": str(uuid4()), "target": target, "scope": scope, "expiresAt": expires.isoformat()}


def send_request(ftp, folder, request, timeout=90):
    pending = folder + "/reset-request.json"
    # Never replace an unacknowledged request; it could run when the server starts.
    try:
        download(ftp, pending)
    except ftplib.error_perm as error:
        if not str(error).startswith("550"):
            raise
    else:
        raise RuntimeError("A reset is already pending. Start the updated server and wait for its result.")
    temporary = folder + "/reset-" + request["id"] + ".upload"
    ftp.storbinary("STOR " + temporary, io.BytesIO((json.dumps(request) + "\n").encode()))
    ftp.rename(temporary, pending)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = json.loads(download(ftp, folder + "/reset-result.json"))
        except ftplib.error_perm as error:
            if not str(error).startswith("550"):
                raise
        else:
            if result.get("id") == request["id"]:
                if result.get("success") is not True:
                    raise RuntimeError("Server rejected reset: " + result.get("message", "unknown error"))
                # Mod publishes the receipt before removing the request.
                while time.monotonic() < deadline:
                    try:
                        download(ftp, pending)
                    except ftplib.error_perm as error:
                        if str(error).startswith("550"):
                            return result
                        raise
                    time.sleep(1)
                break
        time.sleep(2)
    # Cancel our unacknowledged request so a failed button click cannot reset later.
    try:
        if json.loads(download(ftp, pending)).get("id") == request["id"]:
            ftp.delete(pending)
    except ftplib.error_perm:
        pass
    raise TimeoutError("No completed reset acknowledgement. Check that mod 1.2.0 is running; no success was reported.")


def main():
    ftp = ftplib.FTP(timeout=30)
    try:
        ftp.connect(os.environ["FTP_HOST"], int(os.environ.get("FTP_PORT") or "21"))
        ftp.login(os.environ["FTP_USER"], os.environ["FTP_PASSWORD"])
        folder, request = prepare_request(ftp, os.environ["RESET_TARGET"].strip(), os.environ["RESET_SCOPE"])
        result = send_request(ftp, folder, request)
        print(result["message"])
        print("Backup:", folder + "/reset-backups/" + request["id"])
    finally:
        ftp.close()


if __name__ == "__main__":
    main()
