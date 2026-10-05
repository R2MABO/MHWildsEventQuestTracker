"""Local Monster Hunter Wilds quest tracker. Python 3.10+, standard library only."""
from __future__ import annotations

import argparse
import base64
import csv
from contextlib import contextmanager, closing
import difflib
import hashlib
import io
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import sqlite3
import sys
import threading
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote, parse_qs
import uuid
import webbrowser
import zipfile
import catalogs

ROOT = Path(__file__).resolve().parent


def default_data_directory():
    """Keep portable user data outside bundled resources and macOS .app files."""
    if not getattr(sys, 'frozen', False):
        return ROOT / 'data'
    executable = Path(sys.executable).resolve()
    parent = executable.parent
    if (sys.platform == 'darwin' and parent.name == 'MacOS'
            and parent.parent.name == 'Contents' and parent.parent.parent.suffix == '.app'):
        parent = parent.parent.parent.parent
    return parent / 'data'


REWARD_TYPES = ["Ausrüstung", "Materialien", "Artian Material", "Rüstkugeln", "Dekorationen", "Jägerrang XP", "Kochzutaten"]
MONSTER_TYPES = ["Normal", "Tempered", "Frenzy", "Archtempered"]
RANKS = ["Low-Rank", "High-Rank", "Master-Rank"]
MAX_BODY = 120 * 1024 * 1024
MAX_IMAGE = 20 * 1024 * 1024
MAX_UNPACKED = 250 * 1024 * 1024
NOTION_NAMESPACE = uuid.UUID("a5364606-7306-44cd-9712-9ebf812b1cdc")


class ValidationError(ValueError):
    pass


def text_value(value, label, maximum=1000, required=False):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValidationError(f"{label}: ungültiger Text oder zu lang.")
    value = value.strip()
    if required and not value:
        raise ValidationError(f"{label} fehlt.")
    return value


def integer(value, label, minimum=0, maximum=10000, nullable=False):
    if nullable and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValidationError(f"{label}: eine ganze Zahl zwischen {minimum} und {maximum} eingeben.")
    return value


def identifier(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Ungültige Quest-ID.") from None


def normalized(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if c.isalnum())


def image_extension(content):
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return ".webp"
    raise ValidationError("Bilder müssen PNG, JPEG, WebP oder GIF sein.")


def image_key(content):
    if not content or len(content) > MAX_IMAGE:
        raise ValidationError("Ein Bild darf höchstens 20 MB groß sein.")
    return hashlib.sha256(content).hexdigest() + image_extension(content)


def validate_quest(raw):
    if not isinstance(raw, dict):
        raise ValidationError("Ungültiger Questeintrag.")
    quest = {
        "id": identifier(raw.get("id")),
        "name": text_value(raw.get("name"), "Questname", 300, True),
        "rank": text_value(raw.get("rank"), "Rang", 200, True),
        "hr": integer(raw.get("hr"), "Jägerrang", maximum=99999, nullable=True),
        "stars": integer(raw.get("stars"), "Sterne", 1),
        "notes": text_value(raw.get("notes", ""), "Notizen", 4000),
    }
    targets = raw.get("targets")
    if not isinstance(targets, list) or not 1 <= len(targets) <= 30:
        raise ValidationError("Mindestens ein Jagdziel angeben (höchstens 30).")
    quest["targets"] = []
    for target in targets:
        if not isinstance(target, dict):
            raise ValidationError("Ungültige Monsterart.")
        quest["targets"].append({"monster": text_value(target.get("monster"), "Monster", 200, True),
                                 "type": text_value(target.get("type"), "Monsterzustand", 200, True), "count": integer(target.get("count", 1), "Monsteranzahl", 1, 100)})
        for field in ("monster_id", "type_id"):
            if target.get(field) is not None:
                quest["targets"][-1][field] = identifier(target[field])
    types = raw.get("reward_types", [])
    if not isinstance(types, list) or len(types) > 100 or any(not isinstance(t, str) or not t.strip() or len(t) > 200 for t in types):
        raise ValidationError("Ungültige Belohnungsart.")
    quest["reward_types"] = list(dict.fromkeys(types))
    rewards = raw.get("rewards", [])
    if not isinstance(rewards, list) or len(rewards) > 30:
        raise ValidationError("Höchstens 30 Belohnungen angeben.")
    quest["rewards"] = []
    for reward in rewards:
        if not isinstance(reward, dict):
            raise ValidationError("Ungültige Belohnung.")
        quest["rewards"].append({"name": text_value(reward.get("name"), "Belohnung", 300, True),
                                 "required": text_value(reward.get("required", ""), "Benötigte Anzahl", 200)})
    images = raw.get("images", [])
    if not isinstance(images, list) or len(images) > 50 or any(not isinstance(i, str) or not re.fullmatch(r"[a-f0-9]{64}\.(png|jpg|gif|webp)", i) for i in images):
        raise ValidationError("Ungültige Bildreferenz.")
    quest["images"] = list(dict.fromkeys(images))
    for field in ("area", "quest_type"):
        quest[field] = text_value(raw.get(field, ""), field, 200)
    for field in ("rank_id", "area_id", "quest_type_id"):
        if raw.get(field) is not None:
            quest[field] = identifier(raw[field])
        elif field != 'rank_id':
            quest[field] = None
    for field in ("reward_type_ids",):
        if field in raw:
            if not isinstance(raw[field], list) or len(raw[field]) > 100:
                raise ValidationError("Ungültige Stammdaten-Referenzen.")
            quest[field] = [identifier(i) for i in raw[field]]
    # Whitelist intentionally excludes completion flags and other user data.
    return quest


def validate_progress(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get("first_clear"), bool) or not isinstance(raw.get("all_rewards"), bool):
        raise ValidationError("Ungültiger persönlicher Fortschritt.")
    return {"first_clear": raw["first_clear"] or raw["all_rewards"], "all_rewards": raw["all_rewards"]}


def validate_crown_backup(raw):
    if not isinstance(raw, list) or len(raw) > 1000:
        raise ValidationError('Ungültige Kronenliste im Backup.')
    records = []
    for monster in raw:
        if not isinstance(monster, dict) or any(not isinstance(monster.get(k), bool) for k in ('small', 'gold')):
            raise ValidationError('Ungültiger Kronenfortschritt im Backup.')
        key = monster.get('icon')
        if key is not None and (not isinstance(key, str) or not re.fullmatch(r'[a-f0-9]{64}\.(png|jpg|gif|webp)', key)):
            raise ValidationError('Ungültiges Monsterbild im Backup.')
        records.append({'id': identifier(monster.get('id')), 'name': text_value(monster.get('name'), 'Monstername', 200, True),
                        'icon': key, 'source': text_value(monster.get('source', ''), 'Bildquelle', 1000),
                        'small': monster['small'], 'gold': monster['gold']})
    if len({m['id'] for m in records}) != len(records) or len({normalized(m['name']) for m in records}) != len(records):
        raise ValidationError('Doppelte Monster im Kronenbackup.')
    return records


def parse_notion(zf):
    names = zf.namelist()
    csv_names = [n for n in names if n.endswith(".csv")]
    if not csv_names:
        raise ValidationError("Die ZIP enthält weder catalog.json noch eine Notion-CSV.")
    csv_name = next((n for n in csv_names if n.endswith("_all.csv")), csv_names[0])
    rows = list(csv.DictReader(io.StringIO(zf.read(csv_name).decode("utf-8-sig"))))
    if not rows or "Questname" not in rows[0]:
        raise ValidationError("Notion-CSV: Spalte Questname fehlt oder Tabelle ist leer.")
    quests, images, progress, warnings = [], {}, {}, []
    type_map = {"JR XP": "Jägerrang XP", "Koch": "Kochzutaten", "Artien Material": "Artian Material"}
    for row in rows:
        name = row["Questname"].strip()
        qid = str(uuid.uuid5(NOTION_NAMESPACE, normalized(name)))
        source = row.get("Jagdziel", "").strip()
        targets = []
        for item in source.split(" + "):
            item = item.strip()
            count = 1
            match = re.match(r"^(\d+)\s+", item)
            if match:
                count, item = int(match[1]), item[match.end():]
            kind = "Normal"
            for marker, mapped in [("[]", "Archtempered"), ("§", "Tempered"), ("$", "Tempered"), ("!", "Frenzy")]:
                if item.startswith(marker):
                    kind, item = mapped, item[len(marker):]
                    break
            targets.append({"monster": item or "Unbekannt", "type": kind, "count": count})
        category = row.get("Belohnungsart", "").strip()
        reward_types = ["Rüstkugeln" if category.startswith("Rüstkugel") else type_map.get(category, category)] if category else []
        reward_name = row.get("Belohnung", "").strip()
        stars = int(row.get("Sterne") or 1)
        hr = re.search(r"\d+", row.get("JR", ""))
        notes = f"Notion-Jagdziel: {source}" if source else ""
        if category.startswith("Rüstkugel"):
            notes += f"\nNotion-Belohnungsart: {category}"
        quest = {"id": qid, "name": name, "targets": targets, "rank": RANKS[0 if stars <= 3 else 1 if stars <= 10 else 2],
                 "hr": int(hr.group()) if hr else None, "stars": stars, "reward_types": reward_types,
                 "rewards": [{"name": reward_name, "required": row.get("Benötigte Anzahl", "").strip()}] if reward_name else [],
                 "notes": notes, "images": []}
        for filename in row.get("Bilder", "").split(","):
            filename = unquote(filename.strip())
            if not filename:
                continue
            found = next((n for n in names if n == filename or n == str(PurePosixPath(csv_name).parent / filename)), None)
            if found is None:
                warnings.append(f"{name}: Bild {filename} fehlt im Export.")
                continue
            content = zf.read(found)
            key = image_key(content)
            images[key] = content
            quest["images"].append(key)
        quests.append(validate_quest(quest))
        progress[qid] = validate_progress({"first_clear": row.get("1. Abschluss") == "Yes", "all_rewards": row.get("Alle Belohnungen erhalten") == "Yes"})
    return {"quests": quests, "images": images, "progress": progress, "aliases": {}, "catalogs": [], "catalog_id_aliases": [], "source": "Notion", "warnings": warnings}


def parse_package(content):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            entries = zf.infolist()
            if len(entries) > 2000 or sum(i.file_size for i in entries) > MAX_UNPACKED:
                raise ValidationError("Die entpackte ZIP ist zu groß (maximal 250 MB / 2000 Dateien).")
            seen = set()
            for info in entries:
                path = PurePosixPath(info.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in info.filename or ":" in info.filename or info.filename in seen:
                    raise ValidationError("Die ZIP enthält unsichere oder doppelte Dateipfade.")
                seen.add(info.filename)
            if "catalog.json" not in seen:
                parsed = parse_notion(zf)
            else:
                raw = json.loads(zf.read("catalog.json").decode("utf-8"))
                if not isinstance(raw, dict) or raw.get("format") != "mh-wilds-quests" or raw.get("version") not in (1, 2):
                    raise ValidationError("Unbekanntes Quest-ZIP-Format oder nicht unterstützte Version.")
                quests = raw.get("quests")
                if not isinstance(quests, list) or len(quests) > 1000:
                    raise ValidationError("Ungültige Questliste (maximal 1000 Quests).")
                quests = [validate_quest(q) for q in quests]
                records = raw.get("catalogs", [])
                if not isinstance(records, list) or len(records) > 3000:
                    raise ValidationError("Ungültige Stammdatenliste.")
                records = [catalogs.validate_record(r) for r in records if not isinstance(r, dict) or r.get('kind') != 'tag']
                if len({r['id'] for r in records}) != len(records):
                    raise ValidationError("Doppelte Stammdaten-IDs.")
                id_aliases = raw.get("catalog_id_aliases", [])
                if not isinstance(id_aliases, list) or len(id_aliases) > 10000:
                    raise ValidationError("Ungültige Stammdaten-Zuordnungen.")
                validated_aliases = []
                records_by_id = {r['id']: r for r in records}
                for alias in id_aliases:
                    if not isinstance(alias, dict):
                        raise ValidationError("Ungültige Stammdaten-Zuordnung.")
                    if alias.get('kind') == 'tag':
                        continue
                    foreign, target = identifier(alias.get('foreign_id')), identifier(alias.get('target_id'))
                    if foreign in records_by_id or target not in records_by_id or records_by_id[target]['kind'] != alias.get('kind'):
                        raise ValidationError("Stammdaten-Zuordnung verweist nicht auf einen gültigen Eintrag.")
                    validated_aliases.append({'foreign_id': foreign, 'kind': alias['kind'], 'target_id': target})
                images = {}
                asset_keys = {i for q in quests for i in q["images"]} | {r['icon'] for r in records if r.get('icon')}
                for key in asset_keys:
                    path = f"images/{key}"
                    if path not in seen:
                        raise ValidationError(f"Bild {key} fehlt in der ZIP.")
                    blob = zf.read(path)
                    if image_key(blob) != key:
                        raise ValidationError("Eine Bilddatei passt nicht zu ihrer Referenz.")
                    images[key] = blob
                progress, aliases, crown_records = {}, {}, []
                if "userdata.json" in seen:
                    private = json.loads(zf.read("userdata.json").decode("utf-8"))
                    if not isinstance(private, dict) or private.get("format") != "mh-wilds-userdata" or private.get("version") != 1:
                        raise ValidationError("Ungültiges privates Backup.")
                    if not isinstance(private.get("progress"), dict) or not isinstance(private.get("aliases", {}), dict):
                        raise ValidationError("Ungültige Nutzerdaten im Backup.")
                    progress = {identifier(k): validate_progress(v) for k, v in private["progress"].items()}
                    aliases = {identifier(k): identifier(v) for k, v in private.get("aliases", {}).items()}
                    crown_records = validate_crown_backup(private.get('crowns', []))
                    for monster in crown_records:
                        if monster['icon']:
                            key = monster['icon']
                            blob = zf.read(f'images/{key}')
                            if image_key(blob) != key:
                                raise ValidationError('Ein Monsterbild passt nicht zur Referenz.')
                            images[key] = blob
                parsed = {"quests": quests, "images": images, "progress": progress, "aliases": aliases, "catalogs": records, "catalog_id_aliases": validated_aliases, "source": "Privates Backup" if "userdata.json" in seen else "Questliste", "warnings": []}
                parsed['crowns'] = crown_records
            ids = [q["id"] for q in parsed["quests"]]
            if len(ids) > 1000 or len(ids) != len(set(ids)):
                raise ValidationError("Die Questliste enthält zu viele Quests oder doppelte IDs.")
            return parsed
    except ValidationError:
        raise
    except (zipfile.BadZipFile, UnicodeError, KeyError, ValueError, RuntimeError, NotImplementedError, OSError) as exc:
        raise ValidationError(f"ZIP konnte nicht gelesen werden: {exc}") from None


class Tracker:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.new_catalog = not (self.directory / "quests.sqlite").exists()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.images = self.directory / "images"
        self.images.mkdir(exist_ok=True)
        self.lock = threading.RLock()
        self.previews = {}
        with self.connect() as db:
            version = db.execute("PRAGMA main.user_version").fetchone()[0]
            if version > 3:
                raise ValidationError("Die Datenbank stammt aus einer neueren Tracker-Version.")
            if version in (1, 2):
                backup_dir = self.directory / f"migration-backup-v{version}"
                backup_dir.mkdir(exist_ok=True)
                if not (backup_dir / 'quests.sqlite').exists():
                    with closing(sqlite3.connect(backup_dir / 'quests.sqlite')) as backup:
                        db.backup(backup)
            db.execute("CREATE TABLE IF NOT EXISTS quests (id TEXT PRIMARY KEY, name TEXT NOT NULL, data TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS personal.progress (quest_id TEXT PRIMARY KEY, first_clear INTEGER NOT NULL, all_rewards INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS personal.aliases (foreign_id TEXT PRIMARY KEY, quest_id TEXT NOT NULL)")
            catalogs.create_schema(db)
            if version < 2:
                catalogs.import_records(db, catalogs.defaults())
                seed_monsters = ROOT / 'seed' / 'monsters.json'
                if seed_monsters.exists():
                    records = json.loads(seed_monsters.read_text(encoding='utf-8'))
                    for record in records:
                        if record.get('icon'):
                            self.save_image((ROOT / 'seed' / 'icons' / record['icon']).read_bytes())
                    catalogs.import_records(db, records)
                for qid, raw in db.execute('SELECT id,data FROM quests').fetchall():
                    q = catalogs.resolve_quest(db, validate_quest(json.loads(raw)), True)
                    db.execute('UPDATE quests SET data=? WHERE id=?', (json.dumps(q, ensure_ascii=False), qid))
            if version < 3:
                for table in ('catalog_entries', 'catalog_id_aliases', 'catalog_name_aliases'):
                    db.execute(f"DELETE FROM {table} WHERE kind='tag'")
                catalogs.refresh_quests(db)
            db.execute("PRAGMA main.user_version = 3")
            db.execute("CREATE TABLE IF NOT EXISTS crown_monsters (id TEXT PRIMARY KEY, name TEXT NOT NULL, icon TEXT, source TEXT NOT NULL DEFAULT '')")
            db.execute("CREATE TABLE IF NOT EXISTS personal.crowns (monster_id TEXT PRIMARY KEY, small INTEGER NOT NULL DEFAULT 0, gold INTEGER NOT NULL DEFAULT 0, position INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS tracker_features (name TEXT PRIMARY KEY)")
            if not db.execute("SELECT 1 FROM tracker_features WHERE name='crowns'").fetchone():
                for position, monster in enumerate(json.loads((ROOT / 'seed/crowns.json').read_text(encoding='utf-8'))):
                    key = self.save_image((ROOT / 'seed/icons' / monster['icon']).read_bytes())
                    db.execute("INSERT INTO crown_monsters VALUES (?,?,?,?)", (monster['id'], monster['name'], key, monster['source']))
                    db.execute("INSERT OR IGNORE INTO personal.crowns (monster_id,position) VALUES (?,?)", (monster['id'], position))
                db.execute("INSERT INTO tracker_features VALUES ('crowns')")
            if db.execute('PRAGMA personal.user_version').fetchone()[0] != 1:
                db.execute("PRAGMA personal.user_version = 1")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.directory / "quests.sqlite", timeout=15)
        try:
            db.execute("ATTACH DATABASE ? AS personal", (str(self.directory / "userdata.sqlite"),))
            with db:
                yield db
        finally:
            db.close()

    def state(self):
        with self.lock, self.connect() as db:
            states = {r[0]: {"first_clear": bool(r[1]), "all_rewards": bool(r[2])} for r in db.execute("SELECT * FROM personal.progress")}
            quests = [json.loads(r[0]) for r in db.execute("SELECT data FROM quests ORDER BY rowid")]
            for q in quests:
                q["progress"] = states.get(q["id"], {"first_clear": False, "all_rewards": False})
            groups = catalogs.grouped(db)
            crowns = [dict(zip(('id', 'name', 'icon', 'source', 'small', 'gold'), row)) for row in db.execute(
                "SELECT m.id,m.name,m.icon,m.source,COALESCE(c.small,0),COALESCE(c.gold,0) FROM crown_monsters m LEFT JOIN personal.crowns c ON c.monster_id=m.id ORDER BY COALESCE(c.position,2147483647),m.rowid")]
            for monster in crowns:
                monster['small'], monster['gold'] = bool(monster['small']), bool(monster['gold'])
            return {"quests": quests, "crowns": crowns, "catalogs": groups, "reward_types": [r['name'] for r in groups['reward_type']],
                    "monster_types": [r['name'] for r in groups['state']], "ranks": [r['name'] for r in groups['rank']]}

    def save_crown_monster(self, raw, create=False):
        mid = str(uuid.uuid4()) if create else identifier(raw.get('id'))
        name = text_value(raw.get('name'), 'Monstername', 200, True)
        key = raw.get('icon')
        if key is not None and (not isinstance(key, str) or not re.fullmatch(r'[a-f0-9]{64}\.(png|jpg|gif|webp)', key) or not (self.images / key).is_file()):
            raise ValidationError('Ungültiges oder fehlendes Monsterbild.')
        with self.lock, self.connect() as db:
            if not create and not db.execute('SELECT 1 FROM crown_monsters WHERE id=?', (mid,)).fetchone():
                raise ValidationError('Monster wurde nicht gefunden.')
            if any(other != mid and normalized(value) == normalized(name) for other, value in db.execute('SELECT id,name FROM crown_monsters')):
                raise ValidationError('Dieses Monster ist bereits im Kronen-Tracker vorhanden.')
            if create:
                db.execute('INSERT INTO crown_monsters (id,name,icon) VALUES (?,?,?)', (mid, name, key))
                position = db.execute('SELECT COALESCE(MAX(position),-1)+1 FROM personal.crowns').fetchone()[0]
                db.execute('INSERT INTO personal.crowns (monster_id,position) VALUES (?,?)', (mid, position))
            else:
                db.execute('UPDATE crown_monsters SET name=?,icon=? WHERE id=?', (name, key, mid))
        return {'id': mid, 'name': name, 'icon': key}

    def set_crown_progress(self, mid, raw):
        mid = identifier(mid)
        if not isinstance(raw, dict) or any(not isinstance(raw.get(k), bool) for k in ('small', 'gold')):
            raise ValidationError('Ungültiger Kronenfortschritt.')
        with self.lock, self.connect() as db:
            if not db.execute('SELECT 1 FROM crown_monsters WHERE id=?', (mid,)).fetchone():
                raise ValidationError('Monster wurde nicht gefunden.')
            position = db.execute('SELECT COALESCE(MAX(position),-1)+1 FROM personal.crowns').fetchone()[0]
            db.execute('INSERT INTO personal.crowns VALUES (?,?,?,?) ON CONFLICT(monster_id) DO UPDATE SET small=excluded.small,gold=excluded.gold', (mid, raw['small'], raw['gold'], position))
        return {'small': raw['small'], 'gold': raw['gold']}

    def reorder_crowns(self, ids):
        if not isinstance(ids, list):
            raise ValidationError('Ungültige Monsterreihenfolge.')
        ids = [identifier(mid) for mid in ids]
        with self.lock, self.connect() as db:
            existing = {row[0] for row in db.execute('SELECT id FROM crown_monsters')}
            if len(ids) != len(existing) or set(ids) != existing:
                raise ValidationError('Die Reihenfolge muss jedes Monster genau einmal enthalten. Bitte neu laden.')
            for position, mid in enumerate(ids):
                db.execute('INSERT INTO personal.crowns (monster_id,position) VALUES (?,?) ON CONFLICT(monster_id) DO UPDATE SET position=excluded.position', (mid, position))
        return {'ok': True}

    def save_image(self, content):
        key = image_key(content)
        with self.lock:
            dest = self.images / key
            if not dest.exists():
                temporary = self.images / (key + ".tmp")
                try:
                    temporary.write_bytes(content)
                    os.replace(temporary, dest)
                finally:
                    temporary.unlink(missing_ok=True)
        return key

    def save_quest(self, raw, create=False):
        q = validate_quest(raw)
        with self.lock, self.connect() as db:
            q = catalogs.resolve_quest(db, q)
            exists = db.execute("SELECT 1 FROM quests WHERE id = ?", (q["id"],)).fetchone()
            if create == bool(exists):
                raise ValidationError("Quest-ID existiert bereits." if create else "Quest wurde nicht gefunden.")
            if any(not (self.images / key).is_file() for key in q["images"]):
                raise ValidationError("Ein angehängtes Bild fehlt.")
            db.execute("INSERT INTO quests VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, data=excluded.data", (q["id"], q["name"], json.dumps(q, ensure_ascii=False)))
        return q

    def set_progress(self, qid, raw):
        qid, progress = identifier(qid), validate_progress(raw)
        with self.lock, self.connect() as db:
            if not db.execute("SELECT 1 FROM quests WHERE id=?", (qid,)).fetchone():
                raise ValidationError("Quest wurde nicht gefunden.")
            db.execute("INSERT OR REPLACE INTO personal.progress VALUES (?,?,?)", (qid, progress["first_clear"], progress["all_rewards"]))
        return progress

    def delete_quest(self, qid):
        qid = identifier(qid)
        with self.lock, self.connect() as db:
            db.execute("DELETE FROM quests WHERE id=?", (qid,))
            db.execute("DELETE FROM personal.progress WHERE quest_id=?", (qid,))
            db.execute("DELETE FROM personal.aliases WHERE quest_id=? OR foreign_id=?", (qid, qid))

    def export(self, private=False):
        with self.lock, self.connect() as db:
            quests = [validate_quest(json.loads(r[0])) for r in db.execute("SELECT data FROM quests ORDER BY rowid")]
            records = catalogs.all_records(db)
            id_aliases = [{'foreign_id': row[0], 'kind': row[1], 'target_id': row[2]} for row in db.execute('SELECT * FROM catalog_id_aliases')]
            buffer = io.BytesIO()
            crown_records = self.state()['crowns'] if private else []
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("catalog.json", json.dumps({"format": "mh-wilds-quests", "version": 2, "quests": quests, "catalogs": records, "catalog_id_aliases": id_aliases}, ensure_ascii=False, indent=2))
                for key in sorted({i for q in quests for i in q["images"]} | {r['icon'] for r in records if r.get('icon')} | {m['icon'] for m in crown_records if m.get('icon')}):
                    path = self.images / key
                    if not path.is_file():
                        raise ValidationError("Ein Bild fehlt. Export wurde abgebrochen.")
                    zf.write(path, f"images/{key}")
                if private:
                    progress = {r[0]: {"first_clear": bool(r[1]), "all_rewards": bool(r[2])} for r in db.execute("SELECT * FROM personal.progress")}
                    aliases = dict(db.execute("SELECT foreign_id, quest_id FROM personal.aliases"))
                    zf.writestr("userdata.json", json.dumps({"format": "mh-wilds-userdata", "version": 1, "progress": progress, "aliases": aliases, "crowns": crown_records}, ensure_ascii=False, indent=2))
            return buffer.getvalue()

    def preview(self, content):
        package = parse_package(content)
        with self.lock, self.connect() as db:
            existing = {q["id"]: q for q in self.state()["quests"]}
            aliases = dict(db.execute("SELECT foreign_id, quest_id FROM personal.aliases"))
            rows = []
            for q in package["quests"]:
                exact_id = q["id"] if q["id"] in existing else aliases.get(q["id"])
                exact = existing.get(exact_id)
                candidates = []
                if exact:
                    candidates = [exact]
                else:
                    targets = sorted(normalized(t["monster"]) for t in q["targets"])
                    scored = []
                    for local in existing.values():
                        similarity = difflib.SequenceMatcher(None, normalized(q["name"]), normalized(local["name"])).ratio()
                        same_targets = targets == sorted(normalized(t["monster"]) for t in local["targets"])
                        if similarity == 1 or (similarity >= .5 and same_targets) or similarity >= .8:
                            scored.append((similarity, local))
                    candidates = [item[1] for item in sorted(scored, key=lambda x: x[0], reverse=True)[:3]]
                rows.append({"quest": q, "exact": bool(exact), "candidates": candidates,
                             "default": f"update:{exact_id}" if exact else "skip" if candidates else "add"})
            now = time.monotonic()
            self.previews = {k: v for k, v in self.previews.items() if now - v[0] < 900}
            if len(self.previews) >= 5:
                self.previews.pop(next(iter(self.previews)))
            token = secrets.token_urlsafe(24)
            self.previews[token] = (now, package, rows)
            return {"token": token, "source": package["source"], "has_progress": bool(package["progress"] or package.get('crowns')), "crown_count": len(package.get('crowns', [])), "catalog_count": len(package['catalogs']), "rows": rows, "warnings": package["warnings"]}

    def commit(self, token, choices, restore_progress=False, update_catalogs=False):
        with self.lock:
            pending = self.previews.get(token)
            if pending is None or time.monotonic() - pending[0] > 900:
                raise ValidationError("Importvorschau abgelaufen. Bitte ZIP erneut auswählen.")
            _, package, rows = pending
            if not isinstance(choices, dict) or set(choices) != {r["quest"]["id"] for r in rows}:
                raise ValidationError("Für jede importierte Quest muss eine Entscheidung vorliegen.")
            counts = {"added": 0, "updated": 0, "skipped": 0}
            remap, operations, destinations = {}, [], set()
            with self.connect() as db:
                existing = {r[0] for r in db.execute("SELECT id FROM quests")}
                for row in rows:
                    q = row["quest"].copy()
                    foreign_id, choice = q["id"], choices[q["id"]]
                    if choice == "skip":
                        counts["skipped"] += 1
                        continue
                    if choice == "add":
                        # A deliberate separate copy of a known ID receives a new identity.
                        local_id = str(uuid.uuid4()) if foreign_id in existing or row["exact"] else foreign_id
                        counts["added"] += 1
                    elif isinstance(choice, str) and choice.startswith("update:"):
                        local_id = identifier(choice[7:])
                        if local_id not in existing:
                            raise ValidationError("Eine zugeordnete Quest existiert nicht mehr.")
                        counts["updated"] += 1
                    else:
                        raise ValidationError("Ungültige Importentscheidung.")
                    if local_id in destinations:
                        raise ValidationError("Mehrere Einträge wurden derselben lokalen Quest zugeordnet. Bitte Zuordnung ändern.")
                    destinations.add(local_id)
                    remap[foreign_id] = local_id
                    q["id"] = local_id
                    operations.append((foreign_id, q, choice))
                # Images are content-addressed; writing them first avoids DB references to absent files.
                crown_icons = {m['icon'] for m in package.get('crowns', []) if m.get('icon')} if restore_progress else set()
                for key in {i for _, q, _ in operations for i in q["images"]} | {r['icon'] for r in package['catalogs'] if r.get('icon')} | crown_icons:
                    self.save_image(package["images"][key])
                catalogs.import_records(db, package['catalogs'], update_catalogs)
                for alias in package['catalog_id_aliases']:
                    target = catalogs.find(db, alias['kind'], qid=alias['target_id'])
                    known = catalogs.find(db, alias['kind'], qid=alias['foreign_id'])
                    if target and known and target['id'] != known['id'] and update_catalogs:
                        catalogs.merge(db, known['id'], target['id'])
                    if target and not known:
                        db.execute('INSERT OR REPLACE INTO catalog_id_aliases VALUES (?,?,?)', (alias['foreign_id'], alias['kind'], target['id']))
                catalogs.refresh_quests(db)
                for foreign_id, q, choice in operations:
                    q = catalogs.resolve_quest(db, q, True)
                    db.execute("INSERT INTO quests VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,data=excluded.data", (q["id"], q["name"], json.dumps(q, ensure_ascii=False)))
                    if choice.startswith("update:") and foreign_id != q["id"]:
                        db.execute("INSERT OR REPLACE INTO personal.aliases VALUES (?,?)", (foreign_id, q["id"]))
                    if restore_progress and foreign_id in package["progress"]:
                        p = package["progress"][foreign_id]
                        db.execute("INSERT OR REPLACE INTO personal.progress VALUES (?,?,?)", (q["id"], p["first_clear"], p["all_rewards"]))
                if restore_progress:
                    crown_records = package.get('crowns', [])
                    # Keep monsters absent from a backup after its restored order.
                    offset = len(crown_records)
                    db.execute('UPDATE personal.crowns SET position=position+?', (offset,))
                    for position, monster in enumerate(crown_records):
                        db.execute('INSERT INTO crown_monsters VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,icon=excluded.icon,source=excluded.source', (monster['id'], monster['name'], monster['icon'], monster['source']))
                        db.execute('INSERT OR REPLACE INTO personal.crowns VALUES (?,?,?,?)', (monster['id'], monster['small'], monster['gold'], position))
                    for foreign_id, target in package["aliases"].items():
                        local_id = remap.get(target)
                        if local_id and foreign_id not in existing and foreign_id not in destinations:
                            db.execute("INSERT OR REPLACE INTO personal.aliases VALUES (?,?)", (foreign_id, local_id))
            del self.previews[token]
            return counts

    def save_catalog(self, raw, create=False):
        raw = dict(raw)
        if create:
            raw['id'] = str(uuid.uuid4())
        record = catalogs.validate_record(raw)
        with self.lock, self.connect() as db:
            current = catalogs.find(db, record['kind'], qid=record['id'])
            if not create and not current:
                raise ValidationError('Stammdateneintrag wurde nicht gefunden.')
            if current:
                if current.get('is_none') and record['name'] != current['name']:
                    raise ValidationError('Normal/ohne Zustand bleibt als neutraler Zustand erhalten.')
                record['aliases'] = list(dict.fromkeys([*current['aliases'], *record['aliases'], *([current['name']] if catalogs.norm(current['name']) != catalogs.norm(record['name']) else [])]))
            if record.get('icon') and not (self.images / record['icon']).is_file():
                raise ValidationError('Das ausgewählte Monster-Icon fehlt.')
            result = catalogs.write_record(db, record)
            catalogs.refresh_quests(db)
            return result

    def merge_catalog(self, source_id, target_id):
        with self.lock, self.connect() as db:
            catalogs.merge(db, identifier(source_id), identifier(target_id))
        return {'ok': True}


class BrowserLifetime:
    """Track open streams rather than timers in throttled background tabs."""

    def __init__(self, grace=8, startup_timeout=120, clock=time.monotonic):
        self.lock = threading.Lock()
        self.clock = clock
        self.grace = grace
        self.startup_timeout = startup_timeout
        self.started = clock()
        self.empty_since = None
        self.connections = 0

    def opened(self):
        with self.lock:
            self.connections += 1
            self.empty_since = None

    def closed(self):
        with self.lock:
            self.connections -= 1
            if not self.connections:
                self.empty_since = self.clock()

    def expired(self):
        with self.lock:
            if self.connections:
                return False
            if self.empty_since is None:
                return self.clock() - self.started >= self.startup_timeout
            return self.clock() - self.empty_since >= self.grace


def make_handler(tracker, csrf, lifetime=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            if args and str(args[1] if len(args) > 1 else "").startswith("5"):
                super().log_message(format, *args)

        def send(self, status, content, content_type="application/json; charset=utf-8", filename=None):
            if not isinstance(content, bytes):
                content = json.dumps(content, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(content)

        def valid_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

        def route(self, mutation=False):
            if not self.valid_host():
                self.send(403, {"error": "Nur lokale Zugriffe sind erlaubt."})
                return
            if mutation and self.headers.get("X-Tracker-Token") != csrf:
                self.send(403, {"error": "Ungültiger Sitzungsschlüssel. Seite neu laden."})
                return
            try:
                self.dispatch(mutation)
            except ValidationError as exc:
                self.send(400, {"error": str(exc)})
            except (sqlite3.Error, OSError) as exc:
                print(f"Speicherfehler: {exc}")
                self.send(500, {"error": "Daten konnten nicht gespeichert oder gelesen werden. Schreibrechte und freien Speicher prüfen."})
            except (ValueError, TypeError, KeyError) as exc:
                self.send(400, {"error": f"Ungültige Anfrage: {exc}"})

        def read_body(self):
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY:
                raise ValidationError("Leere Anfrage oder Datei zu groß (maximal 120 MB).")
            return self.rfile.read(size)

        def dispatch(self, mutation):
            path = urlsplit(self.path).path
            if not mutation:
                if path == "/api/session":
                    if parse_qs(urlsplit(self.path).query).get('token') != [csrf]:
                        self.send(403, {"error": "Ungültiger Sitzungsschlüssel."})
                        return
                    self.browser_session()
                elif path == "/api/health":
                    self.send(200, {"ok": True, "token": csrf})
                elif path == "/api/state":
                    self.send(200, tracker.state())
                elif path in ("/api/export/catalog", "/api/export/backup"):
                    private = path.endswith("backup")
                    self.send(200, tracker.export(private), "application/zip", "wilds-privates-backup.zip" if private else "wilds-questliste.zip")
                elif path in ("/", "/index.html"):
                    self.send(200, (ROOT / "web" / "index.html").read_text(encoding="utf-8").replace("__TRACKER_TOKEN__", csrf).encode("utf-8"), "text/html; charset=utf-8")
                elif path in ("/app.js", "/style.css", "/favicon.svg", "/favicon.ico", "/logo.png", "/crown-small.png", "/crown-gold.png"):
                    file = ROOT / "web" / path[1:]
                    self.send(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")
                elif re.fullmatch(r"/images/[a-f0-9]{64}\.(png|jpg|gif|webp)", path):
                    file = tracker.images / path.split("/")[-1]
                    if not file.is_file():
                        self.send(404, {"error": "Bild nicht gefunden."})
                    else:
                        self.send(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")
                else:
                    self.send(404, {"error": "Nicht gefunden."})
                return
            body = self.read_body()
            if path == "/api/import/preview":
                self.send(200, tracker.preview(body))
                return
            raw = json.loads(body)
            if not isinstance(raw, dict):
                raise ValidationError("Eine JSON-Anfrage wird erwartet.")
            if path == "/api/quest/create":
                raw["id"] = str(uuid.uuid4())
                self.send(200, tracker.save_quest(raw, True))
            elif path == "/api/quest/save":
                self.send(200, tracker.save_quest(raw))
            elif path == "/api/quest/delete":
                tracker.delete_quest(raw.get("id"))
                self.send(200, {"ok": True})
            elif path == "/api/progress":
                self.send(200, tracker.set_progress(raw.get("id"), raw.get("progress")))
            elif path in ('/api/crowns/create', '/api/crowns/save'):
                self.send(200, tracker.save_crown_monster(raw, path.endswith('create')))
            elif path == '/api/crowns/progress':
                self.send(200, tracker.set_crown_progress(raw.get('id'), raw.get('progress')))
            elif path == '/api/crowns/order':
                self.send(200, tracker.reorder_crowns(raw.get('ids')))
            elif path in ("/api/catalog/create", "/api/catalog/save"):
                self.send(200, tracker.save_catalog(raw, path.endswith('create')))
            elif path == "/api/catalog/merge":
                self.send(200, tracker.merge_catalog(raw.get('source_id'), raw.get('target_id')))
            elif path == "/api/image":
                data = raw.get("data")
                if not isinstance(data, str) or len(data) > MAX_IMAGE * 1.4:
                    raise ValidationError("Ungültiges Bild oder Bild größer als 20 MB.")
                try:
                    blob = base64.b64decode(data, validate=True)
                except ValueError:
                    raise ValidationError("Ungültige Bilddaten.") from None
                self.send(200, {"key": tracker.save_image(blob)})
            elif path == "/api/import/commit":
                restore = raw.get("restore_progress", False)
                update_catalogs = raw.get('update_catalogs', False)
                if not isinstance(restore, bool) or not isinstance(update_catalogs, bool):
                    raise ValidationError("Ungültige Backup-Option.")
                self.send(200, tracker.commit(raw.get("token"), raw.get("choices"), restore, update_catalogs))
            else:
                self.send(404, {"error": "Nicht gefunden."})

        def browser_session(self):
            self.connection.settimeout(5)
            stop = getattr(self.server, 'browser_stop', threading.Event())
            if lifetime:
                lifetime.opened()
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                while not stop.is_set():
                    self.wfile.write(b': connected\n\n')
                    self.wfile.flush()
                    stop.wait(1)
            except OSError:
                pass  # Tab closed, navigated away, or browser exited.
            finally:
                if lifetime:
                    lifetime.closed()

        def do_GET(self):
            self.route()

        def do_POST(self):
            self.route(True)

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path, default=default_data_directory())
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--auto-stop", action="store_true", help="Nach Schließen des letzten Browser-Tabs automatisch beenden")
    parser.add_argument("--import-notion", type=Path, help="Einmaligen Notion-Erstimport ausführen und beenden")
    args = parser.parse_args()
    tracker = Tracker(args.data_dir)
    if args.import_notion:
        preview = tracker.preview(args.import_notion.read_bytes())
        if any(r["candidates"] and not r["exact"] for r in preview["rows"]):
            parser.error("Mögliche Duplikate gefunden. Bitte über die Oberfläche importieren.")
        counts = tracker.commit(preview["token"], {r["quest"]["id"]: r["default"] for r in preview["rows"]}, True)
        print(json.dumps(counts))
        for warning in preview["warnings"]:
            print(warning)
        return
    seed = ROOT / "seed" / "catalog.zip"
    if tracker.new_catalog and seed.exists():
        preview = tracker.preview(seed.read_bytes())
        tracker.commit(preview["token"], {r["quest"]["id"]: "add" for r in preview["rows"]})
    token = secrets.token_urlsafe(32)
    auto_stop = args.auto_stop or (getattr(sys, 'frozen', False) and not args.no_browser)
    lifetime = BrowserLifetime() if auto_stop else None
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(tracker, token, lifetime))
    except OSError:
        print(f"Port {args.port} ist belegt. Läuft der Tracker bereits? Alternativ: app.py --port 8766")
        return 1
    server.browser_stop = threading.Event()
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Wilds Quest Tracker: {url}\nDaten: {tracker.directory.resolve()}\nZum Beenden Strg+C drücken.", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    def watch_browser():
        while not server.browser_stop.wait(.5):
            if lifetime.expired():
                server.shutdown()
                return
    if lifetime:
        threading.Thread(target=watch_browser, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTracker beendet.")
    finally:
        server.browser_stop.set()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
