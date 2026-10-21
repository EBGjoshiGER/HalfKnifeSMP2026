import ftplib, io, json, os, zipfile
from pathlib import PurePosixPath

ftp = ftplib.FTP(timeout=30)
try:
    ftp.connect(os.environ["FTP_HOST"], int(os.environ.get("FTP_PORT") or "21"))
    ftp.login(os.environ["FTP_USER"], os.environ["FTP_PASSWORD"])
    mods = ftp.nlst("mods")
    print("Installed mods:")
    for path in sorted(mods):
        name = PurePosixPath(path).name
        print(name)
        if any(term in name.lower() for term in ("playtime", "play-time", "afk")) and name.endswith(".jar"):
            buffer = io.BytesIO()
            ftp.retrbinary("RETR mods/" + name, buffer.write)
            with zipfile.ZipFile(buffer) as jar:
                metadata = json.loads(jar.read("fabric.mod.json"))
                print("PLAYTIME METADATA:", json.dumps(metadata, ensure_ascii=False))
    for directory in ("config", "."):
        print("Relevant paths in", directory)
        for path in ftp.nlst(directory):
            if any(term in path.lower() for term in ("playtime", "play-time", "afk")):
                print(path)
finally:
    ftp.close()
