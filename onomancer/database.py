import sqlite3
import sys

DB_NAME = 'onomancer.db'

conn = sqlite3.connect(DB_NAME)
conn.row_factory = sqlite3.Row


def bootstrap():
    with conn:
        conn.execute('CREATE TABLE names (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)')
        conn.execute('CREATE UNIQUE INDEX idx_names_name ON names (name)')

        conn.execute('CREATE TABLE leaders (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, votes INTEGER)')
        conn.execute('CREATE INDEX idx_leaders_votes ON leaders (votes)')
        conn.execute('CREATE UNIQUE INDEX idx_leaders_name ON leaders (name)')


def clear():
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
    with conn:
        conn.execute("INSERT INTO names (name) VALUES (?)", (name,))


def upvote_name(name):
    with conn:
        conn.execute('INSERT INTO leaders (name, votes) VALUES (?, 1) ON CONFLICT (name) DO UPDATE SET votes = votes + 1', (name,))


def get_leaders(top=20):
    with conn:
        rows = conn.execute('SELECT * FROM leaders ORDER BY votes LIMIT ?', (top,))
        return [
            {
                'name': row['name'],
                'votes': row['votes'],
            } for row in rows
        ]


def get_random_names(limit=2):
    with conn:
        rows = conn.execute('SELECT name FROM names ORDER BY RANDOM() LIMIT ?', (limit,))
        return [row['name'] for row in rows]


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
        return

    for arg in sys.argv:
        if arg == 'clear':
            clear()
        if arg == 'bootstrap':
            bootstrap()
        if arg == 'load':
            pass  # TODO
