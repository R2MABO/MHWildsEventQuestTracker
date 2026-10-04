# Wilds · Quest Tracker

Lokaler Eventquest-Tracker für Monster Hunter Wilds. HTML/CSS/JavaScript im normalen Browser, Python und SQLite für die Speicherung. Keine Cloud, keine Anmeldung, keine zusätzlichen Python-Pakete und keine externen Schriftarten oder CDN-Abhängigkeiten.

## Starten

Voraussetzung: **Python 3.10 oder neuer** von [python.org](https://www.python.org/downloads/). Unter Windows „Add Python to PATH“ aktivieren. Den gesamten Projektordner aufbewahren, nicht nur die HTML-Datei.

Auf dem vorbereiteten Rechner verwendet der Starter bereits die vorhandene Python-Laufzeit über die lokale Datei `.python-path`. Diese enthält nur den Pfad zum Interpreter, wird nicht mit der Anwendung geteilt und kann bei Bedarf angepasst werden. Ohne diese Datei suchen die Starter nach regulär installiertem Python.

- **Windows:** `start.bat` doppelklicken.
- **Linux:** im Projektordner `sh start.sh` ausführen; optional `chmod +x start.sh` und danach `./start.sh`.
- **macOS:** im Projektordner `chmod +x start.command` einmalig ausführen, dann `start.command` doppelklicken. Alternativ `sh start.sh` im Terminal.

Der Starter öffnet `http://127.0.0.1:8765` im Standardbrowser. Das Startfenster während der Nutzung geöffnet lassen; mit **Strg+C** beenden. Das Schließen des Browser-Tabs beendet den lokalen Dienst nicht. Bei belegtem Port zuerst prüfen, ob der Tracker schon läuft, oder z. B. `python3 app.py --port 8766` nutzen (Windows: `py -3 app.py --port 8766`). Die Anwendung lauscht nur auf dem eigenen Rechner.

Direktstart: `python3 app.py` beziehungsweise `py -3 app.py`. `--no-browser` verhindert das automatische Öffnen, `--data-dir PFAD` verwendet einen anderen Datenordner. Daten sind vom Browser unabhängig und werden direkt gespeichert.

## Daten und Privatsphäre

```
data/
  quests.sqlite       # Quests und Stammdaten ohne Häkchen
  images/             # Belohnungsbilder und Monster-Icons, über Inhalts-Hash referenziert
  userdata.sqlite     # Persönliche Häkchen und bestätigte fremde Quest-IDs
seed/
  catalog.zip         # Mitgelieferte erste Questliste, ohne Nutzerdaten
```

Die mitgelieferte Liste enthält 53 Quests und 49 Belohnungsbilder aus dem bereitgestellten Notion-Export sowie 35 große Monster einschließlich Varianten und ein Unbekannt-Icon. Die Icons stammen aus dem [Monster Hunter Wiki](https://monsterhunterwiki.org/wiki/Category:MHWilds_Monster_Icons); Einzelquellen stehen in `seed/ICON_SOURCES.md`. Beim Erstimport auf dem ursprünglichen Rechner werden bestehende Häkchen in `userdata.sqlite` übernommen. Ein neuer Datenordner startet mit derselben Questliste **ohne** persönlichen Fortschritt. Der Seed wird nur beim erstmaligen Erstellen der Katalogdatenbank geladen; eine bewusst geleerte Liste bleibt leer.

**Zum Teilen „Questliste teilen“ verwenden.** Die ZIP enthält ausschließlich `catalog.json` mit Quests, Stammdaten und deren gemeinsamen Namens-/ID-Zuordnungen sowie zugehörige Bilder und Icons. Häkchen und persönliche Quest-Import-Zuordnungen sind darin nicht enthalten. Den gesamten `data/`-Ordner oder den originalen Notion-Export nicht als öffentlichen Questkatalog weitergeben: Sie enthalten persönliche Daten.

Das Archivsymbol neben „Questliste teilen“ erstellt ein ausdrücklich **privates Backup** mit Katalog, Bildern und `userdata.json`. Zur Wiederherstellung dieses Backup importieren und „Persönlichen Fortschritt aus dieser Datei übernehmen“ aktivieren. Ein gewöhnlicher Questlisten-Import verändert vorhandene Häkchen nicht. Zum direkten Sichern oder Umziehen den Tracker beenden und anschließend den vollständigen `data/`-Ordner kopieren. Ein regelmäßiges privates Backup empfiehlt sich.

## Quests und Filter

- Quests anlegen, bearbeiten und mit Bestätigung löschen; mehrere Jagdziele mit Anzahl, einem Monster aus der durchsuchbaren Icon-Liste und einem unabhängig gewählten Zustand (Normal, Tempered, Frenzy, Archtempered oder eigene Zustände).
- Rang, Sterne (auch 11+), Jägerrangbeschränkung, mehrere Belohnungsarten als Tags, mehrere benannte Belohnungen mit eigener benötigter Anzahl als Freitext, Notizen und Bilder.
- Suche nach Questname, Monster oder Belohnung; kombinierbare Filter für Fortschritt, Rang, Sterne, eigenen Jägerrang, Monster, Monsterzustand, Belohnungsarten, Gebiet, Questtyp und eigene Tags. Belohnungsarten innerhalb der Auswahl werden mit ODER kombiniert; verschiedene Filtergruppen mit UND. Monster und Zustand müssen auf dasselbe Jagdziel passen.
- „Alle Belohnungen“ setzt automatisch „Erster Abschluss“. „Alle Belohnungen“ zurücknehmen lässt den Erstabschluss stehen. Wird der Erstabschluss zurückgenommen, wird auch „Alle Belohnungen“ zurückgenommen.
- Auf den Questnamen klicken, um Details aufzuklappen; auf ein Bild klicken, um die Galerie zu öffnen. `/` fokussiert die Suche, Pfeiltasten wechseln Galeriebilder, Escape schließt Dialoge.
- Sterne schlagen Low-Rank (1–3), High-Rank (4–10) oder Master-Rank (11+) vor. Diese Zuordnung ist eine editierbare Ausgangseinstellung, kein unveränderliches Spiellimit.

## Stammdaten

Über **+ Neu** eine Quest oder einen Eintrag für Monster, Monsterzustände, Ränge, Belohnungsarten, Gebiete, Questtypen und eigene Tags anlegen. Kleine Plusbuttons im Questeditor ergänzen die jeweilige Liste und wählen den neuen Eintrag direkt aus. Gebiete und Tags starten leer; Questtypen enthalten Jagd, Fang und Sammeln. Monster können eigene Icons erhalten. Ein Zustand bekommt eine frei wählbare Farbe per Farbwähler oder Hexcode. Die Icon-Umrandung verwendet exakt diese Farbe; Normal/ohne Zustand hat keine Border. Ausgangsfarben: Tempered `#7837FC`, Archtempered `#BE4233`, Frenzy `#1C0037`.

**Stammdaten verwalten** bietet Suche, Bearbeiten und Zusammenführen pro Kategorie. Umbenennen aktualisiert alle zugeordneten Quests, während IDs und Fortschritt erhalten bleiben. Zusammenführen übernimmt die Zuordnungen in den beibehaltenen Eintrag; alte Namen und IDs bleiben für spätere Imports bekannt. Normal bleibt als neutraler Zustand erhalten. Ränge können einen optionalen Sternbereich für den automatischen Vorschlag bekommen.

Beim ersten Start mit einer bestehenden Version-1-Datenbank entsteht vor der Migration eine Sicherung unter `data/migration-backup-v1/quests.sqlite`. Die Nutzerdatenbank bleibt getrennt; Quests und Häkchen bleiben erhalten.

## Import und Updates

Neue Stammdaten und alle Icons werden aus einer Questliste ergänzt. Vorhandene lokale Namen und Farben bleiben standardmäßig erhalten. **Vorhandene Stammdaten aus der ZIP aktualisieren** übernimmt auch diese Einstellungen und mitgelieferte Zusammenführungen. Version-1-Questlisten und Notion-Exports bleiben importierbar.

Über „Importieren“ Quest-ZIP, privates Backup oder einen Notion-CSV-ZIP-Export auswählen. Die Vorschau bietet für jeden Eintrag **aktualisieren**, **als separate Quest übernehmen** oder **überspringen** an. Nicht enthaltene Quests bleiben erhalten.

Quest-IDs sind UUIDs und ändern sich bei normalen Bearbeitungen nicht. Gleiche IDs sowie bestätigte Import-Zuordnungen werden erkannt. Bei unabhängig angelegten Quests schlägt die App anhand von Namen und Jagdzielen mögliche Duplikate vor; diese werden ohne Bestätigung nicht zusammengeführt. Auch eine andere lokale Quest lässt sich manuell zuordnen, z. B. bei Übersetzungen. Bei einer Aktualisierung bleibt die lokale ID samt Fortschritt erhalten; die fremde ID wird ausschließlich in der Nutzerdatenbank vermerkt. Zwei Einträge auf dieselbe lokale Quest zuzuordnen wird abgelehnt.

Die Vorschau gilt 15 Minuten. Alle Questeinträge werden vor der Übernahme validiert. Bilder werden vor dem Datenbank-Commit gespeichert; fehlende Bilder, ungültige IDs, doppelte ZIP-Pfade oder nicht unterstützte Versionen führen zum Abbruch. Grenzen: 120 MB ZIP-Upload, 250 MB entpackt, 1000 Quests, 20 MB pro Bild. Unterstützte Bilder: PNG, JPEG, GIF, WebP. Nicht mehr referenzierte Bilder werden auf der Festplatte behalten, aber nicht exportiert; so werden gemeinsam verwendete Bilder nicht versehentlich gelöscht.

Notion-Markierungen: `§` und `$` → Tempered, `!` → Frenzy (ehemals Rasend), `[]` → Archtempered. Bekannte Schreibweisen wie `ReyDau` und `Rey-Dau` werden demselben Monster zugeordnet; `W.-` wird den entsprechenden Wächter-Monstern zugeordnet. Originale Jagdzieltexte und spezifische Rüstkugelarten bleiben als Notizen erhalten. Unbekannte Namen werden als neue Stammdaten übernommen. Bei weiteren Notion-Importen wird vorhandener Fortschritt nur bei ausdrücklicher Auswahl der persönlichen Übernahme geändert.

Einmaliger Erstimport per Terminal: `python3 app.py --import-notion PFAD_ZUR_ZIP`. Dieser Befehl übernimmt auch die Häkchen und beendet sich anschließend. Bei möglichen Duplikaten die Oberfläche verwenden.

## Prüfen

`python3 -m unittest discover -s tests -v` (Windows: `py -3 -m unittest discover -s tests -v`). Die Tests verwenden temporäre Datenordner. Anwendungscode und Starter sind für alle drei Betriebssysteme ausgelegt; die tatsächliche Browserprüfung erfolgte unter Windows. Linux/macOS-Starts benötigen eine Prüfung auf diesen Betriebssystemen.

`python3 tools/package_release.py` erstellt `dist/wilds-quest-tracker.zip` zum Weitergeben der gesamten Anwendung. Es enthält die Oberfläche, alle drei Starter und die öffentliche Startliste mit Bildern, aber keinen persönlichen Datenordner. Entpacken und den Starter für das jeweilige Betriebssystem nutzen.

Das ZIP-Format ist versioniert (`mh-wilds-quests`, Version 2; Version 1 wird weiterhin eingelesen). Persönliche Daten sind gesondert versioniert (`mh-wilds-userdata`, Version 1). Keine externe API und kein Internetzugriff sind für den Betrieb erforderlich. `tools/fetch_monsters.py` lädt die Wiki-Icons bei Bedarf erneut und braucht dazu Internetzugriff; die ausgelieferte Anwendung enthält sie bereits. Inoffizielles Fanprojekt; Monster Hunter ist eine Marke von Capcom.
