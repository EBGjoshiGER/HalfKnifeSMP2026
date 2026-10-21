"""Boot an isolated Fabric server with the new mod and the installed Fabric API."""
import ftplib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request


def main():
    root = Path("temp/active-playtime-smoke")
    (root / "mods").mkdir(parents=True, exist_ok=True)
    ftp = ftplib.FTP(timeout=30)
    try:
        ftp.connect(os.environ["FTP_HOST"], int(os.environ.get("FTP_PORT") or "21"))
        ftp.login(os.environ["FTP_USER"], os.environ["FTP_PASSWORD"])
        with (root / "mods/fabric-api.jar").open("wb") as output:
            ftp.retrbinary("RETR mods/fabric-api-0.160.0+26.2.jar", output.write)
    finally:
        ftp.close()
    shutil.copyfile("mods/halfknife-active-playtime/build/libs/halfknife-active-playtime-1.0.0.jar", root / "mods/halfknife-active-playtime.jar")
    with urllib.request.urlopen("https://meta.fabricmc.net/v2/versions/installer", timeout=30) as response:
        installer = next(item["version"] for item in json.load(response) if item.get("stable"))
    url = f"https://meta.fabricmc.net/v2/versions/loader/26.2/0.19.3/{installer}/server/jar"
    with urllib.request.urlopen(url, timeout=60) as response:
        (root / "server.jar").write_bytes(response.read())
    (root / "eula.txt").write_text("eula=true\n")
    (root / "server.properties").write_text("server-port=0\nonline-mode=false\nview-distance=2\nsimulation-distance=2\nlevel-name=smoke-world\nmax-players=1\n")
    with (root / "smoke.log").open("w") as log:
        process = subprocess.Popen(["java", "-Xmx1G", "-jar", "server.jar", "nogui"], cwd=root, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, text=True)
        try:
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                text = (root / "smoke.log").read_text()
                if 'Done (' in text:
                    # Verify packet-handler mixins too; class may be lazy-loaded on an empty server.
                    process.stdin.write("stop\n")
                    process.stdin.flush()
                    process.wait(timeout=40)
                    data = json.loads((root / "smoke-world/config/halfknife-active-playtime/playtime.json").read_text())
                    assert data["mode"] == "active" and data["afkTimeoutSeconds"] == 300
                    assert data["players"] == []
                    if process.returncode != 0:
                        raise RuntimeError("Smoke server failed on shutdown")
                    print("Isolated Fabric 26.2 server booted and shut down cleanly; active-playtime JSON verified.")
                    return
                if process.poll() is not None:
                    raise RuntimeError("Smoke server stopped before startup completed")
                time.sleep(2)
            raise TimeoutError("Smoke server startup timed out")
        except Exception:
            print((root / "smoke.log").read_text()[-16000:])
            raise
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
