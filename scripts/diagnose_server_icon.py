"""Read-only server icon and MiniMOTD diagnostics; never print credentials."""
import base64, ftplib, hashlib, io, json, os, re, struct, socket

def get(ftp,path):
    b=io.BytesIO()
    try: ftp.retrbinary("RETR "+path,b.write)
    except ftplib.error_perm as e:
        if str(e).startswith("550"): return None
        raise
    return b.getvalue()

def png(path,data):
    if data is None: print("MISSING",path); return
    info={"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data)>=33:
        info.update(width=struct.unpack(">I",data[16:20])[0],height=struct.unpack(">I",data[20:24])[0],bitDepth=data[24],colorType=data[25])
    else: info["format"]="not PNG"
    print("IMAGE",path,json.dumps(info))

ftp=ftplib.FTP(timeout=30)
try:
    ftp.connect(os.environ["FTP_HOST"],int(os.environ.get("FTP_PORT") or "21"))
    ftp.login(os.environ["FTP_USER"],os.environ["FTP_PASSWORD"])
    root=ftp.pwd()
    names=ftp.nlst()
    print("ROOT ICON FILENAMES",json.dumps([n for n in names if "icon" in n.lower()]))
    png("server-icon.png",get(ftp,"server-icon.png"))
    config_roots=[]
    try:
        ftp.cwd("config")
        config_roots=[n.rsplit("/",1)[-1] for n in ftp.nlst() if "minimotd" in n.lower()]
    finally: ftp.cwd(root)
    print("MINIMOTD CONFIG DIRS",json.dumps(config_roots))
    for folder in config_roots:
        for filename in ["main.conf","extra-configs/main.conf"]:
            path="config/"+folder+"/"+filename
            raw=get(ftp,path)
            if raw is not None:
                lines=raw.decode("utf-8-sig",errors="replace").splitlines()
                print("CONFIG",path)
                for line in lines:
                    if re.match(r"\s*(?:icon-enabled|motd-enabled|icon)\s*=",line): print(line.strip())
        for suffix in ["icons","extra-configs"]:
            path="config/"+folder+"/"+suffix
            try:
                ftp.cwd(path); entries=ftp.nlst(); print("DIRECTORY",path,json.dumps(entries))
                if suffix=="icons":
                    for name in entries[:12]:
                        if name.lower().endswith(".png"): png(path+"/"+name,get(ftp,name))
            except ftplib.error_perm: print("MISSING DIR",path)
            finally: ftp.cwd(root)
    log=get(ftp,"logs/latest.log")
    if log:
        lines=log.decode("utf-8",errors="replace").splitlines()
        print("STARTUP",next((line for line in lines if "Starting minecraft server version" in line),"unknown"))
        matches=[i for i,line in enumerate(lines) if re.search(r"icon|favicon|minimotd",line,re.I)]
        for i in matches[-25:]:
            for line in lines[max(0,i-1):i+3]: print("ICON LOG",line)
finally: ftp.close()
