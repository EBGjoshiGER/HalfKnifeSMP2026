# Nether Project 2.4.0 – manuelle Freischaltung

Serverseitig für Fabric 26.2 / Java 25. Übernimmt `config/netherproject/config.json` und `progress.json` unverändert. Kein Reset nötig.

100 % schließen nur das Sammelziel ab. Das Portal bleibt gesperrt; Fortschritt, Beiträge und Punkte bleiben gespeichert. Auch Neustart und Reload starten keine Freischaltung.

- `/netherproject activate`: OP startet nach erreichtem Ziel den konfigurierten Countdown (bisher standardmäßig 60 Sekunden).
- `/netherproject unlocknether`: Alias für `activate`, mit denselben Prüfungen.
- `/netherproject forcecomplete`: füllt nur das Sammelziel; öffnet nicht den Nether.
- `/netherproject locknether`: sperrt den Nether und bricht einen laufenden Countdown ab. Erneute Freischaltung muss manuell erfolgen.
- `/netherproject reload`: lädt Daten neu und bricht einen laufenden Countdown ab.
- `/netherproject reset`: setzt wie bisher das gesamte Projekt zurück; für das Update nicht verwenden.
- Anzeige und Einzahlungen unverändert über `/netherproject`, `/netherproject status`, `/netherproject top`.

In der Serverkonsole Befehle ohne `/` eingeben. `completionCommandsExecuted` speichert die erfolgte Freischaltung; nach Neustart keine doppelte Ausführung. Abgebrochene Countdowns müssen erneut manuell gestartet werden.

Der Workflow baut die JAR, testet auf einem isolierten Fabric-Server mit der installierten Fabric API und DimensionDaddy und ersetzt danach ausschließlich die Mod-JAR mit Backup. Der Produktionsserver wird nicht neu gestartet; die Änderung wird mit dessen nächstem Neustart aktiv. Konfiguration und laufender Fortschritt werden nicht bearbeitet.
