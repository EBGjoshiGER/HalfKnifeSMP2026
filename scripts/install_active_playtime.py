"""Install the tested active-time bridge and Tab patch with backups and rollback."""
import ftplib
import hashlib
import io
import os
from datetime import datetime, timezone
from pathlib import Path
from tab_active_bridge import patch_tab_jar


def read(ftp, path):
    buffer = io.BytesIO()
    ftp.retrbinary("RETR " + path, buffer.write)
    return buffer.getvalue()


def main():
    mod = Path("mods/halfknife-active-playtime/build/libs/halfknife-active-playtime-1.2.0.jar").read_bytes()
    tested_tab = Path("temp/active-playtime-smoke/mods/tab-info.jar").read_bytes()
    target_mod = "mods/halfknife-active-playtime-1.2.0.jar"
    target_tab = "mods/tab-info-0.3.0+mod.jar"
    ftp = ftplib.FTP(timeout=30)
    committed = []
    try:
        ftp.connect(os.environ["FTP_HOST"], int(os.environ.get("FTP_PORT") or "21"))
        ftp.login(os.environ["FTP_USER"], os.environ["FTP_PASSWORD"])
        installed = {p.rsplit("/", 1)[-1] for p in ftp.nlst("mods")}
        previous = sorted(name for name in installed if name.startswith("halfknife-active-playtime-") and name.endswith(".jar"))
        if len(previous) != 1 or previous[0] not in {"halfknife-active-playtime-1.0.0.jar", "halfknife-active-playtime-1.1.0.jar", "halfknife-active-playtime-1.2.0.jar"}:
            raise RuntimeError("Unexpected active-playtime installation; refusing to overwrite")
        old_mod_path = "mods/" + previous[0]
        old_mod = read(ftp, old_mod_path)
        original_tab = read(ftp, target_tab)
        if patch_tab_jar(original_tab) != tested_tab:
            raise RuntimeError("Tab Info changed since the smoke test; refusing to overwrite")
        operations = []
        if old_mod != mod:
            operations.append((target_mod, mod, old_mod_path))
        if original_tab != tested_tab:
            operations.append((target_tab, tested_tab, target_tab))
        for target, content, source in operations:
            ftp.storbinary("STOR " + target + ".upload", io.BytesIO(content))
            downloaded = read(ftp, target + ".upload")
            if hashlib.sha256(downloaded).digest() != hashlib.sha256(content).digest():
                raise RuntimeError("Uploaded file checksum mismatch")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        for target, content, source in operations:
            backup = source + ".before-active-" + stamp + ".bak"
            ftp.rename(source, backup)
            committed.append((target, source, backup))
            ftp.rename(target + ".upload", target)
        print("Active-playtime 1.2.0 and Tab Info bridge installed; checksums verified; previous JARs backed up.")
        print("Restart the server to activate Tab and lobby integration. Player data and reward history were not modified.")
    except Exception:
        for target, source, backup in reversed(committed):
            try:
                try:
                    ftp.delete(target)
                except ftplib.error_perm:
                    pass
                ftp.rename(backup, source)
            except Exception as rollback_error:
                print("Rollback requires manual attention:", type(rollback_error).__name__)
        raise
    finally:
        ftp.close()


if __name__ == "__main__":
    main()
