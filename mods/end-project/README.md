# End Project 1.1.0

Serverseitig für Fabric 26.2, Java 25. Die freigegebenen Ziele stehen in `approved-requirements.json`.

Beim ersten Modstart werden bestehende Konfigurationen mit `configVersion < 2` einmalig auf die zwölf freigegebenen Ziele umgestellt. Befehle, Verzögerung, Erinnerungen, vorhandene Punkte und Beiträge bleiben erhalten. Der alte Quarzschlüssel `minecraft:nether_quartz` wird auf die tatsächliche Item-ID `minecraft:quartz` übertragen. Spätere Änderungen an einer Konfiguration mit Version 2 werden nicht erneut überschrieben. Für neue Materialien wird ein Beitragspunkt je Item vergeben; bestehende Gewichtungen werden übernommen.

- `/endproject start`: OP startet das Sammeln; öffnet das End nicht.
- `/endproject`: Einzahlungsinventar. `/endproject status` und `/endproject top`: Fortschritt und Rangliste.
- 100 %: Sammelziel abgeschlossen; Chat informiert alle, End bleibt gesperrt.
- `/endproject activate`: OP startet nach erreichtem Ziel den konfigurierten Öffnungs-Countdown.
- `/endproject unlockend`: Alias für `activate`, mit denselben Prüfungen.
- `/endproject forcecomplete`: füllt nur die Ziele; öffnet das End nicht.
- `/endproject lockend`: sperrt das End und beendet einen Countdown.
- `/endproject reload`: lädt Konfiguration/Fortschritt, beendet einen Countdown.
- `/endproject reset`: löscht wie bisher den Projektfortschritt; für dieses Update nicht verwenden.

In der Serverkonsole ohne `/`. Weder Zielerreichung, Serverstart noch Reload lösen automatisch eine Freischaltung aus. Unterbrochene Countdowns müssen manuell neu gestartet werden. Eine bereits erfolgte Öffnung bleibt gespeichert.

Die Installation sichert die bisherige JAR sowie Konfiguration und Fortschritt. Sie ersetzt nur die Mod-JAR; die einmalige Konfigurationsmigration erfolgt beim nächsten Produktionsstart. Kein automatischer Neustart, kein automatischer Projektstart.
