import ftplib, io, json, os, zipfile
ftp=ftplib.FTP(timeout=30)
try:
 ftp.connect(os.environ["FTP_HOST"],int(os.environ.get("FTP_PORT") or "21"))
 ftp.login(os.environ["FTP_USER"],os.environ["FTP_PASSWORD"])
 b=io.BytesIO(); ftp.retrbinary("RETR mods/tab-info-0.3.0+mod.jar",b.write)
 with zipfile.ZipFile(b) as jar:
  for path in jar.namelist():
   if path.endswith((".mcfunction",".json")) and ("playtime" in path.lower() or path.endswith(("load.mcfunction","install.mcfunction","tick.mcfunction"))):
    print("TAB RESOURCE",path);print(jar.read(path).decode())
  for path in jar.namelist():
   if path.endswith(".mcfunction"):
    text=jar.read(path).decode()
    if "play_time" in text or "playtime" in text.lower():
     print("TAB PLAYTIME",path);print(text)
finally:ftp.close()
