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
import zipfile
from datetime import datetime, timedelta, timezone
from tab_active_bridge import patch_tab_jar


def main():
    root = Path("temp/active-playtime-smoke")
    (root / "mods").mkdir(parents=True, exist_ok=True)
    ftp = ftplib.FTP(timeout=30)
    try:
        ftp.connect(os.environ["FTP_HOST"], int(os.environ.get("FTP_PORT") or "21"))
        ftp.login(os.environ["FTP_USER"], os.environ["FTP_PASSWORD"])
        files = [
            "fabric-api-0.160.0+26.2.jar", "tab-info-0.3.0+mod.jar",
            "halfknifequiz-1.0.0.jar", "halfknife-leaderboards-1.2.3.jar", "playtime-rewards-1.7.3.jar",
            "rpg_attribute_reworked.jar", "nether-project-2.3.0.jar", "end-project-1.0.0.jar",
            "LuckPerms-Fabric-5.5.57.jar", "cloth-config-26.2.155.jar",
            "architectury-fabric-21.1.9.jar", "placeholder-api-3.1.0-beta.1+26.2.jar",
            "PuzzlesLib-v26.2.3-mc26.2.x-Fabric.jar", "collective-26.2.0-8.40.jar",
            "ForgeConfigAPIPort-v26.2.1-mc26.2.x-Fabric.jar",
            "dataanchor-fabric-26.2-5.0.0.3.jar", "fabric-language-kotlin-1.14.1+kotlin.2.4.20.jar"
        ]
        for filename in files:
            buffer = io.BytesIO()
            ftp.retrbinary("RETR mods/" + filename, buffer.write)
            content = buffer.getvalue()
            if filename.startswith("tab-info-"):
                content = patch_tab_jar(content)
                filename = "tab-info.jar"
            (root / "mods" / filename).write_bytes(content)
    finally:
        ftp.close()
    shutil.copyfile("mods/halfknife-active-playtime/build/libs/halfknife-active-playtime-1.2.0.jar", root / "mods/halfknife-active-playtime.jar")
    with urllib.request.urlopen("https://meta.fabricmc.net/v2/versions/installer", timeout=30) as response:
        installer = next(item["version"] for item in json.load(response) if item.get("stable"))
    url = f"https://meta.fabricmc.net/v2/versions/loader/26.2/0.19.5/{installer}/server/jar"
    with urllib.request.urlopen(url, timeout=60) as response:
        (root / "server.jar").write_bytes(response.read())
    (root / "eula.txt").write_text("eula=true\n")
    (root / "server.properties").write_text("server-port=0\nonline-mode=false\nview-distance=2\nsimulation-distance=2\nlevel-name=smoke-world\nmax-players=1\n")
    ids = ["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002", "00000000-0000-0000-0000-000000000003"]
    (root / "whitelist.json").write_text(json.dumps([
        {"uuid": "2f4bd5e2-e184-43af-8ab5-df7670dbc530", "name": "RenamedTestAccount"}, {"uuid": ids[0], "name": "ActiveAlice"}, {"uuid": ids[1], "name": "ActiveBob"}
    ]))
    export = root / "smoke-world/config/halfknife-active-playtime/playtime.json"
    export.parent.mkdir(parents=True, exist_ok=True)
    export.write_text(json.dumps({
        "schema": 1, "mode": "active", "afkTimeoutSeconds": 300,
        "startedAt": "2026-10-21T00:00:00Z", "updatedAt": "2026-10-21T00:00:00Z",
        "players": [
            {"uuid": "2f4bd5e2-e184-43af-8ab5-df7670dbc530", "name": "RenamedTestAccount", "activeMillis": 999999999, "afkMillis": 0},
            {"uuid": ids[0], "name": "ActiveAlice", "activeMillis": 21600000, "afkMillis": 999999999},
            {"uuid": ids[1], "name": "ActiveBob", "activeMillis": 7200000, "afkMillis": 999999999},
            {"uuid": ids[2], "name": "NotWhitelisted", "activeMillis": 999999999, "afkMillis": 0}
        ]
    }))
    stats_file = root / "smoke-world/players/stats" / (ids[0] + ".json")
    stats_file.parent.mkdir(parents=True, exist_ok=True)
    stats_file.write_text(json.dumps({"stats": {"minecraft:custom": {"minecraft:deaths": 5}}, "DataVersion": 4900}))
    with zipfile.ZipFile(root / "mods/tab-info.jar") as tab:
        function = tab.read("data/tab_info/function/display/playtime/main.mcfunction").decode()
        assert "= @s hk.active_ticks" in function
        assert "= @s playtime\n" not in function
    with (root / "smoke.log").open("w") as log:
        process = subprocess.Popen(["java", "-Xmx2G", "-Dhalfknife.playtime.integration-test=true", "-jar", "server.jar", "nogui"], cwd=root, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, text=True)
        try:
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                text = (root / "smoke.log").read_text()
                if 'Done (' in text:
                    # Verify packet-handler mixins too; class may be lazy-loaded on an empty server.
                    request = {"id": "11111111-1111-4111-8111-111111111111", "target": ids[0], "scope": "all",
                               "expiresAt": (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()}
                    request_file = export.with_name("reset-request.json")
                    result_file = export.with_name("reset-result.json")
                    request_file.write_text(json.dumps(request))
                    reset_deadline = time.monotonic() + 15
                    while not result_file.exists() and time.monotonic() < reset_deadline:
                        time.sleep(0.2)
                    result = json.loads(result_file.read_text())
                    assert result["success"] is True, result
                    assert not stats_file.exists(), "Offline vanilla stats were not reset"
                    backup = export.parent / "reset-backups" / request["id"]
                    assert (backup / "playtime.json").exists()
                    assert (backup / "players/stats" / stats_file.name).exists()
                    # A repeated upload must be acknowledged without reapplying it.
                    time.sleep(1)
                    request_file.write_text(json.dumps(request))
                    duplicate_deadline = time.monotonic() + 10
                    while request_file.exists() and time.monotonic() < duplicate_deadline:
                        time.sleep(0.2)
                    assert "Already applied" in json.loads(result_file.read_text())["message"]
                    process.stdin.write("stop\n")
                    process.stdin.flush()
                    process.wait(timeout=40)
                    data = json.loads((root / "smoke-world/config/halfknife-active-playtime/playtime.json").read_text())
                    assert data["mode"] == "active" and data["afkTimeoutSeconds"] == 300
                    assert len(data["players"]) == 4
                    by_id = {entry["uuid"]: entry for entry in data["players"]}
                    assert by_id[ids[0]]["activeMillis"] == by_id[ids[0]]["afkMillis"] == 0
                    assert by_id[ids[1]]["activeMillis"] == 7200000
                    assert request["id"] in data["processedResetIds"]
                    # Read the same store after a real second start; old time must stay gone.
                    with (root / "restart.log").open("w") as restart_log:
                        restart = subprocess.Popen(["java", "-Xmx2G", "-jar", "server.jar", "nogui"], cwd=root,
                                                   stdin=subprocess.PIPE, stdout=restart_log, stderr=subprocess.STDOUT, text=True)
                        try:
                            restart_deadline = time.monotonic() + 120
                            while time.monotonic() < restart_deadline and restart.poll() is None:
                                if 'Done (' in (root / "restart.log").read_text():
                                    break
                                time.sleep(1)
                            else:
                                raise RuntimeError("Restart failed: " + (root / "restart.log").read_text()[-8000:])
                            restart.stdin.write("stop\n"); restart.stdin.flush(); restart.wait(timeout=40)
                            assert restart.returncode == 0
                        finally:
                            if restart.poll() is None:
                                restart.kill(); restart.wait()
                    restarted = json.loads(export.read_text())
                    assert next(p for p in restarted["players"] if p["uuid"] == ids[0])["activeMillis"] == 0
                    assert "HALFKNIFE INTEGRATION PASSED" in (root / "smoke.log").read_text()
                    if process.returncode != 0:
                        raise RuntimeError("Smoke server failed on shutdown")
                    print("Integration passed: lobby, Tab, backups, offline stats reset, duplicate request, unchanged other players and reset persistence after restart.")
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
