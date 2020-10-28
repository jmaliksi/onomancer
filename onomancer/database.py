import random
import sqlite3
import sys

DB_NAME = 'onomancer.db'


def bootstrap():
    conn = sqlite3.connect(DB_NAME)
    with conn:
        conn.execute('CREATE TABLE names (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)')
        conn.execute('CREATE UNIQUE INDEX idx_names_name ON names (name)')

        conn.execute('CREATE TABLE leaders (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, votes INTEGER)')
        conn.execute('CREATE INDEX idx_leaders_votes ON leaders (votes)')
        conn.execute('CREATE UNIQUE INDEX idx_leaders_name ON leaders (name)')


def clear():
    conn = sqlite3.connect(DB_NAME)
    with conn:
        try:
            conn.execute('DROP TABLE names')
        except Exception:
            pass
        try:
            conn.execute('DROP TABLE leaders')
        except Exception:
            pass


def add_name(name):
    conn = sqlite3.connect(DB_NAME)
    with conn:
        conn.execute("INSERT INTO names (name) VALUES (?)", (name,))
    return name


def upvote_name(name, thumbs=1):
    conn = sqlite3.connect(DB_NAME)
    with conn:
        conn.execute('INSERT INTO leaders (name, votes) VALUES (?, ?) ON CONFLICT (name) DO UPDATE SET votes = votes + ?', (name, thumbs, thumbs))


def get_leaders(top=20):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    with conn:
        rows = conn.execute('SELECT * FROM leaders ORDER BY votes DESC LIMIT ?', (top,))
        return [
            {
                'name': row['name'],
                'votes': row['votes'],
            } for row in rows
        ]


def get_random_names(limit=2):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    with conn:
        rows = conn.execute('SELECT name FROM names ORDER BY RANDOM() LIMIT ?', (limit,))
        return [row['name'] for row in rows]


def get_random_name():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    with conn:
        if random.random() > .1:
            rows = conn.execute('SELECT name FROM names ORDER BY RANDOM() LIMIT 2')
            return ' '.join([row['name'] for row in rows])
        rows = conn.execute('SELECT name FROM leaders ORDER BY RANDOM() LIMIT 1')
        return rows.fetchone()['name']


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
    ]
    with conn:
        for name in names:
            conn.execute('INSERT INTO names (name) VALUES (?)', (name,))


if __name__ == '__main__':
    if 'test' in sys.argv:
        clear()
        bootstrap()
        add_name('Bluhs')
        upvote_name('Bluh')
        print(get_leaders())
        upvote_name('Bluh')
        print(get_leaders())
        clear()

    for arg in sys.argv:
        if arg == 'clear':
            clear()
        if arg == 'bootstrap':
            bootstrap()
        if arg == 'load':
            load()
