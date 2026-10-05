"""Editable public catalog records with stable identities and rename/merge aliases."""
import json
import re
import unicodedata
import uuid

KINDS = ('monster', 'state', 'rank', 'reward_type', 'area', 'quest_type')
NAMESPACE = uuid.UUID('1dbb9727-3381-4b04-bda2-7a458e5ab748')
IMAGE_PATTERN = re.compile(r'[a-f0-9]{64}\.(png|jpg|gif|webp)')


def norm(value):
    key = ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if c.isalnum())
    return key or value.casefold().strip()


def stable_id(kind, name):
    return str(uuid.uuid5(NAMESPACE, kind + ':' + name))


def validate_record(raw):
    if not isinstance(raw, dict) or raw.get('kind') not in KINDS:
        raise ValueError('Ungültige Stammdaten-Kategorie.')
    try:
        qid = str(uuid.UUID(raw['id']))
    except (KeyError, ValueError, TypeError, AttributeError):
        raise ValueError('Ungültige Stammdaten-ID.') from None
    name = raw.get('name')
    if not isinstance(name, str) or not name.strip() or len(name) > 200 or not norm(name):
        raise ValueError('Ein Name mit höchstens 200 Zeichen wird benötigt.')
    record = {'id': qid, 'kind': raw['kind'], 'name': name.strip()}
    if raw['kind'] in ('reward_type', 'area'):
        color = raw.get('color')
        if color is not None and (not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color)):
            raise ValueError('Eine Kategoriefarbe im Format #RRGGBB wird benötigt.')
        record['color'] = color.upper() if color is not None else None
    if raw['kind'] == 'state':
        color = raw.get('color')
        is_none = qid == stable_id('state', 'Normal')
        if not is_none and (not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color)):
            raise ValueError('Eine Zustandsfarbe im Format #RRGGBB wird benötigt.')
        record.update(color=None if is_none else color.upper(), is_none=is_none)
    if raw['kind'] == 'monster':
        image = raw.get('icon')
        if image is not None and (not isinstance(image, str) or not IMAGE_PATTERN.fullmatch(image)):
            raise ValueError('Ungültige Monster-Icon-Referenz.')
        record['icon'] = image
        source = raw.get('source', '')
        if not isinstance(source, str) or len(source) > 1000:
            raise ValueError('Ungültige Quellenangabe.')
        record['source'] = source
    aliases = raw.get('aliases', [])
    if not isinstance(aliases, list) or len(aliases) > 100 or any(not isinstance(a, str) or len(a) > 200 or not norm(a) for a in aliases):
        raise ValueError('Ungültige alternative Namen.')
    record['aliases'] = list(dict.fromkeys(a.strip() for a in aliases if norm(a) != norm(name)))
    if raw['kind'] == 'rank':
        for field in ('stars_min', 'stars_max'):
            value = raw.get(field)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10000):
                raise ValueError('Ungültiger Sternbereich.')
            record[field] = value
        if record['stars_max'] is not None and (record['stars_min'] is None or record['stars_max'] < record['stars_min']):
            raise ValueError('Sternbereich: Maximum muss mindestens dem Minimum entsprechen.')
    return record


def defaults():
    records = []
    for name, color in [('Normal', None), ('Tempered', '#7837FC'), ('Archtempered', '#BE4233'), ('Frenzy', '#1C0037')]:
        records.append(validate_record({'id': stable_id('state', name), 'kind': 'state', 'name': name, 'color': color, 'aliases': ['Rasend'] if name == 'Frenzy' else []}))
    for name, low, high in [('Low-Rank', 1, 3), ('High-Rank', 4, 10), ('Master-Rank', 11, None)]:
        records.append(validate_record({'id': stable_id('rank', name), 'kind': 'rank', 'name': name, 'stars_min': low, 'stars_max': high}))
    for name in ['Ausrüstung', 'Materialien', 'Artian Material', 'Rüstkugeln', 'Dekorationen', 'Jägerrang XP', 'Kochzutaten']:
        records.append(validate_record({'id': stable_id('reward_type', name), 'kind': 'reward_type', 'name': name}))
    for name in ['Jagd', 'Fang', 'Sammeln']:
        records.append(validate_record({'id': stable_id('quest_type', name), 'kind': 'quest_type', 'name': name}))
    return records


def create_schema(db):
    db.execute('CREATE TABLE IF NOT EXISTS catalog_entries (id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, normalized TEXT NOT NULL, data TEXT NOT NULL, UNIQUE(kind, normalized))')
    db.execute('CREATE TABLE IF NOT EXISTS catalog_id_aliases (foreign_id TEXT PRIMARY KEY, kind TEXT NOT NULL, target_id TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS catalog_name_aliases (kind TEXT NOT NULL, normalized TEXT NOT NULL, target_id TEXT NOT NULL, PRIMARY KEY(kind, normalized))')


def all_records(db):
    return [json.loads(r[0]) for r in db.execute('SELECT data FROM catalog_entries ORDER BY rowid')]


def grouped(db):
    groups = {kind: [] for kind in KINDS}
    for record in all_records(db):
        groups[record['kind']].append(record)
    return groups


def find(db, kind, qid=None, name=None):
    if qid:
        row = db.execute('SELECT data FROM catalog_entries WHERE id=? AND kind=?', (qid, kind)).fetchone()
        if row:
            return json.loads(row[0])
        row = db.execute('SELECT target_id FROM catalog_id_aliases WHERE foreign_id=? AND kind=?', (qid, kind)).fetchone()
        if row:
            return find(db, kind, qid=row[0])
    if name:
        row = db.execute('SELECT data FROM catalog_entries WHERE kind=? AND normalized=?', (kind, norm(name))).fetchone()
        if row:
            return json.loads(row[0])
        row = db.execute('SELECT target_id FROM catalog_name_aliases WHERE kind=? AND normalized=?', (kind, norm(name))).fetchone()
        if row:
            return find(db, kind, qid=row[0])
    return None


def write_record(db, record):
    record = validate_record(record)
    existing_kind = db.execute('SELECT kind FROM catalog_entries WHERE id=?', (record['id'],)).fetchone()
    if existing_kind and existing_kind[0] != record['kind']:
        raise ValueError('Eine Stammdaten-ID darf ihre Kategorie nicht wechseln.')
    for alias in [record['name'], *record['aliases']]:
        existing = find(db, record['kind'], name=alias)
        if existing and existing['id'] != record['id']:
            raise ValueError(f'„{alias}“ existiert bereits. Bitte die Einträge zusammenführen.')
    db.execute('INSERT INTO catalog_entries VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET kind=excluded.kind,name=excluded.name,normalized=excluded.normalized,data=excluded.data',
               (record['id'], record['kind'], record['name'], norm(record['name']), json.dumps(record, ensure_ascii=False)))
    for alias in record['aliases']:
        db.execute('INSERT OR REPLACE INTO catalog_name_aliases VALUES (?,?,?)', (record['kind'], norm(alias), record['id']))
    return record


def import_records(db, records, update=False):
    for raw in records:
        record = validate_record(raw)
        local = find(db, record['kind'], qid=record['id']) or find(db, record['kind'], name=record['name'])
        if not local:
            local = next((match for alias in record['aliases'] if (match := find(db, record['kind'], name=alias))), None)
        if local:
            if record['id'] != local['id']:
                db.execute('INSERT OR REPLACE INTO catalog_id_aliases VALUES (?,?,?)', (record['id'], record['kind'], local['id']))
            # Aliases are matched locally too, but conflicting names do not overwrite another entry.
            aliases = list(dict.fromkeys([*local['aliases'], *record['aliases'], *([record['name']] if norm(record['name']) != norm(local['name']) else [])]))
            aliases = [a for a in aliases if not find(db, record['kind'], name=a) or find(db, record['kind'], name=a)['id'] == local['id']]
            result = {**(record if update else local), 'id': local['id'], 'aliases': aliases}
            if update and norm(local['name']) != norm(result['name']):
                result['aliases'].append(local['name'])
            if not update and record['kind'] == 'monster' and not local.get('icon'):
                result['icon'] = record.get('icon')
                result['source'] = record.get('source', '')
            write_record(db, result)
        else:
            write_record(db, record)


def resolve_quest(db, quest, allow_create=False):
    """Canonical IDs are authoritative; names are readable export/display snapshots."""
    quest = json.loads(json.dumps(quest))
    quest.pop('tags', None)
    quest.pop('tag_ids', None)

    def resolve(kind, name, qid=None):
        record = find(db, kind, qid=qid, name=name)
        if record is None:
            if not allow_create:
                raise ValueError(f'„{name}“ ist kein bekannter Eintrag. Bitte zuerst in den Stammdaten anlegen.')
            record = {'id': qid or str(uuid.uuid4()), 'kind': kind, 'name': name}
            if kind == 'state':
                record['color'] = '#8C9A76'
            record = write_record(db, record)
        return record

    rank = resolve('rank', quest['rank'], quest.get('rank_id'))
    quest['rank'], quest['rank_id'] = rank['name'], rank['id']
    for target in quest['targets']:
        monster = resolve('monster', target['monster'], target.get('monster_id'))
        status = resolve('state', target['type'], target.get('type_id'))
        target.update(monster=monster['name'], monster_id=monster['id'], type=status['name'], type_id=status['id'])
    for field, kind in [('reward_types', 'reward_type')]:
        names = quest.get(field, [])
        ids = quest.get('reward_type_ids', [])
        records = [resolve(kind, name, ids[i] if i < len(ids) else None) for i, name in enumerate(names)]
        records = list({record['id']: record for record in records}.values())
        quest[field] = [record['name'] for record in records]
        quest['reward_type_ids'] = [record['id'] for record in records]
    for field, kind in [('area', 'area'), ('quest_type', 'quest_type')]:
        if quest.get(field):
            record = resolve(kind, quest[field], quest.get(field + '_id'))
            quest[field], quest[field + '_id'] = record['name'], record['id']
        else:
            quest[field] = ''
            quest[field + '_id'] = None
    return quest


def refresh_quests(db):
    for qid, raw in db.execute('SELECT id,data FROM quests').fetchall():
        q = resolve_quest(db, json.loads(raw))
        db.execute('UPDATE quests SET data=? WHERE id=?', (json.dumps(q, ensure_ascii=False), qid))


def merge(db, source_id, target_id):
    source = next((r for r in all_records(db) if r['id'] == source_id), None)
    target = next((r for r in all_records(db) if r['id'] == target_id), None)
    if not source or not target or source['kind'] != target['kind'] or source_id == target_id:
        raise ValueError('Zwei unterschiedliche Einträge derselben Kategorie auswählen.')
    if source['kind'] == 'state' and (source.get('is_none') or target.get('is_none')):
        raise ValueError('Der Zustand Normal/ohne Zustand kann nicht zusammengeführt werden.')
    db.execute('DELETE FROM catalog_entries WHERE id=?', (source_id,))
    db.execute('UPDATE catalog_id_aliases SET target_id=? WHERE target_id=?', (target_id, source_id))
    db.execute('UPDATE catalog_name_aliases SET target_id=? WHERE target_id=?', (target_id, source_id))
    db.execute('INSERT OR REPLACE INTO catalog_id_aliases VALUES (?,?,?)', (source_id, source['kind'], target_id))
    target['aliases'] = list(dict.fromkeys([*target['aliases'], source['name'], *source['aliases']]))
    if source['kind'] == 'monster' and not target.get('icon'):
        target['icon'], target['source'] = source.get('icon'), source.get('source', '')
    write_record(db, target)
    refresh_quests(db)
