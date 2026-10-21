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
                import struct
                for entry in jar.namelist():
                    if not entry.startswith("com/sovern/") or not entry.endswith(".class"):
                        continue
                    raw = jar.read(entry)
                    count = struct.unpack_from(">H", raw, 8)[0]
                    position = 10
                    index = 1
                    strings = []
                    sizes = {3: 4, 4: 4, 5: 8, 6: 8, 7: 2, 8: 2, 9: 4, 10: 4, 11: 4, 12: 4, 15: 3, 16: 2, 17: 4, 18: 4, 19: 2, 20: 2}
                    while index < count:
                        tag = raw[position]
                        position += 1
                        if tag == 1:
                            length = struct.unpack_from(">H", raw, position)[0]
                            position += 2
                            strings.append(raw[position:position+length].decode("utf-8", errors="replace"))
                            position += length
                        else:
                            position += sizes[tag]
                            if tag in (5, 6):
                                index += 1
                        index += 1
                    print("CLASS", entry, json.dumps([s for s in strings if not s.startswith("(")], ensure_ascii=False))
    for directory in ("config", "."):
        print("Relevant paths in", directory)
        for path in ftp.nlst(directory):
            print(path)
finally:
    ftp.close()
