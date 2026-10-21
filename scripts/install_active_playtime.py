"""Install only the tested HalfKnife JAR; leave activation to a normal restart."""
import ftplib
import hashlib
import io
import os
from pathlib import Path


def main():
    jar = Path("mods/halfknife-active-playtime/build/libs/halfknife-active-playtime-1.0.0.jar").read_bytes()
    filename = "mods/halfknife-active-playtime-1.0.0.jar"
    staging = filename + ".upload"
    ftp = ftplib.FTP(timeout=30)
    try:
        ftp.connect(os.environ["FTP_HOST"], int(os.environ.get("FTP_PORT") or "21"))
        ftp.login(os.environ["FTP_USER"], os.environ["FTP_PASSWORD"])
        existing = {path.rsplit("/", 1)[-1] for path in ftp.nlst("mods")}
        duplicates = [name for name in existing if name.startswith("halfknife-active-playtime-") and name.endswith(".jar") and name != filename.rsplit("/", 1)[-1]]
        if duplicates:
            raise RuntimeError("Another active-playtime version is present; refusing duplicate installation")
        ftp.storbinary("STOR " + staging, io.BytesIO(jar))
        check = io.BytesIO()
        ftp.retrbinary("RETR " + staging, check.write)
        if hashlib.sha256(check.getvalue()).digest() != hashlib.sha256(jar).digest():
            raise RuntimeError("Uploaded JAR checksum mismatch")
        if filename.rsplit("/", 1)[-1] in existing:
            old = io.BytesIO()
            ftp.retrbinary("RETR " + filename, old.write)
            if old.getvalue() == jar:
                ftp.delete(staging)
                print("Verified JAR already installed. Activation requires a server restart.")
                return
            ftp.storbinary("STOR " + filename + ".bak", io.BytesIO(old.getvalue()))
        ftp.rename(staging, filename)
        print("Tested JAR installed and SHA-256 verified. Restart the server to activate it.")
    finally:
        ftp.close()


if __name__ == "__main__":
    main()
