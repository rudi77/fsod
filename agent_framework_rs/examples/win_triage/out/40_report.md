# Triage-Bericht — SRV-WWS-01, 2026-07-11T00:12:03 – 2026-07-11T07:44:07

Es gab zwei getrennte Vorfälle: 96 fehlgeschlagene Anmeldungen gegen `administrator` führten um 02:04 zu einer Kontosperrung, und unabhängig davon löste ein Storage-/Treiberproblem um 04:11 einen Kernel-Bugcheck aus. Der zweite Vorfall ist kritisch, weil danach C: nur noch 3,1 GB von 237,4 GB frei hat und die Dienste `postgresql-x64-16` und `WWS-AppServer` weiter auf `Stopped` stehen.

## Lage

| | |
|---|---|
| Letzter Start | 2026-07-11T04:11:30 |
| Datenträger C: | 3,1 GB frei von 237,4 GB (1,3 %) |
| Hängende Dienste | `postgresql-x64-16` (Stopped), `WWS-AppServer` (Stopped) |
| Kritische Vorfälle | V1 kritisch, V2 hoch |

## Vorfall V1 — IAStorVD-/Storage-Problem → Kernel-Bugcheck → PostgreSQL/WWS-Dienststörung  ⚠️ kritisch

**Ursache:** Ein instabiler Intel-RAID/VMD-Treiber `iaStorVD.sys` auf `\Device\RaidPort1`, zeitlich nach Installation von `KB5062170`.

**Kette:**
1. 2026-07-11T03:47:05: Treiberupdate `iaStorVD.sys 20.10.1.1023 (KB5062170)` installiert.
2. 2026-07-11T04:07:31: mehrfaches Event 129, `\Device\RaidPort1` wurde zurückgesetzt.
3. 2026-07-11T04:09:18: Event 41, Kernel-Power / harter Neustart.
4. 2026-07-11T04:11:02: WER meldet `0x000000d1`, fehlerhaftes Modul `iaStorVD.sys`.
5. 2026-07-11T04:11:02: `MEMORY.DMP` wird geschrieben und belegt 9,7 GB.
6. 2026-07-11T04:12:40: `postgresql-x64-16` startet wegen Timeout nicht.
7. 2026-07-11T04:12:41: `WWS-AppServer` startet nicht, weil PostgreSQL nicht läuft.
8. 2026-07-11T04:22:40: `postgresql-x64-16` beendet sich erneut unerwartet.
9. Seit 2026-07-11T04:11:30: Inventar zeigt `postgresql-x64-16` und `WWS-AppServer` auf `Stopped`, gleichzeitig ist C: fast voll.

**Warum ein einfacher Neustart nicht reicht:** Der Absturz hat ein 9,7-GB-Dump auf C: hinterlassen; bei nur 1,3 % freiem Platz kann das die Stabilisierung und Dienststarts weiter behindern. Die eigentliche Ursache bleibt der Storage-/Treiberpfad, nicht der Dienst selbst.

**Belege:** `Event 19` für `iaStorVD.sys 20.10.1.1023 (KB5062170)`, `Event 129` auf `\Device\RaidPort1`, `Event 1001` mit `0x000000d1` und Modul `iaStorVD.sys`, `Event 7000/7001/7031` für PostgreSQL und den WWS-AppServer, Inventar mit `C: 3,1 GB frei` und `MEMORY.DMP 9,7 GB`.

**Zuversicht:** hoch — für die Zuordnung zum Treiber ist die Beweislage stark; offen bleibt, ob `KB5062170` bzw. `iaStorVD.sys` bereits als bekannt problematisch bestätigt ist und warum PostgreSQL nach 04:22:40 erneut abstürzte.

## Vorfall V2 — Brute-Force gegen `administrator` → Kontosperrung  🔒 hoch

**Ursache:** Brute-Force- oder Password-Spraying-Versuch gegen das Konto `administrator` von `198.51.100.42`.

**Kette:**
1. 2026-07-11T01:47:12: Beginn von 96 fehlgeschlagenen Netzwerk-Anmeldungen (`Event 4625`) für `administrator`.
2. 2026-07-11T02:03:49: Ende der Fehlversuchsserie.
3. 2026-07-11T02:04:01: `Event 4740`, Konto `administrator` gesperrt.

**Belege:** `Event 4625 x96` von `198.51.100.42`, danach `Event 4740` für `administrator`.

**Zuversicht:** hoch — für die Klassifizierung als Angriffsserie reicht die Ereignisfolge aus; offen ist nur, ob `198.51.100.42` zu einer bekannten Verwaltungsstelle gehört.

## Was jetzt zu tun ist

1. **Sofort:** `MEMORY.DMP` von `C:\Windows` nach `D:\dumps` archivieren, nicht löschen. *(im Skript enthalten)*
2. **Sofort:** `postgresql-x64-16` starten und Status prüfen. *(im Skript enthalten)*
3. **Sofort:** `WWS-AppServer` starten und Status prüfen. *(im Skript enthalten)*
4. **Manuell, nach Rücksprache:** Den Intel-RAID/VMD-Treiber `iaStorVD.sys` bzw. `KB5062170` nur nach Herstellerprüfung und im Wartungsfenster zurückrollen oder aktualisieren.
5. **Separat:** Für V2 ein eigenes Security-Ticket anlegen: Quell-IP `198.51.100.42` prüfen/sperren und das Konto `administrator` härten.

## Bewusst nicht verknüpft

Der Brute-Force-Vorfall gegen `administrator` liegt zwar am selben Morgen wie der Storage-/Kernel-Absturz, aber es gibt keinen Beleg für eine Verbindung. `WindowsUpdateFailure3` um 01:15:22 und das kumulative Update `KB5061980` wurden ebenfalls nicht als Ursache der späteren Abstürze verknüpft; belastbarer ist der Treiber `iaStorVD.sys`.

---
*Der Reparaturvorschlag (`remediation.ps1`) stammt von einem Agenten, der unter `--dry-run` lief und keinerlei verändernde Werkzeuge hatte. Nichts wurde ausgeführt. Freigabe: `.\Invoke-WinTriage.ps1 -Apply`.*
