"""Install the verified 64px HalfKnife icon with checksum verification and backup."""
import ftplib, hashlib, io, os, struct
from datetime import datetime, timezone
from pathlib import Path

EXPECTED = "be037b9ead325af1950c41380f7a8317e74747b8244e9a46e15ab760da4efed2"
REPLACED = "af31e5a1a30e68d3474e181051b1b3f5a987ce5568e7c4b7ed2495afcc8189fd"

def digest(data): return hashlib.sha256(data).hexdigest()
def read(ftp,path):
    b=io.BytesIO(); ftp.retrbinary("RETR "+path,b.write); return b.getvalue()

def main():
    image=Path("assets/server-icon.png").read_bytes()
    if digest(image)!=EXPECTED or image[:8]!=b"\x89PNG\r\n\x1a\n" or struct.unpack(">II",image[16:24])!=(64,64):
        raise ValueError("Local icon failed verification")
    ftp=ftplib.FTP(timeout=30)
    try:
        ftp.connect(os.environ["FTP_HOST"],int(os.environ.get("FTP_PORT") or "21"))
        ftp.login(os.environ["FTP_USER"],os.environ["FTP_PASSWORD"])
        old=read(ftp,"server-icon.png")
        if digest(old)==EXPECTED:
            print("Correct 64x64 icon already installed.");return
        if digest(old)!=REPLACED:
            raise RuntimeError("Server icon changed since diagnosis; refusing to overwrite it")
        stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        temp="server-icon.png.upload-"+stamp
        backup="server-icon.png.before-icon-fix-"+stamp+".bak"
        ftp.storbinary("STOR "+temp,io.BytesIO(image))
        if read(ftp,temp)!=image:
            ftp.delete(temp);raise RuntimeError("Staged icon failed checksum verification")
        # Verify the original again immediately before activation.
        if read(ftp,"server-icon.png")!=old:
            ftp.delete(temp);raise RuntimeError("Server icon changed during upload")
        ftp.rename("server-icon.png",backup)
        activated=False
        try:
            ftp.rename(temp,"server-icon.png");activated=True
            if read(ftp,"server-icon.png")!=image:raise RuntimeError("Installed icon verification failed")
        except Exception:
            if activated:ftp.delete("server-icon.png")
            ftp.rename(backup,"server-icon.png")
            raise
        print("Installed server-icon.png: PNG, 64x64, 9711 bytes; checksum verified.")
        print("Previous 1254x1254 image backed up as "+backup)
        print("A Minecraft server restart is needed to load the new root icon.")
    finally:ftp.close()

if __name__=="__main__":main()
