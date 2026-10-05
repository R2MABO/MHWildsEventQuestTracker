# Wilds · Quest Tracker

Lokaler Eventquest- und Kronen-Tracker für Monster Hunter Wilds. HTML/CSS/JavaScript im normalen Browser, Python und SQLite für die Speicherung. Keine Cloud, keine Anmeldung und keine externen Schriftarten oder CDN-Abhängigkeiten. Die nativen ZIP-Builds enthalten die Python-Laufzeit; eine Python-Installation ist dafür nicht erforderlich.

## Monster Kronen

Links unter **Eventquests** öffnet **Monster Kronen** den Crown Tracker. Er enthält ausschließlich die 29 Monster aus dem bereitgestellten Notion-Kronenexport; neue Installationen beginnen ohne persönliche Kronen. Jede Karte zeigt ein Monster-Icon und unabhängige Checkboxen für die kleine und die goldene Krone.

Die Suche findet Monsternamen auch ohne Bindestriche. Der Fortschrittsfilter zeigt alle Monster, keine Krone, nur kleine, nur goldene oder beide Kronen. Karten am Griff ziehen, um sie vor oder hinter einer anderen Karte einzuordnen. Alternativ den Griff fokussieren und die Pfeiltasten verwenden. Das funktioniert auch bei aktiver Suche oder Filterung; ausgeblendete Monster bleiben in der Gesamtreihenfolge erhalten. Fortschritt und Reihenfolge liegen in `userdata.sqlite` und bleiben bei Browserwechsel erhalten.

**Monster anlegen** öffnet ein Formular für Name und ein optionales eigenes Bild (PNG, JPEG, WebP oder GIF). Der Stift auf einer Karte bearbeitet Name und Bild. Diese Monster sind unabhängig von den Quest-Stammdaten. Private Backups enthalten Kronenmonster, Bilder, Kronen und Reihenfolge; beim Import die Option zur Übernahme persönlichen Fortschritts aktivieren. Öffentliche Questlisten enthalten keinen Kronenfortschritt.

Die Kronen-Icons stammen aus [MHWiki Monster UI Icons](https://monsterhunterwiki.org/wiki/Category:MHWiki_Monster_UI_Icons) und werden offline aus dem Projekt geladen. Die Monster-Icons verwenden den bereits vorhandenen Wilds-Wiki-Katalog. Quellen stehen in `seed/ICON_SOURCES.md`.

Der persönliche Notion-Fortschritt kann bei Bedarf erneut übernommen werden: `python tools/import_crowns.py "Pfad/zum/Export.zip" --data-dir data`. Dies überschreibt die Kronenhäkchen der 29 Exportmonster. `--build-seed` erzeugt ausschließlich die öffentliche Monsterliste ohne persönliche Häkchen.

## Starten

### Native ZIP-Builds (ohne Python-Installation)

Die passende ZIP vollständig in einen beschreibbaren Ordner entpacken:

- **Windows:** `wilds-quest-tracker-windows.zip` → `WildsQuestTracker.exe` doppelklicken.
- **Linux:** `wilds-quest-tracker-linux.zip` → `./WildsQuestTracker` starten. Falls das Entpackprogramm die Ausführungsrechte entfernt: einmalig `chmod +x WildsQuestTracker`.
- **macOS:** `wilds-quest-tracker-macos.zip` → `WildsQuestTracker.app` doppelklicken.

Der Standardbrowser öffnet sich automatisch. Nach dem Schließen des letzten Tracker-Tabs beendet sich die native Anwendung nach acht Sekunden. Unter Windows/Linux erscheint ein Konsolenfenster, das ebenfalls zum Beenden geschlossen werden kann. Die macOS-App protokolliert Startfehler unter `data/tracker-start.log`.

Der persönliche `data/`-Ordner entsteht neben der EXE, Linux-Datei bzw. macOS-App, außerhalb der eingebetteten Ressourcen. Beim Update diesen Ordner behalten; vorhandene Daten einer Quellcode-Version können bei beendetem Tracker dorthin kopiert werden. `--data-dir` bleibt verfügbar. Mit `--no-browser` läuft die Anwendung dauerhaft, sofern nicht zusätzlich `--auto-stop` angegeben wird.

Die GitHub-Builds sind für Windows/Linux x64 und macOS Intel x64 ausgelegt (auf Apple Silicon mit Rosetta). Lokale Builds verwenden die Architektur des Build-Rechners; sie steht in `BUILD.txt`. Der Linux-Build entsteht auf Ubuntu 22.04 und setzt eine kompatible Linux-Umgebung mit glibc 2.35 oder neuer voraus. Die macOS-App ist nicht mit einem Apple-Entwicklerzertifikat signiert oder notarisiert; macOS kann beim ersten Start eine Freigabe unter **Datenschutz & Sicherheit** verlangen.

### Quellcode starten

Voraussetzung: **Python 3.10 oder neuer** von [python.org](https://www.python.org/downloads/). Unter Windows „Add Python to PATH“ aktivieren. Den gesamten Projektordner aufbewahren, nicht nur die HTML-Datei.

Auf dem vorbereiteten Rechner verwendet der Starter bereits die vorhandene Python-Laufzeit über die lokale Datei `.python-path`. Diese enthält nur den Pfad zum Interpreter, wird nicht mit der Anwendung geteilt und kann bei Bedarf angepasst werden. Ohne diese Datei suchen die Starter nach regulär installiertem Python.

- **Windows:** `start.bat` doppelklicken. Der Tracker startet mit sichtbarem Konsolenfenster; dieses während der Nutzung geöffnet lassen oder minimieren.
- **Linux:** im Projektordner `sh start.sh` ausführen; optional `chmod +x start.sh` und danach `./start.sh`.
- **macOS:** im Projektordner `chmod +x start.command` einmalig ausführen, dann `start.command` doppelklicken. Alternativ `sh start.sh` im Terminal.

Der Starter öffnet `http://127.0.0.1:8765` im Standardbrowser. Der lokale Server läuft im Konsolenfenster. Das Schließen des Fensters oder **Strg+C** beendet den Server; das Schließen eines Browser-Tabs beendet ihn beim normalen Start nicht. Startfehler werden direkt im Konsolenfenster angezeigt.

Optional aktiviert `--auto-stop` das automatische Beenden nach dem Schließen des letzten Tracker-Tabs, auch beim Direktstart. Der Server wartet nach dem letzten Verbindungsabbruch acht Sekunden, damit Neuladen möglich bleibt. Bei belegtem Port zuerst prüfen, ob der Tracker schon läuft, oder z. B. `python3 app.py --port 8766` nutzen (Windows: `py -3 app.py --port 8766`). Die Anwendung lauscht nur auf dem eigenen Rechner.

Direktstart: `python3 app.py` beziehungsweise `py -3 app.py`. `--no-browser` verhindert das automatische Öffnen, `--data-dir PFAD` verwendet einen anderen Datenordner. Daten sind vom Browser unabhängig und werden direkt gespeichert.

Bei einem Verbindungsabbruch erscheint oben mittig dauerhaft „Server nicht erreichbar“, auch über geöffneten Dialogen. Bearbeitung, Fortschritt und Speichern werden gesperrt; offene Eingaben bleiben im Tab erhalten. Den Tracker erneut starten: Die Seite prüft die Verbindung automatisch und gibt die Bearbeitung wieder frei. Der Hinweis funktioniert auch beim Konsolenstart. Ungespeicherte Entwürfe werden dadurch nicht automatisch gespeichert; nach der Wiederverbindung selbst speichern und den Tab bis dahin geöffnet lassen.

Das kompakte Logo oben links liegt unter `web/logo.png`. `web/favicon.ico` enthält dasselbe Motiv mit transparentem Hintergrund in 16, 24, 32, 48, 64, 128 und 256 Pixeln. Die Oberfläche und das Browser-Icon verwenden `web/favicon.svg`, das das PNG direkt einbettet. Der Windows-Build bindet die ICO-Datei als EXE-Anwendungssymbol ein. Der Quellcode-Starter bleibt eine BAT-Datei.

## Daten und Privatsphäre

```
data/
  quests.sqlite       # Quests, Stammdaten und Kronenmonster ohne Häkchen
  images/             # Belohnungsbilder und Monster-Icons, über Inhalts-Hash referenziert
  userdata.sqlite     # Quest-/Kronenhäkchen, Monsterreihenfolge und bestätigte fremde Quest-IDs
seed/
  catalog.zip         # Mitgelieferte erste Questliste, ohne Nutzerdaten
```

Die mitgelieferte Liste enthält 53 Quests und 49 Belohnungsbilder aus dem bereitgestellten Notion-Export sowie 35 große Monster einschließlich Varianten und ein Unbekannt-Icon. Die Icons stammen aus dem [Monster Hunter Wiki](https://monsterhunterwiki.org/wiki/Category:MHWilds_Monster_Icons); Einzelquellen stehen in `seed/ICON_SOURCES.md`. Beim Erstimport auf dem ursprünglichen Rechner werden bestehende Häkchen in `userdata.sqlite` übernommen. Ein neuer Datenordner startet mit derselben Questliste **ohne** persönlichen Fortschritt. Der Seed wird nur beim erstmaligen Erstellen der Katalogdatenbank geladen; eine bewusst geleerte Liste bleibt leer.

**Zum Teilen „Questliste teilen“ verwenden.** Die ZIP enthält ausschließlich `catalog.json` mit Quests, Stammdaten und deren gemeinsamen Namens-/ID-Zuordnungen sowie zugehörige Bilder und Icons. Häkchen und persönliche Quest-Import-Zuordnungen sind darin nicht enthalten. Den gesamten `data/`-Ordner oder den originalen Notion-Export nicht als öffentlichen Questkatalog weitergeben: Sie enthalten persönliche Daten.

Das Archivsymbol neben „Questliste teilen“ erstellt ein ausdrücklich **privates Backup** mit Katalog, Bildern und `userdata.json`. Zur Wiederherstellung dieses Backup importieren und „Persönlichen Fortschritt aus dieser Datei übernehmen“ aktivieren. Ein gewöhnlicher Questlisten-Import verändert vorhandene Häkchen nicht. Zum direkten Sichern oder Umziehen den Tracker beenden und anschließend den vollständigen `data/`-Ordner kopieren. Ein regelmäßiges privates Backup empfiehlt sich.

## Quests und Filter

Der Caret-Button rechts neben der Suche klappt alle Quests gemeinsam auf oder zu. Einzelne Quests lassen sich weiterhin über ihren Namen auf- und einklappen.

Im Listenkopf lassen sich die Breiten von Quest, Rang, Gebiet, Belohnung und Fortschritt an den senkrechten Griffen ziehen (auf größeren Ansichten). Beim Verbreitern geben die Spalten rechts Platz bis zu ihrer Mindestbreite ab; beim Fortschritt wird die Bildspalte rechts davon breiter oder schmaler. Die Bildvorschau und der Bearbeitungsbutton bleiben rechtsbündig; alle Spalten und der Bearbeitungsbutton bleiben innerhalb der Liste. Die Einstellung bleibt in diesem Browser gespeichert; beim ersten Start gilt die Standardaufteilung. Ein Doppelklick auf einen Griff stellt die Standardaufteilung wieder her. Die Griffe lassen sich auch mit Tab fokussieren und mit den Pfeiltasten bedienen (Umschalt für größere Schritte, Pos1 für die Standardaufteilung).

- Quests anlegen, bearbeiten und mit Bestätigung löschen; mehrere Jagdziele mit Anzahl, einem Monster aus der durchsuchbaren Icon-Liste und einem unabhängig gewählten Zustand (Normal, Tempered, Frenzy, Archtempered oder eigene Zustände).
- Rang, Sterne (auch 11+), Jägerrangbeschränkung, mehrere Belohnungsarten als Tags, mehrere benannte Belohnungen mit eigener benötigter Anzahl als Freitext, Notizen und Bilder.
- Suche nach Questname, Monster oder Belohnung; kombinierbare Filter für Fortschritt, Rang, Sterne, eigenen Jägerrang, Monster, Monsterzustand, Belohnungsarten, Gebiet, Questtyp. Belohnungsarten innerhalb der Auswahl werden mit ODER kombiniert; verschiedene Filtergruppen mit UND. Monster und Zustand müssen auf dasselbe Jagdziel passen.
- „Alle Belohnungen“ setzt automatisch „Erster Abschluss“. „Alle Belohnungen“ zurücknehmen lässt den Erstabschluss stehen. Wird der Erstabschluss zurückgenommen, wird auch „Alle Belohnungen“ zurückgenommen.
- Auf den Questnamen klicken, um Details aufzuklappen; auf ein Bild klicken, um die Galerie zu öffnen. `/` fokussiert die Suche, Pfeiltasten wechseln Galeriebilder, Escape schließt Dialoge.
- Sterne schlagen Low-Rank (1–3), High-Rank (4–10) oder Master-Rank (11+) vor. Diese Zuordnung ist eine editierbare Ausgangseinstellung, kein unveränderliches Spiellimit.

## Stammdaten

Über **+ Neu** eine Quest oder einen Eintrag für Monster, Monsterzustände, Ränge, Belohnungsarten, Gebiete, Questtypen anlegen. Kleine Plusbuttons im Questeditor ergänzen die jeweilige Liste und wählen den neuen Eintrag direkt aus. Gebiete starten leer; Questtypen enthalten Jagd, Fang und Sammeln. Monster können eigene Icons erhalten. Ein Zustand bekommt eine frei wählbare Farbe per Farbwähler oder Hexcode. Die Icon-Umrandung verwendet exakt diese Farbe; Normal/ohne Zustand hat keine Border. Ausgangsfarben: Tempered `#7837FC`, Archtempered `#BE4233`, Frenzy `#1C0037`.

**Stammdaten verwalten** bietet Suche, Bearbeiten und Zusammenführen pro Kategorie. Umbenennen aktualisiert alle zugeordneten Quests, während IDs und Fortschritt erhalten bleiben. Zusammenführen übernimmt die Zuordnungen in den beibehaltenen Eintrag; alte Namen und IDs bleiben für spätere Imports bekannt. Normal bleibt als neutraler Zustand erhalten. Ränge können einen optionalen Sternbereich für den automatischen Vorschlag bekommen.

Belohnungsarten erhalten unter **Stammdaten verwalten → Belohnungsart → Bearbeiten** eine eigene Kategoriefarbe per Farbwähler oder Hexcode mit Vorschau. Die Farbe erscheint in der Questliste, den Filtern und im Questeditor; die Schriftfarbe passt sich für lesbaren Kontrast an. **Standardfarbe verwenden** wählt die kräftige Standardfarbe der jeweiligen Kategorie: Ausrüstung Gold, Materialien Cyan, Artian Material Pink, Rüstkugeln Orange, Dekorationen Violett, Jägerrang XP Limette und Kochzutaten Mint. Eigene Kategorien erhalten automatisch eine Farbe. Eigene Kategoriefarben werden mit den Stammdaten gespeichert und in Questlisten und Backups exportiert.

Beim ersten Start mit einer bestehenden Version-1-Datenbank entsteht vor der Migration eine Sicherung unter `data/migration-backup-v1/quests.sqlite`. Die Nutzerdatenbank bleibt getrennt; Quests und Häkchen bleiben erhalten.

Gebiete bekommen ebenfalls eine Kategoriefarbe mit Vorschau unter **Stammdaten verwalten → Gebiet → Bearbeiten**. Sie erscheinen als farbige Labels zwischen Belohnung und Fortschritt in jeder Questzeile. Im Listenkopf sortiert **Gebiet** auf- oder absteigend; Quests ohne Zuordnung stehen immer am Ende. Die Farben bleiben beim Export und Import erhalten. Custom Tags werden nicht mehr unterstützt; vorhandene Zuordnungen werden beim Start entfernt, ältere ZIP-Dateien bleiben importierbar. Vor der Datenbankumstellung wird eine Sicherung im Datenordner angelegt.

## Theme bearbeiten

Der Palettenbutton rechts neben dem Wilds-Logo öffnet den Theme-Editor. **Aktuell** stellt das ursprüngliche Wilds-Design wieder her; **Dark** und **Light** bieten weitere Vorlagen. Grundfarbe, Akzentfarbe und zweite Akzentfarbe lassen sich per Farbwähler oder Hexcode ändern. Der Tracker erzeugt daraus automatisch abgestufte Flächen, Konturen und kontrastreiche Textfarben. Änderungen erscheinen sofort als Vorschau. **Theme speichern** merkt die Auswahl in diesem Browser; **Abbrechen**, das Schließen-Symbol oder Escape stellen das zuletzt gespeicherte Theme wieder her. Monsterzustandsfarben bleiben unabhängig davon in den Stammdaten definiert. Themes gehören zum lokalen Browserspeicher und sind nicht Teil von Questlisten oder privaten ZIP-Backups.

## Import und Updates

Neue Stammdaten und alle Icons werden aus einer Questliste ergänzt. Vorhandene lokale Namen und Farben bleiben standardmäßig erhalten. **Vorhandene Stammdaten aus der ZIP aktualisieren** übernimmt auch diese Einstellungen und mitgelieferte Zusammenführungen. Version-1-Questlisten und Notion-Exports bleiben importierbar.

Über „Importieren“ Quest-ZIP, privates Backup oder einen Notion-CSV-ZIP-Export auswählen. Die Vorschau bietet für jeden Eintrag **aktualisieren**, **als separate Quest übernehmen** oder **überspringen** an. Nicht enthaltene Quests bleiben erhalten.

Quest-IDs sind UUIDs und ändern sich bei normalen Bearbeitungen nicht. Gleiche IDs sowie bestätigte Import-Zuordnungen werden erkannt. Bei unabhängig angelegten Quests schlägt die App anhand von Namen und Jagdzielen mögliche Duplikate vor; diese werden ohne Bestätigung nicht zusammengeführt. Auch eine andere lokale Quest lässt sich manuell zuordnen, z. B. bei Übersetzungen. Bei einer Aktualisierung bleibt die lokale ID samt Fortschritt erhalten; die fremde ID wird ausschließlich in der Nutzerdatenbank vermerkt. Zwei Einträge auf dieselbe lokale Quest zuzuordnen wird abgelehnt.

Die Vorschau gilt 15 Minuten. Alle Questeinträge werden vor der Übernahme validiert. Bilder werden vor dem Datenbank-Commit gespeichert; fehlende Bilder, ungültige IDs, doppelte ZIP-Pfade oder nicht unterstützte Versionen führen zum Abbruch. Grenzen: 120 MB ZIP-Upload, 250 MB entpackt, 1000 Quests, 20 MB pro Bild. Unterstützte Bilder: PNG, JPEG, GIF, WebP. Nicht mehr referenzierte Bilder werden auf der Festplatte behalten, aber nicht exportiert; so werden gemeinsam verwendete Bilder nicht versehentlich gelöscht.

Notion-Markierungen: `§` und `$` → Tempered, `!` → Frenzy (ehemals Rasend), `[]` → Archtempered. Bekannte Schreibweisen wie `ReyDau` und `Rey-Dau` werden demselben Monster zugeordnet; `W.-` wird den entsprechenden Wächter-Monstern zugeordnet. Originale Jagdzieltexte und spezifische Rüstkugelarten bleiben als Notizen erhalten. Unbekannte Namen werden als neue Stammdaten übernommen. Bei weiteren Notion-Importen wird vorhandener Fortschritt nur bei ausdrücklicher Auswahl der persönlichen Übernahme geändert.

Einmaliger Erstimport per Terminal: `python3 app.py --import-notion PFAD_ZUR_ZIP`. Dieser Befehl übernimmt auch die Häkchen und beendet sich anschließend. Bei möglichen Duplikaten die Oberfläche verwenden.

## Prüfen

`python3 -m unittest discover -s tests -v` (Windows: `py -3 -m unittest discover -s tests -v`). Die Tests verwenden temporäre Datenordner. Anwendungscode und Starter sind für alle drei Betriebssysteme ausgelegt; die tatsächliche Browserprüfung erfolgte unter Windows. Linux/macOS-Starts benötigen eine Prüfung auf diesen Betriebssystemen.

Die Verbindungserkennung lässt sich zusätzlich mit `node --test tests/test_connection.js` prüfen. Diese Entwicklungstests benötigen Node.js; für den Betrieb des Trackers ist Node.js nicht erforderlich.

## Native Builds erstellen

Auf dem Build-Rechner sind Python 3.10+ und PyInstaller erforderlich. Einmalig `python -m pip install -r tools/requirements-build.txt` ausführen (Linux/macOS: `python3`). Danach erstellt `python tools/package_release.py` immer **beide Varianten**: die bisherige plattformübergreifende Quellcode-ZIP `dist/wilds-quest-tracker.zip` und die native Anwendung für das **aktuelle** Betriebssystem in `dist/wilds-quest-tracker-windows.zip`, `dist/wilds-quest-tracker-linux.zip` bzw. `dist/wilds-quest-tracker-macos.zip`. Optional: `--output-dir PFAD`.

Die Quellcode-ZIP enthält `start.bat` für Windows, `start.sh` für Linux und `start.command` für macOS sowie Anwendung, Oberfläche, öffentliche Startliste, Tests und Buildwerkzeuge. Sie benötigt beim Nutzer Python 3.10+. Persönliche Daten und `.python-path` bleiben ausgeschlossen. Mit `python tools/package_release.py --source-only` lässt sich diese Variante auch ohne PyInstaller erstellen. Falls der native Build fehlschlägt, bleibt die bereits erzeugte Quellcode-ZIP verfügbar.

Unter Windows kann `tools/build.bat` doppelt angeklickt werden; damit werden die Quellcode-ZIP mit allen drei Startern und die Windows-ZIP mit EXE erstellt. Unter Linux/macOS `sh tools/build.sh` ausführen; dabei entstehen ebenfalls die Quellcode-ZIP und der jeweilige native Build. Die Skripte verwenden bevorzugt eine lokale `.venv-build`-Umgebung, sofern vorhanden. Diese lässt sich mit `python -m venv .venv-build` anlegen; darin die Build-Abhängigkeiten installieren.

PyInstaller baut jeweils auf dem Zielbetriebssystem, nicht alle drei Plattformen auf Windows. Für alle drei nativen ZIPs enthält `.github/workflows/build.yml` den Workflow **Native ZIP builds**: nach dem Push in GitHub unter **Actions → Native ZIP builds → Run workflow** starten, oder einen Tag mit Präfix `v` pushen. Der Workflow testet und baut auf Windows, Linux und macOS und bietet die drei nativen ZIPs sowie einmal die Quellcode-ZIP als getrennte Download-Artefakte an. Bei GitHub-Artefakten gegebenenfalls zuerst die äußere Download-ZIP und dann die darin enthaltene Release-ZIP entpacken.

Die nativen Release-ZIPs enthalten die ausführbare Anwendung, README, Lizenz und Build-Informationen. Oberfläche und öffentliche Startliste samt Icons sind eingebettet; persönliche Daten, lokale Python-Pfade und Starter-Skripte werden darin nicht ausgeliefert. Windows/Linux verwenden eine einzelne ausführbare Datei, macOS ein `.app`-Bundle. Der Workflow prüft jede frisch entpackte Anwendung auf Start, Ressourcen, saubere Kronen-Startdaten, den Datenordner und gespeicherten Fortschritt nach einem Neustart. Lokal: `python tools/smoke_release.py dist/wilds-quest-tracker-windows.zip` (bzw. die ZIP der eigenen Plattform).

Das ZIP-Format ist versioniert (`mh-wilds-quests`, Version 2; Version 1 wird weiterhin eingelesen). Persönliche Daten sind gesondert versioniert (`mh-wilds-userdata`, Version 1). Keine externe API und kein Internetzugriff sind für den Betrieb erforderlich. `tools/fetch_monsters.py` lädt die Wiki-Icons bei Bedarf erneut und braucht dazu Internetzugriff; die ausgelieferte Anwendung enthält sie bereits. Inoffizielles Fanprojekt; Monster Hunter ist eine Marke von Capcom.
