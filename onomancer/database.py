import base64
import functools
import random
import sqlite3
import sys
from urllib.parse import quote
import uuid

from imagekitio import ImageKit

DB_NAME = 'data/onomancer.db'
VOTE_THRESHOLD = -4
LEADER_THRESHOLD = -2


try:
    with open('data/imagekit.key', 'r') as f:
        imagekit_key = f.read()

    imagekit = ImageKit(
        private_key=imagekit_key,
        public_key='public_sb9Ym97kLySuXDx8WAm0OFVvmWg=',
        url_endpoint='https://ik.imagekit.io/4waizx9and',
    )
except Exception as e:
    imagekit = None
    print(e)

def connect():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def bootstrap():
    conn = connect()
    with conn:
        try:
            conn.execute('CREATE TABLE names (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)')
            conn.execute('CREATE UNIQUE INDEX idx_names_name ON names (name)')
            conn.execute('ALTER TABLE names ADD COLUMN upvotes INTEGER DEFAULT 0')
            conn.execute('ALTER TABLE names ADD COLUMN downvotes INTEGER DEFAULT 0')
            conn.execute('ALTER TABLE names ADD COLUMN naughty INTEGER DEFAULT 0')
            conn.execute('ALTER TABLE names ADD COLUMN flag TEXT')
            conn.execute('ALTER TABLE names ADD COLUMN first_votes INTEGER DEFAULT 0')
            conn.execute('ALTER TABLE names ADD COLUMN second_votes INTEGER DEFAULT 0')
            conn.execute('ALTER TABLE names ADD COLUMN guid TEXT')
            conn.execute('CREATE UNIQUE INDEX idx_names_guid ON names (guid)')
        except Exception:
            pass

        try:
            conn.execute('CREATE TABLE leaders (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, votes INTEGER)')
            conn.execute('CREATE INDEX idx_leaders_votes ON leaders (votes)')
            conn.execute('CREATE UNIQUE INDEX idx_leaders_name ON leaders (name)')
            conn.execute('ALTER TABLE leaders ADD COLUMN naughty INTEGER DEFAULT 0')
            conn.execute('ALTER TABLE leaders ADD COLUMN flag TEXT')
            conn.execute('ALTER TABLE leaders ADD COLUMN guid TEXT')
            conn.execute('CREATE UNIQUE INDEX idx_leaders_guid ON names (guid)')
        except Exception:
            pass


def clear():
    conn = connect()
    with conn:
        try:
            conn.execute('DROP TABLE names')
        except Exception:
            pass
        try:
            conn.execute('DROP TABLE leaders')
        except Exception:
            pass


def migrate():
    conn = connect()
    with conn:
        conn.execute('ALTER TABLE names ADD COLUMN guid TEXT')
        conn.execute('CREATE UNIQUE INDEX idx_names_guid ON names (guid)')
        conn.execute('ALTER TABLE leaders ADD COLUMN guid TEXT')
        conn.execute('CREATE UNIQUE INDEX idx_leaders_guid ON names (guid)')


def add_name(name):
    name = name.replace(' ', u"\u00A0")  # replace with nonbreaking space
    conn = connect()
    with conn:
        conn.execute('INSERT INTO names (name, upvotes, downvotes, naughty, guid) VALUES (?, 0, 0, 1, ?) ON CONFLICT (name) DO UPDATE SET upvotes = upvotes', (name, str(uuid.uuid4())))
    return name


def upvote_name(name, thumbs=1, hit_eggs=True):
    conn = connect()
    with conn:
        eggs = [e.replace(' ', u'\u00A0') for e in name.split(' ', 1)]
        name = ' '.join(eggs)


        existing = conn.execute('SELECT * FROM leaders WHERE name = ?', (name,)).fetchone()
        naughty = 0
        if existing:
            if existing['naughty'] == -1:
                # rejected, throw away everything
                return
            if existing['naughty'] == 1:
                # has been validated
                naughty = 1
        else:
            # doesn't exist, do insertions
            for egg in eggs:
                n = conn.execute('SELECT * FROM names WHERE name = ?', (egg,)).fetchone()
                if not n:
                    conn.execute('INSERT INTO names (name, upvotes, downvotes, naughty, guid) VALUES (?, 0, 0, 1, ?)', (egg, str(uuid.uuid4())))
                if not n or n['naughty'] != 0:
                    naughty = 1

        if hit_eggs:
            for egg in eggs:
                if thumbs > 0:
                    conn.execute(
                        'UPDATE names SET upvotes = upvotes + ? WHERE name = ?',
                        (thumbs, egg))
                elif thumbs < 0:
                    conn.execute(
                        'UPDATE names SET downvotes = downvotes + ? WHERE name = ?',
                        (thumbs, egg))

        mult = 1
        if thumbs < 0 and check_egg_threshold(name):
            mult = 2

        conn.execute('INSERT INTO leaders (name, votes, naughty, guid) VALUES (?, ?, ?, ?) ON CONFLICT (name) DO UPDATE SET votes = votes + ?', (name, thumbs, naughty, str(uuid.uuid4()), thumbs * mult))


def flip_leader(name):
    """Flip leaderboard name turnwise"""
    with connect() as c:
        me = c.execute('SELECT * FROM leaders WHERE name=?', (name,)).fetchone()
        flipped = ' '.join(name.split(' ')[::-1])
        sibling = c.execute('SELECT * FROM leaders WHERE name = ?', (flipped,)).fetchone()
        if not sibling:
            c.execute('INSERT INTO leaders (name, votes, naughty, guid) VALUES (?, 0, 0, ?)', (flipped, str(uuid.uuid4())))
            sibling_votes = 0
        else:
            sibling_votes = sibling['votes']
        c.execute('UPDATE leaders SET votes=? WHERE name=?', (me['votes'], flipped))
        c.execute('UPDATE leaders SET votes=? WHERE name=?', (sibling_votes, name))


def get_leaders(top=20):
    conn = connect()
    with conn:
        rows = conn.execute(f'SELECT * FROM leaders WHERE naughty = 0 AND votes > {LEADER_THRESHOLD} ORDER BY votes DESC, RANDOM() LIMIT ?', (top,))
        return [dict(row) for row in rows]


def get_random_name():
    conn = connect()
    with conn:
        if random.random() > .3:
            order = 'RANDOM()'
            if random.random() < .25:
                rows = conn.execute(
                    'SELECT * FROM names WHERE naughty=0 AND (downvotes>=? OR upvotes+downvotes>=-2) ORDER BY upvotes-downvotes, RANDOM() LIMIT 500',
                    (VOTE_THRESHOLD,),
                ).fetchall()
                rows.extend(conn.execute(
                    'SELECT * FROM names WHERE naughty=0 AND (downvotes>=? OR upvotes+downvotes>=-2) ORDER BY RANDOM() LIMIT 100',
                    (VOTE_THRESHOLD,),
                ).fetchall())
                rows = sorted(rows, key=lambda _: random.random())
            else:
                rows = conn.execute(
                    f'SELECT * FROM names WHERE naughty = 0 AND (downvotes > {VOTE_THRESHOLD} OR upvotes+downvotes>=-2) ORDER BY RANDOM() LIMIT 2').fetchall()

            # choose which goes first and second
            # roll die between whether combined firsts or seconds the chooser
            # lol what is this mess
            total_first_votes = rows[0]['first_votes'] + rows[1]['second_votes'] + 1
            total_second_votes = rows[0]['second_votes'] + rows[1]['second_votes'] + 1
            if random.random() * (total_first_votes + total_second_votes) < total_first_votes:
                if random.random() * total_first_votes < rows[0]['first_votes']:
                    name = f'{rows[0]["name"]} {rows[1]["name"]}'
                else:
                    name = f'{rows[1]["name"]} {rows[0]["name"]}'
            else:
                if random.random() * total_second_votes < rows[0]['second_votes']:
                    name = f'{rows[1]["name"]} {rows[0]["name"]}'
                else:
                    name = f'{rows[0]["name"]} {rows[1]["name"]}'

            votes = conn.execute(f'SELECT * FROM leaders WHERE name = ? AND votes <= {LEADER_THRESHOLD} LIMIT 1', (name,))
            if not votes.fetchone():
                return name

        # no good name gen, just pick something good from the leaderboard
        if random.random() < .05:
            # pull something from the top of the board
            try:
                rows = conn.execute(f'SELECT name FROM leaders WHERE votes > {LEADER_THRESHOLD} AND naughty = 0 ORDER BY votes DESC, RANDOM() LIMIT 1000 OFFSET 100').fetchall()
                return random.choice(rows)['name']
            except IndexError:
                pass
        if random.random() < .1:
            # pull something from the bottom of the board to differentiate it faster
            rows = conn.execute(f'SELECT name FROM leaders WHERE votes > {LEADER_THRESHOLD} AND naughty = 0 ORDER BY votes ASC, RANDOM() LIMIT 200').fetchall()
            return random.choice(rows)['name']

        name = conn.execute(f'SELECT name FROM leaders WHERE votes > {LEADER_THRESHOLD} AND naughty = 0 ORDER BY RANDOM() LIMIT 1').fetchone()['name']
        return name


def check_egg_threshold(fullname, threshold=VOTE_THRESHOLD):
    names = fullname.split(' ', 1)
    conn = connect()
    with conn:
        rows = conn.execute(f'SELECT * FROM names WHERE name IN ({",".join("?" * len(names))}) AND (downvotes < {threshold} AND upvotes+downvotes<-2)', names)
        if rows.fetchone():
            return True
    return False


def get_mod_list():
    conn = connect()
    with conn:
        return {
            'names': {
                r['id']: r for r in conn.execute('SELECT * FROM leaders WHERE naughty = 1')
            },
            'eggs': {
                r['id']: r for r in conn.execute('SELECT * FROM names WHERE naughty = 1')
            },
        }


def moderate(names=None, eggs=None):
    names = names or {}
    eggs = eggs or {}
    conn = connect()
    with conn:
        for id_, naughty in names.items():
            conn.execute('UPDATE leaders SET naughty = ? WHERE id = ?', (naughty, id_))
        for id_, naughty in eggs.items():
            conn.execute('UPDATE names SET naughty = ? WHERE id = ?', (naughty, id_))



def purge(name):
    if not name:
        return
    conn = connect()
    with conn:
        if isinstance(name, str):
            conn.execute('DELETE FROM names WHERE name = ?', (name,))
            conn.execute('DELETE FROM leaders WHERE name LIKE ?', (f'%{name}%',))
        else:
            conn.execute('DELETE FROM names WHERE id = ?', (name,))
            conn.execute('DELETE FROM leaders WHERE id = ?', (name,))


def lookup(name, only_good=False):
    conn = connect()
    with conn:
        egg_query = 'SELECT * FROM names WHERE name LIKE ?'
        name_query = 'SELECT * FROM leaders WHERE name LIKE ?'
        if only_good:
            egg_query += ' AND naughty = 0'
            name_query += ' AND naughty = 0'
        res = {
            'eggs': [
                dict(r) for r in conn.execute(egg_query, (f'%{name}%',))
            ],
            'names': [
                dict(r) for r in conn.execute(name_query, (f'%{name}%',))
            ],
        }
    return res


def mark_naughty(id_, is_leader=True, naughty=-1):
    with connect() as conn:
        tbl = 'leaders' if is_leader else 'names'
        conn.execute(f'UPDATE {tbl} SET naughty = ? WHERE id = ?', (naughty, id_))


def reset_egg(id_):
    with connect() as conn:
        conn.execute('UPDATE names SET upvotes=0, downvotes=0, first_votes=0, second_votes=0 WHERE id = ?', (id_, ))


def reset_leader(id_):
    with connect() as conn:
        conn.execute('UPDATE leaders SET votes=1 WHERE id=?', (id_,))



def admin_leaders():
    conn = connect()
    with conn:
        return {
            'naughty': [dict(r) for r in conn.execute('SELECT * FROM leaders WHERE naughty = -1')],
            'bad': [dict(r) for r in conn.execute(f'SELECT * FROM leaders WHERE votes < {LEADER_THRESHOLD}')],
        }


def delete_egg(id_):
    with connect() as conn:
        conn.execute('DELETE FROM names WHERE id=?', (id_, ))


def delete_leader(id_):
    with connect() as conn:
        conn.execute('DELETE FROM leaders WHERE id=?', (id_, ))


def admin_eggs():
    with connect() as conn:
        return {
            'naughty': [dict(r) for r in conn.execute('SELECT * FROM names WHERE naughty = -1')],
            'measured': [dict(r) for r in conn.execute(f'SELECT * FROM names WHERE downvotes <= -(upvotes * 2) AND downvotes <= {VOTE_THRESHOLD}')],
        }


def random_pool(count=100):
    """Regard random pool of 100 names"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    with conn:
        names = conn.execute('SELECT name FROM leaders WHERE votes > 0 AND naughty = 0 ORDER BY RANDOM() LIMIT ?', (count,))
        return [n['name'] for n in names]


def flag_name(name, reason):
    with connect() as conn:
        conn.execute('INSERT INTO leaders (name, votes, naughty, flag, guid) VALUES (?, 0, 1, ?, ?) ON CONFLICT (name) DO UPDATE SET flag=?, naughty=1', (name, reason, str(uuid.uuid4()), reason))


def flag_egg(name, reason):
    with connect() as conn:
        conn.execute('UPDATE names SET naughty=1,flag=? WHERE name=?', (reason, name))


def collect(friends=14, threshold=1):
    with connect() as conn:
        res = conn.execute('SELECT * FROM leaders WHERE naughty = 0 AND votes >= ? ORDER BY RANDOM() LIMIT ?', (threshold, friends))
        return [r['name'] for r in res]


def get_collection_ids(names):
    with connect() as conn:
        rows = conn.execute(f'SELECT * FROM leaders WHERE name IN ({",".join(["?"] * len(names))})', names)
        res = {r['name']: r['id'] for r in rows}
        for name in names:
            if name not in res:
                res[name] = None
        return res


def get_names_from_ids(ids):
    with connect() as conn:
        rows = conn.execute(f'SELECT * FROM leaders WHERE id IN ({",".join(["?"] * len(ids))})', ids)
        res = {r['id']: r['name'] for r in rows}
        return [res[id_] if id_ in res else '-' for id_ in ids]


@functools.lru_cache(1024)
def get_name_from_guid(guid):
    with connect() as c:
        return c.execute('SELECT name FROM leaders WHERE guid=?', (guid,)).fetchone()['name']


def dump_names():
    with connect() as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM names')]


def dump_leaders():
    with connect() as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM leaders')]


def get_names(threshold=0, limit=100, offset=0, rand=0):
    with connect() as c:
        order = 'RANDOM()' if rand else 'name'
        return [
            n['name'] for n in c.execute(
                f'SELECT * FROM leaders WHERE naughty=0 AND votes>=? ORDER BY {order} LIMIT ?,?',
                (threshold, offset, limit),
            )
        ]


def get_eggs(threshold=0, limit=100, offset=0, rand=0):
    with connect() as c:
        order = 'RANDOM()' if rand else 'name'
        return [
            n['name'] for n in c.execute(
                f'SELECT * FROM names WHERE naughty=0 AND upvotes+downvotes>=? ORDER BY {order} LIMIT ?,?',
                (threshold, offset, limit),
            )
        ]


def annotate_egg(egg, first=0, second=0):
    with connect() as c:
        c.execute('UPDATE names SET first_votes=first_votes+?, second_votes=second_votes+? WHERE name=?', (first, second, egg))


def get_annotate_examples(egg, limit=5, rand=0):
    order = 'RANDOM()' if rand else 'votes DESC'
    with connect() as c:
        as_first = c.execute(
            f'SELECT * FROM leaders WHERE name LIKE ? AND votes > ? AND naughty=0 ORDER BY {order} LIMIT ?',
            (f'{egg} %', LEADER_THRESHOLD, limit),
        ).fetchall()
        if len(as_first) < limit:
            rem = limit - len(as_first)
            as_first.extend([{'name': f'{egg} {r["name"]}'} for r in c.execute(
                'SELECT * FROM names WHERE naughty=0 AND (downvotes>=? OR downvotes+upvotes>=-2) ORDER BY RANDOM() LIMIT ?',
                (VOTE_THRESHOLD, rem),
            )])

        as_second = c.execute(
            f'SELECT * FROM leaders WHERE name LIKE ? AND votes > ? AND naughty=0 ORDER BY {order} LIMIT ?',
            (f'% {egg}', LEADER_THRESHOLD, limit),
        ).fetchall()
        if len(as_second) < limit:
            rem = limit - len(as_second)
            as_second.extend([{'name': f'{r["name"]} {egg}'} for r in c.execute(
                'SELECT * FROM names WHERE naughty=0 AND (downvotes>=? OR downvotes+upvotes>=-2) ORDER BY RANDOM() LIMIT ?',
                (VOTE_THRESHOLD, rem),
            )])

    return {
        'as_first': as_first,
        'as_second': as_second,
    }


@functools.lru_cache(1024)
def share_guid(name):
    with connect() as c:
        r = c.execute('SELECT guid FROM leaders WHERE name=?', (name,)).fetchone()
        if r:
            return r['guid']
        guid = str(uuid.uuid4())
        # TODO check naughtiness
        c.execute(
            'INSERT INTO leaders (name, votes, naughty, guid) VALUES (?, 0, ?, ?) ON CONFLICT (name) DO UPDATE SET votes=votes',
            (name, 0, guid))
        return guid


@functools.lru_cache(1024)
def get_image_url(name=None, guid=None):
    if not imagekit:
        raise Exception('Imagekit not initialized')
    if not name and not guid:
        raise ValueError()
    if not name:
        name = get_name_from_guid(guid)
    longest = max(*[len(n) for n in name.split(' ')])
    if longest > 20:
        font_size = 36
    elif longest > 10:
        font_size = 50
    else:
        font_size = 75
    img_url = imagekit.url({
        'path': '/onomancer/black_rectangle_90Zei2Nio.jpg',
        'transformation': [{
            'ote': quote(base64.b64encode(name.encode('utf8')).decode('ascii')),
            'overlay_text_font_family': 'Lora',
            'overlay_text_font_size': font_size,
            'overlay_text_color': 'FFFFFF',
            'otw': 450,
        }],
    })
    return img_url


@functools.lru_cache(1024)
def get_collection_image_url(*names):
    if not imagekit:
        raise Exception('Imagekit not initialized')
    transforms = []
    transforms.append({
        'overlay_text': 'Lineup',
        'overlay_text_typography': 'bold',
        'overlay_text_font_family': 'Lora',
        'overlay_text_font_size': 30,
        'overlay_text_color': 'FFFFFF',
        'overlay_y': 50,
        'overlay_x': 400,
    })
    for i, name in enumerate(names[:9]):
        transforms.append({
            'ote': quote(base64.b64encode(name[0].encode('utf8')).decode('ascii')),
            'overlay_text_font_family': 'Lora',
            'overlay_text_font_size': 21,
            'overlay_text_color': 'FFFFFF',
            'overlay_y': 90 + (i * 26),
            'overlay_x': 250,
        })
        transforms.append({
            'ote': quote(base64.b64encode((('•' * len(name[1])) + ('·' if name[2] else '')).encode('utf8')).decode('ascii')),
            'overlay_text_font_size': 40,
            'overlay_text_color': 'FFFFFF',
            'overlay_y': 75 + (i * 27),
            'overlay_x': 580,
        })

    transforms.append({
        'overlay_text': 'Rotation',
        'overlay_text_typography': 'bold',
        'overlay_text_font_family': 'Lora',
        'overlay_text_font_size': 30,
        'overlay_text_color': 'FFFFFF',
        'overlay_y': 350,
        'overlay_x': 400,
    })
    for i, name in enumerate(names[9:]):
        transforms.append({
            'ote': quote(base64.b64encode(name[0].encode('utf8')).decode('ascii')),
            'overlay_text_font_family': 'Lora',
            'overlay_text_font_size': 21,
            'overlay_text_color': 'FFFFFF',
            'overlay_y': 390 + (i * 26),
            'overlay_x': 250,
        })
        transforms.append({
            'ote': quote(base64.b64encode((('•' * len(name[1])) + ('·' if name[2] else '')).encode('utf8')).decode('ascii')),
            'overlay_text_font_size': 40,
            'overlay_text_color': 'FFFFFF',
            'overlay_y': 375 + (i * 27),
            'overlay_x': 580,
        })


    img_url = imagekit.url({
        'path': '/onomancer/black_rectangle_7xapQJdUh.jpg',
        'transformation': transforms,
    })
    return img_url


def load():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    # TODO load from csv of existing blaseballers
    names = [
        'York',
        'Silk',
        'Fletcher',
        'Yamamoto',
        'Juice',
        'Collins',
        'Nagomi',
        'McDaniel',
        'Jacob',
        'Winner',
        'Spears',
        'Taylor',
        'Sutton',
        'Dreamy',
        'Alyssa',
        'Harrell',
        'Christian',
        'Combs',
        'Montogomery',
        'Bullock',
        'Stevenson',
        'Heat',
        'James',
        'Mora',
        'Gabriel',
        'Griffith',
        'Evelton',
        'McBlase',
        'Elijah',
        'Valenzuela',
        'Karato',
        'Bean',
        'Keanu',
        'Jacuzzi',
        'Nice',
        'Thank',
        'Ladd',
        'Basilio',
        'Fig',
        'Jessi',
        'Wise',
        'Fitzgerald',
        'Massey',
        'Sam',
        'Solis',
        'Hendricks',
        'Rangel',
        'Sebastian',
        'Sunshine',
        'Thomas',
        'England',
        'Test\xa0test',
        'The\xa0Hedgehog',
        'J.\xa0Reily',
        'de\xa0Vito',
    ]
    with conn:
        for name in names:
            try:
                conn.execute('INSERT INTO names (name, guid) VALUES (?, ?)', (name, str(uuid.uuid4())))
            except Exception:
                pass


def backfill_guids():
    with connect() as c:
        rows = c.execute('SELECT id FROM leaders WHERE guid IS NULL').fetchall()
        for row in rows:
            c.execute('UPDATE leaders SET guid=? WHERE id=?', (str(uuid.uuid4()), row['id'],))
        rows = c.execute('SELECT id FROM names WHERE guid IS NULL').fetchall()
        for row in rows:
            c.execute('UPDATE names SET guid=? WHERE id=?', (str(uuid.uuid4()), row['id'],))



if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'purge':
        purge(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'img':
        print(get_collection_image_url(*sys.argv[2].split(',')))
    else:
        for arg in sys.argv:
            if arg == 'clear':
                clear()
            if arg == 'bootstrap':
                bootstrap()
            if arg == 'load':
                load()
            if arg == 'migrate':
                migrate()
