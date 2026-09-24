"""Download the two Nether Project files using the existing FTP secrets."""

import ftplib
import os
from pathlib import Path


def main():
    folder = Path("temp/netherproject")
    folder.mkdir(parents=True, exist_ok=True)
    # Matches the established ServerMiner connection used by the existing sync.
    with ftplib.FTP() as ftp:
        ftp.connect(os.environ["FTP_HOST"], int(os.environ["FTP_PORT"]), timeout=30)
        ftp.login(os.environ["FTP_USER"], os.environ["FTP_PASSWORD"])
        ftp.cwd("config/netherproject")
        for name in ("config.json", "progress.json"):
            destination = folder / name
            with destination.open("wb") as output:
                ftp.retrbinary(f"RETR {name}", output.write)
    print("Nether-Projektdaten heruntergeladen.")


if __name__ == "__main__":
    main()
