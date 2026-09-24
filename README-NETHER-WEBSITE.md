# Nether-Projekt auf der Website

Die Events-Seite zeigt die gespeicherten Einzahlungen, Fortschrittsbalken pro
Ressource, die Anzahl vollständig erfüllter Ressourcenziele, den Projektstatus
und alle Spieler mit positiven Spendenpunkten. Die Punkte werden unverändert
aus `playerPoints` übernommen. Gleiche Punktzahlen teilen sich einen Rang.

## Veröffentlichen

1. Die Dateien dieses Website-Ordners im Stammverzeichnis des bestehenden
   Repositorys `EBGjoshiGER/HalfKnifeSMP2026` auf Branch `main` übernehmen.
   Insbesondere die versteckte `.github`-Struktur und den neuen Ordner
   `scripts` mit übernehmen.
2. Die Änderungen wie bisher committen/pushen und den Website-Build abwarten.
3. Auf GitHub unter Actions den Workflow **Minecraft Serverdaten synchronisieren**
   einmal mit **Run workflow** starten. Der neue Schritt heißt
   **Nether-Projekt synchronisieren**.
4. Die Events-Seite mit Strg+F5 laden. Nach einer Testeinzahlung erneut den
   Workflow starten und die Ressourcen sowie `/netherproject top` vergleichen.

Keine neue Minecraft-Mod und keine zusätzlichen Zugangsdaten erforderlich.
Der Workflow verwendet die vier bereits bestehenden SERVERMINER_FTP-Secrets.
Die bisherigen einzelnen Whitelist-/Online-Spieler-Workflows sind in dieser
Version deaktiviert: Nur `sync-server-data.yml` soll regelmäßig Daten schreiben.

## Datenquelle

Der FTP-Download erwartet, relativ zum bisherigen FTP-Startverzeichnis:

```
config/netherproject/config.json
config/netherproject/progress.json
```

Falls der Ordner auf dem Server anders liegt, `ftp.cwd(...)` in
`scripts/download_nether_project.py` anpassen.

Der Export erzeugt nur `data/nether-project.json`. Konfiguration, Befehle,
FTP-Zugangsdaten und UUID-Zuordnungen werden nicht in diese Datei kopiert.
Spielernamen und Spendenpunkte sind auf der Website öffentlich sichtbar.

Die veröffentlichte Events-Seite liest diese Datei direkt aus dem öffentlichen
Repository über die `data-source`-URL im Nether-Artikel. So ist kein zusätzlicher
GitHub-Pages-Build für jede automatische Datenaktualisierung nötig. Wird das
Repository umbenannt oder der Branch geändert, diese URL anpassen.

Beim lokalen Test über localhost liest die Seite stattdessen die lokale Datei
`data/nether-project.json`. HTML-Dateien bitte über einen lokalen Webserver
öffnen; ein Doppelklick mit `file://` erlaubt den JSON-Abruf nicht zuverlässig.

## Aktualität und Fehler

Der gemeinsame Workflow ist im Fünf-Minuten-Raster eingeplant. GitHub kann
geplante Läufe verzögern. Die offene Seite prüft jede Minute auf neue Daten.
Die Mod muss Einzahlungen zuvor in ihre `progress.json` geschrieben haben.

Ab 30 Minuten ohne Synchronisierung kennzeichnet die Seite den Stand als alt.
Bei Ladefehlern bleiben bereits angezeigte Werte erhalten. Ungültige Serverdaten
überschreiben keine vorhandene gültige JSON-Datei. Die Synchronisierung der
anderen Serverdaten kann trotzdem weiterlaufen; am Ende wird ein Fehler für
das Nether-Projekt sichtbar gemeldet.

Die mitgelieferte erste JSON-Datei stammt aus deiner `netherproject.zip` vom
24.09.2026, 05:45 Uhr: nicht gestartet, sechs Ressourcen bei null, keine Spender.
Sie wird beim ersten erfolgreichen Workflow-Lauf durch den Serverstand ersetzt.

## Prüfung

Lokal geprüft: die echte ZIP, genaue Punkteübernahme, Ranggleichheit,
pausierte/abgeschlossene Projekte, Übererfüllung, fehlerhafte Daten,
Erhalt des letzten gültigen Stands sowie die Browserdarstellung bei
1360, 390 und 320 Pixeln Breite. Test-Spieler wurden nicht ausgeliefert.

Der tatsächliche FTP-Abruf über deine GitHub-Secrets und die Veröffentlichung
können erst nach Übernahme ins Repository mit einem Workflow-Lauf geprüft werden.
