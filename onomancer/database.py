import random
import sqlite3
import sys

DB_NAME = 'data/onomancer.db'
VOTE_THRESHOLD = -15
LEADER_THRESHOLD = -4


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
        except Exception:
            pass

        try:
            conn.execute('CREATE TABLE leaders (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, votes INTEGER)')
            conn.execute('CREATE INDEX idx_leaders_votes ON leaders (votes)')
            conn.execute('CREATE UNIQUE INDEX idx_leaders_name ON leaders (name)')
            conn.execute('ALTER TABLE leaders ADD COLUMN naughty INTEGER DEFAULT 0')
            conn.execute('ALTER TABLE leaders ADD COLUMN flag TEXT')
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
        conn.execute('ALTER TABLE leaders ADD COLUMN flag TEXT')


def add_name(name):
    name = name.replace(' ', u"\u00A0")  # replace with nonbreaking space
    conn = connect()
    with conn:
        conn.execute('INSERT INTO names (name, upvotes, downvotes, naughty) VALUES (?, 0, 0, 1) ON CONFLICT (name) DO UPDATE SET upvotes = upvotes', (name,))
    return name


def upvote_name(name, thumbs=1):
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
                    conn.execute('INSERT INTO names (name, upvotes, downvotes, naughty) VALUES (?, 0, 0, 1)', (egg,))
                if not n or n['naughty'] != 0:
                    naughty = 1

        for egg in eggs:
            if thumbs > 0:
                conn.execute('UPDATE names SET upvotes = upvotes + ? WHERE name = ?', (thumbs, egg))
            elif thumbs < 0:
                conn.execute('UPDATE names SET downvotes = downvotes + ? WHERE name = ?', (thumbs, egg))

        mult = 1
        if thumbs < 0 and check_egg_threshold(name):
            mult = 2

        conn.execute('INSERT INTO leaders (name, votes, naughty) VALUES (?, ?, ?) ON CONFLICT (name) DO UPDATE SET votes = votes + ?', (name, thumbs, naughty, thumbs * mult))


def flip_leader(name):
    """Flip leaderboard name turnwise"""
    with connect() as c:
        me = c.execute('SELECT * FROM leaders WHERE name=?', (name,)).fetchone()
        flipped = ' '.join(name.split(' ')[::-1])
        sibling = c.execute('SELECT * FROM leaders WHERE name = ?', (flipped,)).fetchone()
        if not sibling:
            c.execute('INSERT INTO leaders (name, votes, naughty) VALUES (?, 0, 0)', (flipped,))
            sibling_votes = 0
        else:
            sibling_votes = sibling['votes']
        c.execute('UPDATE leaders SET votes=? WHERE name=?', (me['votes'], flipped))
        c.execute('UPDATE leaders SET votes=? WHERE name=?', (sibling_votes, name))


def _verify_naughtiness(conn, name):
    is_good = conn.execute('SELECT * FROM leaders WHERE name = ? AND naughty != 0').fetchone()
    if is_good:
        return True
    eggs = name.split(' ')
    if len(eggs) == 2:
        # everything is fine
        pass


def get_leaders(top=20):
    conn = connect()
    with conn:
        rows = conn.execute(f'SELECT * FROM leaders WHERE naughty = 0 AND votes > {LEADER_THRESHOLD} ORDER BY votes DESC, RANDOM() LIMIT ?', (top,))
        return [
            {
                'name': row['name'],
                'votes': row['votes'],
            } for row in rows
        ]


def get_random_name():
    conn = connect()
    with conn:
        if random.random() > .2:
            rows = conn.execute(
                f'SELECT name FROM names WHERE naughty = 0 AND (downvotes > {VOTE_THRESHOLD} OR downvotes > -(upvotes * 3)) ORDER BY RANDOM() LIMIT 2')
            name = ' '.join([row['name'] for row in rows])
            votes = conn.execute(f'SELECT * FROM leaders WHERE name = ? AND votes <= {LEADER_THRESHOLD} LIMIT 1', (name,))
            if not votes.fetchone():
                return name
            # no good name gen, just pick something good from the leaderboard
        rows = conn.execute(f'SELECT name FROM leaders WHERE votes > {LEADER_THRESHOLD} AND naughty = 0 ORDER BY RANDOM() LIMIT 1')
        return rows.fetchone()['name']


def check_egg_threshold(fullname, threshold=VOTE_THRESHOLD):
    names = fullname.split(' ', 1)
    conn = connect()
    with conn:
        rows = conn.execute(f'SELECT * FROM names WHERE name IN ({",".join("?" * len(names))}) AND (downvotes < {threshold} AND downvotes < -(upvotes * 3))', names)
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
                r['id']: r['name'] for r in conn.execute('SELECT * FROM names WHERE naughty = 1')
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
        conn.execute('UPDATE names SET upvotes=0, downvotes=0 WHERE id = ?', (id_, ))


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
            'measured': [dict(r) for r in conn.execute(f'SELECT * FROM names WHERE downvotes <= -(upvotes * 3) AND downvotes <= {VOTE_THRESHOLD}')],
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
        conn.execute('INSERT INTO leaders (name, votes, naughty, flag) VALUES (?, 0, 1, ?) ON CONFLICT (name) DO UPDATE SET flag=?, naughty=1', (name, reason, reason))


def collect(friends=14, threshold=1):
    with connect() as conn:
        res = conn.execute('SELECT * FROM leaders WHERE naughty = 0 AND votes >= ? ORDER BY RANDOM () LIMIT ?', (threshold, friends))
        return [r['name'] for r in res]


def hash_dump():
    with connect() as c:
        return [
            [name['name'], hash(name['name'])] for name in
            c.execute('SELECT * FROM leaders WHERE naughty = 0')
        ]


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
        'Test test',
        'The Hedgehog',
        'J. Reily',
        'de Vito',
    ]
    with conn:
        for name in names:
            try:
                conn.execute('INSERT INTO names (name) VALUES (?)', (name,))
            except Exception:
                pass


def replace_whitespace(dry=True):
    with connect() as c:
        print('total rows')
        print(dict(c.execute('SELECT count(*) FROM names').fetchone()))
        print('rows found')
        names = c.execute('SELECT * FROM names WHERE name LIKE "% %"').fetchall()
        print(len(names))
        print('replacing')
        for name in names:
            print('UPDATE names SET name=? WHERE name=?', (name['name'].replace(' ', u'\u00A0'), name['name']))
            if dry:
                continue
            c.execute('UPDATE names SET name=? WHERE name=?', (name['name'].replace(' ', u'\u00A0'), name['name']))
        if not dry:
            c.execute('DELETE FROM leaders WHERE name LIKE "% % %"')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'purge':
        purge(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'whitespace':
        replace_whitespace(dry=sys.argv[2] != 'what')
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
