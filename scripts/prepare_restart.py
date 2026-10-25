"""Prepare rank-display, lunar-events and spark changes, without restarting production."""
import copy
from datetime import datetime, timezone
import ftplib
import hashlib
import io
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import zipfile


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "HalfKnifeSMP/maintenance"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def read(ftp, path):
    result = io.BytesIO()
    ftp.retrbinary("RETR " + path, result.write)
    return result.getvalue()


def hide_rank_prefixes(original):
    result = copy.deepcopy(original)
    if not result.get("luckPermsEnabled") or not result.get("createMissingLuckPermsGroups"):
        raise ValueError("Expected managed LuckPerms groups")
    ranks = result.get("ranks", [])
    if not ranks or any("luckPermsPrefix" not in rank for rank in ranks):
        raise ValueError("Unsupported rewards config")
    for rank in ranks:
        rank["luckPermsPrefix"] = ""
    # Names, times, rewards, permissions and all unrelated options must survive.
    expected = copy.deepcopy(original)
    for rank in expected["ranks"]:
        rank["luckPermsPrefix"] = ""
    assert result == expected
    return result


def metadata(content):
    with zipfile.ZipFile(io.BytesIO(content)) as jar:
        return json.loads(jar.read("fabric.mod.json"))


def smoke(ftp, installed, config, spark_name, spark):
    root = Path("temp/restart-smoke")
    (root / "mods").mkdir(parents=True, exist_ok=True)
    # Test the actual display chain and new profiler; no production world or player data.
    prefixes = ("fabric-api-", "LuckPerms-Fabric-", "playtime-rewards-", "customname-fabric-", "styled-chat-", "placeholder-api-", "cloth-config-")
    for prefix in prefixes:
        names = [name for name in installed if name.startswith(prefix)]
        if len(names) != 1:
            raise ValueError("Cannot uniquely resolve smoke dependency " + prefix)
        (root / "mods" / names[0]).write_bytes(read(ftp, "mods/" + names[0]))
    (root / "mods" / spark_name).write_bytes(spark)
    config_path = root / "smoke-world/config/playtime-rewards/config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    for name in ("eclipsescustomname.json", "styled-chat.json"):
        dest = root / "config" / name
        dest.parent.mkdir(exist_ok=True)
        dest.write_bytes(read(ftp, "config/" + name))
    installers = json.loads(download("https://meta.fabricmc.net/v2/versions/installer"))
    installer = next(item["version"] for item in installers if item.get("stable"))
    (root / "server.jar").write_bytes(download(f"https://meta.fabricmc.net/v2/versions/loader/26.2/0.19.5/{installer}/server/jar"))
    (root / "eula.txt").write_text("eula=true\n")
    (root / "server.properties").write_text("server-ip=127.0.0.1\nserver-port=0\nonline-mode=false\nview-distance=2\nsimulation-distance=2\nlevel-name=smoke-world\nlevel-type=minecraft:flat\nspawn-protection=0\n")
    output = []
    lines = queue.Queue()
    process = subprocess.Popen(["java", "-Xms512M", "-Xmx2G", "-jar", "server.jar", "nogui"], cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    def consume():
        for line in process.stdout:
            output.append(line)
            lines.put(line)
    thread = threading.Thread(target=consume, daemon=True)
    thread.start()
    ready = False
    deadline = time.monotonic() + 240
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Smoke server exited during startup")
            try:
                line = lines.get(timeout=1)
            except queue.Empty:
                continue
            if "Done (" in line:
                ready = True
                break
        if not ready:
            raise RuntimeError("Smoke server did not become ready")
        process.stdin.write("spark tps\nlp group anfaenger meta info\n")
        process.stdin.flush()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if any("TPS from last" in line or "TPS from" in line for line in output):
                break
            time.sleep(0.25)
        if not any("TPS from" in line for line in output):
            raise RuntimeError("spark command did not return TPS")
        parsed = json.loads(config_path.read_text())
        if not parsed["ranks"] or any(rank["luckPermsPrefix"] != "" for rank in parsed["ranks"]):
            raise RuntimeError("Rewards parser did not retain empty prefixes")
        # The mod rewrites its parsed config: verify the entire rank progression is unchanged.
        assert parsed["ranks"] == config["ranks"], "Rank progression changed on load"
        print("SMOKE PASS: Fabric 26.2 started with actual display mods and spark; all rank prefixes empty; rank rewards unchanged.", flush=True)
    finally:
        if process.poll() is None:
            process.stdin.write("stop\n")
            process.stdin.flush()
            try:
                process.wait(timeout=45)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        thread.join(timeout=5)
        (root / "smoke-output.log").write_text("".join(output))
        for line in output:
            if any(word in line for word in ("ERROR", "Exception", "TPS from", "Prefixes", "prefixes", "anfaenger")):
                print(line.rstrip(), flush=True)


def main():
    ftp = ftplib.FTP(timeout=45)
    committed = []
    uploads = []
    try:
        ftp.connect(os.environ["FTP_HOST"], int(os.environ.get("FTP_PORT") or "21"))
        ftp.login(os.environ["FTP_USER"], os.environ["FTP_PASSWORD"])
        installed = sorted(Path(name).name for name in ftp.nlst("mods") if name.endswith(".jar"))
        props = read(ftp, "server.properties").decode("utf-8-sig")
        world = next(line.split("=", 1)[1].strip() for line in props.splitlines() if line.startswith("level-name="))
        if world != "HalfKnifeSMP2026":
            raise ValueError("Unexpected production world")
        config_path = world + "/config/playtime-rewards/config.json"
        original = read(ftp, config_path)
        changed = hide_rank_prefixes(json.loads(original))
        new_config = (json.dumps(changed, ensure_ascii=False, indent=2) + "\n").encode()
        lunar = [name for name in installed if name.startswith("Enhanced-Celestials-2-Default-Lunar-Events-")]
        if len(lunar) != 1:
            raise ValueError("Expected exactly one Default Lunar Events mod")
        lunar_path = "mods/" + lunar[0]
        lunar_content = read(ftp, lunar_path)
        if metadata(lunar_content)["id"] != "enhancedcelestials2defaultlunarevents":
            raise ValueError("Wrong lunar events module")
        query = urllib.parse.urlencode({"loaders": '["fabric"]', "game_versions": '["26.2"]'})
        versions = json.loads(download("https://api.modrinth.com/v2/project/spark/version?" + query))
        version = next(item for item in versions if item["version_type"] == "release")
        asset = next(item for item in version["files"] if item["primary"])
        if not asset["url"].startswith("https://cdn.modrinth.com/") or not asset["filename"].endswith(".jar") or "/" in asset["filename"]:
            raise ValueError("Unexpected spark download")
        spark = download(asset["url"])
        if hashlib.sha512(spark).hexdigest() != asset["hashes"]["sha512"] or metadata(spark)["id"] != "spark":
            raise ValueError("spark integrity validation failed")
        spark_name = asset["filename"]
        if any(name.lower().startswith("spark") for name in installed):
            raise ValueError("spark already installed; refusing duplicate")
        print("Selected spark:", version["version_number"], spark_name, "for Fabric 26.2; SHA-512 verified", flush=True)
        smoke(ftp, installed, changed, spark_name, spark)
        # Revalidate after the isolated boot so concurrent maintenance is never overwritten.
        if read(ftp, config_path) != original or read(ftp, lunar_path) != lunar_content:
            raise RuntimeError("Production inputs changed during smoke test")
        backup = "maintenance-backups"
        try:
            ftp.mkd(backup)
        except ftplib.error_perm:
            ftp.cwd(backup)
            ftp.cwd("..")
        backup += "/restart-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        ftp.mkd(backup)
        for name, content in (("playtime-rewards-config.json", original), (lunar[0], lunar_content)):
            ftp.storbinary("STOR " + backup + "/" + name, io.BytesIO(content))
            if read(ftp, backup + "/" + name) != content:
                raise RuntimeError("Backup verification failed")
        targets = [(config_path, new_config), ("mods/" + spark_name, spark)]
        for path, content in targets:
            temporary = path + ".restart-upload"
            uploads.append(temporary)
            ftp.storbinary("STOR " + temporary, io.BytesIO(content))
            if read(ftp, temporary) != content:
                raise RuntimeError("Upload verification failed")
        # Replace only files loaded at next server start; never send console commands to production.
        original_disabled = config_path + ".before-restart.bak"
        ftp.rename(config_path, original_disabled)
        committed.append(("config", config_path, original_disabled))
        ftp.rename(config_path + ".restart-upload", config_path)
        spark_path = "mods/" + spark_name
        ftp.rename(spark_path + ".restart-upload", spark_path)
        committed.append(("spark", spark_path, None))
        disabled_lunar = backup + "/disabled-" + lunar[0]
        ftp.rename(lunar_path, disabled_lunar)
        committed.append(("lunar", lunar_path, disabled_lunar))
        assert read(ftp, config_path) == new_config
        assert read(ftp, spark_path) == spark
        final_mods = [Path(name).name for name in ftp.nlst("mods") if name.endswith(".jar")]
        assert lunar[0] not in final_mods and spark_name in final_mods
        assert sorted(set(installed) - {lunar[0]} | {spark_name}) == sorted(final_mods)
        print("DEPLOY PASS: rank-prefix config replaced, Default Lunar Events disabled, spark installed; byte-for-byte checks passed.")
        print("BACKUP:", backup)
        print("Production was not stopped, restarted or sent messages. Player data, time counters, rewards and personal prefixes were not edited.")
        report = {"status": "prepared", "sparkVersion": version["version_number"], "sparkFile": spark_name, "removedModule": lunar[0], "rankPrefixesHidden": len(changed["ranks"]), "backupDirectory": backup, "restartPerformed": False}
        Path("temp/restart-result.json").write_text(json.dumps(report, indent=2) + "\n")
    except Exception:
        for kind, path, source in reversed(committed):
            try:
                if kind in {"config", "spark"}:
                    try:
                        ftp.delete(path)
                    except ftplib.error_perm:
                        pass
                if source:
                    ftp.rename(source, path)
            except Exception as error:
                print("ROLLBACK NEEDS ATTENTION:", kind, type(error).__name__)
        raise
    finally:
        for path in uploads:
            try:
                ftp.delete(path)
            except ftplib.error_perm:
                pass
        ftp.close()


if __name__ == "__main__":
    main()
