# Statistiken per Knopfdruck zurücksetzen

Einmalig die getestete Active-Playtime-Mod 1.2.0 installieren und den Minecraft-Server neu starten. Der Build-Workflow installiert die Mod mit Sicherung der bisherigen JAR. Er startet den Server nicht selbst neu.

Danach bei laufendem Server in GitHub Actions **Spielerstatistiken zurücksetzen → Run workflow** öffnen. Minecraft-Name auswählen bzw. eingeben (`ALL` betrifft alle Whitelistspieler), Umfang auswählen und starten:

- `active`: Aktivzeit und AFK-Zähler der Aktivzeit-Mod.
- `all`: zusätzlich die gespeicherten Minecraft-Statistiken, z. B. Tode, abgebaute Blöcke und gesamte Vanilla-Spielzeit.

Der Workflow verlangt GitHub-Schreibrechte. Die Mod führt den Reset auf dem Serverthread aus und setzt dabei auch Sitzungszähler und die Aktivzeit-Anzeige zurück. Sie bestätigt den Reset erst nach Speicherung. Anschließend aktualisiert der Workflow beide Website-Exporte. GitHub Pages benötigt danach etwas Zeit zum Veröffentlichen. Online-Spieler sammeln ab dem Reset wieder neue Spielzeit.

Vor dem Reset entstehen dauerhafte Sicherungen unter `<Welt>/config/halfknife-active-playtime/reset-backups/<Reset-ID>/`. Inventar, Position, Fortschritte, RAS-Level und Belohnungs-/Ranghistorie anderer Mods werden nicht verändert.

Eine gespeicherte Reset-ID verhindert erneutes Zurücksetzen desselben Auftrags nach einem Neustart. Bei ausbleibender Bestätigung bricht der Workflow mit Fehler ab und versucht, seinen wartenden Auftrag zu entfernen. Bei FTP-Verbindungsabbruch den möglichen Auftrag `reset-request.json` prüfen, bevor der Server gestartet wird. Nie mehrere Resets parallel außerhalb des Workflows senden.

Die Mod lädt ihre Datei beim Serverstart und schreibt ihren Stand regelmäßig zurück. Änderungen an `playtime.json` während der Laufzeit können deshalb wieder verschwinden. Der Reset-Knopf vermeidet diese zweite Datenquelle.

## Konsolen-Reset ab 1.3.0

Nur in der echten Serverkonsole, ohne `/`:

- `halfknife reset all` prüft die installierten Mod-Versionen und zeigt eine Vorschau.
- `halfknife reset all confirm` sichert und setzt die Statistikdaten zurück.

Der Server muss leer sein; ein laufendes Quiz oder ein ausstehender GitHub-Reset blockiert den Vorgang. Es werden alle gespeicherten Spieler berücksichtigt, auch nicht mehr gewhitelistete Spieler und alte Scoreboard-Namen. Der Befehl ist für Spieler, Commandblöcke und RCON nicht freigegeben.

Enthalten: Vanilla- und in Vanilla registrierte Mod-Statistiken, Fortschritte (RAS-Namensräume ausgenommen), aktive/AFK-Zeit, Playtime Rewards 1.7.3 inklusive Belohnungsansprüchen, Quiz 1.0.0 einschließlich aller Saisonstatistiken sowie persönliche Nether-/End-Projekt-Beiträge. Der Gesamtfortschritt und Freischaltzustand der Projekte bleiben bestehen. Tab-Anzeigen und statistikbasierte Scoreboard-Werte werden auf null gesetzt; Steuerwerte wie `#ticks_per_hour` bleiben erhalten. Leaderboards aktualisieren sich innerhalb ihres normalen 30-Sekunden-Zyklus; die Website über die bestehenden Sync-Workflows.

RAS-Daten, RAS-Statistiken/-Fortschritte, `ras_level`, der Levelcache der Leaderboards, Inventare, Enderchests, Positionen, Welt, Hall-of-Fame-Statuen, Ledger-Protokolle, Shops und Kistenzugriffe werden nicht gelöscht. Der Reset bearbeitet keine Player-NBT-Dateien. Playtime-Ränge sind sofort auf null; zugehörige LuckPerms-Gruppen werden durch Playtime Rewards beim nächsten Login abgeglichen. Bereits ausgegebene Belohnungsitems werden nicht eingezogen; nach dem Reset sind Belohnungen neu erspielbar.

Die Integration ist ausdrücklich auf die geprüften Versionen begrenzt. Andere Versionen der angebundenen Mods führen vor jeder Änderung zum Abbruch. Unbekannte Mods mit eigenen Datenbanken sind nicht automatisch enthalten.

Sicherung: `<Welt>/config/halfknife-active-playtime/reset-backups/console-<UUID>/`. `manifest.json` ordnet Originalpfade den Sicherungsdateien zu; `scoreboard-values.json` enthält alte Scorewerte. Vor der ersten Änderung werden alle betroffenen Dateien gesichert. Bei einem Laufzeitfehler versucht die Mod, Dateien und Arbeitsspeicherwerte wiederherzustellen; Details stehen im Serverlog und in `status.txt`. Eine unterbrochene JVM während des Resets erfordert Prüfung der Sicherung vor erneutem Start. Für eine manuelle Wiederherstellung den Server stoppen und die Dateizuordnung im Manifest verwenden; Scorewerte separat anhand der Sicherung wiederherstellen.
