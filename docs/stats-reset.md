# Statistiken per Knopfdruck zurücksetzen

Einmalig die getestete Active-Playtime-Mod 1.2.0 installieren und den Minecraft-Server neu starten. Der Build-Workflow installiert die Mod mit Sicherung der bisherigen JAR. Er startet den Server nicht selbst neu.

Danach bei laufendem Server in GitHub Actions **Spielerstatistiken zurücksetzen → Run workflow** öffnen. Minecraft-Name auswählen bzw. eingeben (`ALL` betrifft alle Whitelistspieler), Umfang auswählen und starten:

- `active`: Aktivzeit und AFK-Zähler der Aktivzeit-Mod.
- `all`: zusätzlich die gespeicherten Minecraft-Statistiken, z. B. Tode, abgebaute Blöcke und gesamte Vanilla-Spielzeit.

Der Workflow verlangt GitHub-Schreibrechte. Die Mod führt den Reset auf dem Serverthread aus und setzt dabei auch Sitzungszähler und die Aktivzeit-Anzeige zurück. Sie bestätigt den Reset erst nach Speicherung. Anschließend aktualisiert der Workflow beide Website-Exporte. GitHub Pages benötigt danach etwas Zeit zum Veröffentlichen. Online-Spieler sammeln ab dem Reset wieder neue Spielzeit.

Vor dem Reset entstehen dauerhafte Sicherungen unter `<Welt>/config/halfknife-active-playtime/reset-backups/<Reset-ID>/`. Inventar, Position, Fortschritte, RAS-Level und Belohnungs-/Ranghistorie anderer Mods werden nicht verändert.

Eine gespeicherte Reset-ID verhindert erneutes Zurücksetzen desselben Auftrags nach einem Neustart. Bei ausbleibender Bestätigung bricht der Workflow mit Fehler ab und versucht, seinen wartenden Auftrag zu entfernen. Bei FTP-Verbindungsabbruch den möglichen Auftrag `reset-request.json` prüfen, bevor der Server gestartet wird. Nie mehrere Resets parallel außerhalb des Workflows senden.

Die Mod lädt ihre Datei beim Serverstart und schreibt ihren Stand regelmäßig zurück. Änderungen an `playtime.json` während der Laufzeit können deshalb wieder verschwinden. Der Reset-Knopf vermeidet diese zweite Datenquelle.
