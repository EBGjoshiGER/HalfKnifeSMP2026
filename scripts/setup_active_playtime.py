"""Read-only inspection of the playtime consumers installed on the server."""
import ftplib, io, json, os, re, subprocess, tempfile, zipfile
from pathlib import Path, PurePosixPath

ftp = ftplib.FTP(timeout=30)
try:
    ftp.connect(os.environ["FTP_HOST"], int(os.environ.get("FTP_PORT") or "21"))
    ftp.login(os.environ["FTP_USER"], os.environ["FTP_PASSWORD"])
    for path in sorted(ftp.nlst("mods")):
        name = PurePosixPath(path).name
        if not any(term in name.lower() for term in ("tab-info", "halfknife-leaderboards", "halfknife-hall-of-fame", "playtime-rewards")) or not name.endswith(".jar"):
            continue
        buffer = io.BytesIO()
        ftp.retrbinary("RETR mods/" + name, buffer.write)
        with tempfile.TemporaryDirectory() as work:
            jar_path = Path(work) / name
            jar_path.write_bytes(buffer.getvalue())
            with zipfile.ZipFile(buffer) as jar:
                print("MOD METADATA", name, jar.read("fabric.mod.json").decode())
                classes = [entry[:-6].replace("/", ".") for entry in jar.namelist() if entry.endswith(".class") and not entry.startswith(("net/", "org/", "com/google/", "META-INF/"))]
                print("CLASSES", name, json.dumps(classes))
                for classname in classes:
                    if len(classes) > 100 and not any(t in classname.lower() for t in ("playtime", "leaderboard", "halloffame", "tabinfo")):
                        continue
                    output = subprocess.check_output(["javap", "-p", "-c", "-classpath", str(jar_path), classname], text=True, stderr=subprocess.STDOUT)
                    print("SIGNATURES", classname)
                    print("\n".join(line for line in output.splitlines() if re.match(r"  (public|protected|private|static)", line)))
                    for block in re.split(r"(?m)(?=^  (?:public|protected|private|static).+)", output):
                        if any(term.lower() in block.lower() for term in ("PLAY_TIME", "play_time", "playtime", "getstat", "seconds", "stats/", "config/")):
                            print("BYTECODE", classname, block)
finally:
    ftp.close()
