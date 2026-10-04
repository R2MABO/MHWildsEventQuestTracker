"""Local Monster Hunter Wilds quest tracker. Python 3.10+, standard library only."""
from __future__ import annotations

import argparse
import base64
import csv
from contextlib import contextmanager
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
import threading
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote
import uuid
import webbrowser
import zipfile

ROOT = Path(__file__).resolve().parent
REWARD_TYPES = ["Ausrüstung", "Materialien", "Artian Material", "Rüstkugeln", "Dekorationen", "Jägerrang XP", "Kochzutaten"]
MONSTER_TYPES = ["Normal", "Tempered", "Rasend", "Archtempered"]
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
        "rank": raw.get("rank"),
        "hr": integer(raw.get("hr"), "Jägerrang", maximum=99999, nullable=True),
        "stars": integer(raw.get("stars"), "Sterne", 1),
        "notes": text_value(raw.get("notes", ""), "Notizen", 4000),
    }
    if quest["rank"] not in RANKS:
        raise ValidationError("Ungültiger Rang.")
    targets = raw.get("targets")
    if not isinstance(targets, list) or not 1 <= len(targets) <= 30:
        raise ValidationError("Mindestens ein Jagdziel angeben (höchstens 30).")
    quest["targets"] = []
    for target in targets:
        if not isinstance(target, dict) or target.get("type") not in MONSTER_TYPES:
            raise ValidationError("Ungültige Monsterart.")
        quest["targets"].append({"monster": text_value(target.get("monster"), "Monster", 200, True),
                                 "type": target["type"], "count": integer(target.get("count", 1), "Monsteranzahl", 1, 100)})
    types = raw.get("reward_types", [])
    if not isinstance(types, list) or len(types) > len(REWARD_TYPES) or any(t not in REWARD_TYPES for t in types):
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
    # Whitelist intentionally excludes completion flags and other user data.
    return quest


def validate_progress(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get("first_clear"), bool) or not isinstance(raw.get("all_rewards"), bool):
        raise ValidationError("Ungültiger persönlicher Fortschritt.")
    return {"first_clear": raw["first_clear"] or raw["all_rewards"], "all_rewards": raw["all_rewards"]}


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
            for marker, mapped in [("[]", "Archtempered"), ("§", "Tempered"), ("$", "Tempered"), ("!", "Rasend")]:
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
    return {"quests": quests, "images": images, "progress": progress, "aliases": {}, "source": "Notion", "warnings": warnings}


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
                if not isinstance(raw, dict) or raw.get("format") != "mh-wilds-quests" or raw.get("version") != 1:
                    raise ValidationError("Unbekanntes Quest-ZIP-Format oder nicht unterstützte Version.")
                quests = raw.get("quests")
                if not isinstance(quests, list) or len(quests) > 1000:
                    raise ValidationError("Ungültige Questliste (maximal 1000 Quests).")
                quests = [validate_quest(q) for q in quests]
                images = {}
                for key in {i for q in quests for i in q["images"]}:
                    path = f"images/{key}"
                    if path not in seen:
                        raise ValidationError(f"Bild {key} fehlt in der ZIP.")
                    blob = zf.read(path)
                    if image_key(blob) != key:
                        raise ValidationError("Eine Bilddatei passt nicht zu ihrer Referenz.")
                    images[key] = blob
                progress, aliases = {}, {}
                if "userdata.json" in seen:
                    private = json.loads(zf.read("userdata.json").decode("utf-8"))
                    if not isinstance(private, dict) or private.get("format") != "mh-wilds-userdata" or private.get("version") != 1:
                        raise ValidationError("Ungültiges privates Backup.")
                    if not isinstance(private.get("progress"), dict) or not isinstance(private.get("aliases", {}), dict):
                        raise ValidationError("Ungültige Nutzerdaten im Backup.")
                    progress = {identifier(k): validate_progress(v) for k, v in private["progress"].items()}
                    aliases = {identifier(k): identifier(v) for k, v in private.get("aliases", {}).items()}
                parsed = {"quests": quests, "images": images, "progress": progress, "aliases": aliases, "source": "Privates Backup" if "userdata.json" in seen else "Questliste", "warnings": []}
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
            db.execute("CREATE TABLE IF NOT EXISTS quests (id TEXT PRIMARY KEY, name TEXT NOT NULL, data TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS personal.progress (quest_id TEXT PRIMARY KEY, first_clear INTEGER NOT NULL, all_rewards INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS personal.aliases (foreign_id TEXT PRIMARY KEY, quest_id TEXT NOT NULL)")
            db.execute("PRAGMA main.user_version = 1")
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
            return {"quests": quests, "reward_types": REWARD_TYPES, "monster_types": MONSTER_TYPES, "ranks": RANKS}

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
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("catalog.json", json.dumps({"format": "mh-wilds-quests", "version": 1, "quests": quests}, ensure_ascii=False, indent=2))
                for key in sorted({i for q in quests for i in q["images"]}):
                    path = self.images / key
                    if not path.is_file():
                        raise ValidationError("Ein Bild fehlt. Export wurde abgebrochen.")
                    zf.write(path, f"images/{key}")
                if private:
                    progress = {r[0]: {"first_clear": bool(r[1]), "all_rewards": bool(r[2])} for r in db.execute("SELECT * FROM personal.progress")}
                    aliases = dict(db.execute("SELECT foreign_id, quest_id FROM personal.aliases"))
                    zf.writestr("userdata.json", json.dumps({"format": "mh-wilds-userdata", "version": 1, "progress": progress, "aliases": aliases}, indent=2))
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
            return {"token": token, "source": package["source"], "has_progress": bool(package["progress"]), "rows": rows, "warnings": package["warnings"]}

    def commit(self, token, choices, restore_progress=False):
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
                for key in {i for _, q, _ in operations for i in q["images"]}:
                    self.save_image(package["images"][key])
                for foreign_id, q, choice in operations:
                    db.execute("INSERT INTO quests VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,data=excluded.data", (q["id"], q["name"], json.dumps(q, ensure_ascii=False)))
                    if choice.startswith("update:") and foreign_id != q["id"]:
                        db.execute("INSERT OR REPLACE INTO personal.aliases VALUES (?,?)", (foreign_id, q["id"]))
                    if restore_progress and foreign_id in package["progress"]:
                        p = package["progress"][foreign_id]
                        db.execute("INSERT OR REPLACE INTO personal.progress VALUES (?,?,?)", (q["id"], p["first_clear"], p["all_rewards"]))
                if restore_progress:
                    for foreign_id, target in package["aliases"].items():
                        local_id = remap.get(target)
                        if local_id and foreign_id not in existing and foreign_id not in destinations:
                            db.execute("INSERT OR REPLACE INTO personal.aliases VALUES (?,?)", (foreign_id, local_id))
            del self.previews[token]
            return counts


def make_handler(tracker, csrf):
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
                if path == "/api/state":
                    self.send(200, tracker.state())
                elif path in ("/api/export/catalog", "/api/export/backup"):
                    private = path.endswith("backup")
                    self.send(200, tracker.export(private), "application/zip", "wilds-privates-backup.zip" if private else "wilds-questliste.zip")
                elif path in ("/", "/index.html"):
                    self.send(200, (ROOT / "web" / "index.html").read_text(encoding="utf-8").replace("__TRACKER_TOKEN__", csrf).encode("utf-8"), "text/html; charset=utf-8")
                elif path in ("/app.js", "/style.css", "/favicon.svg"):
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
                if not isinstance(restore, bool):
                    raise ValidationError("Ungültige Backup-Option.")
                self.send(200, tracker.commit(raw.get("token"), raw.get("choices"), restore))
            else:
                self.send(404, {"error": "Nicht gefunden."})

        def do_GET(self):
            self.route()

        def do_POST(self):
            self.route(True)

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--no-browser", action="store_true")
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
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(tracker, token))
    except OSError:
        print(f"Port {args.port} ist belegt. Läuft der Tracker bereits? Alternativ: app.py --port 8766")
        return 1
    server.daemon_threads = True
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Wilds Quest Tracker: {url}\nDaten: {tracker.directory.resolve()}\nZum Beenden Strg+C drücken.", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTracker beendet.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
