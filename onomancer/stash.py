import json
from onomancer import database
from flask import request


class Stash:
    MAX_AGE = 1000000000
    HISTORY_LENGTH = 14

    def __init__(self):
        self._bookmarked_guids = json.loads(request.cookies.get('stash', '[]'))
        self._bookmarked_names = {}
        self._history_guids = json.loads(request.cookies.get('history', '[]'))
        self._history_names = {}
        self._stats = json.loads(request.cookies.get('stats', '{}'))

    def bookmarked_guids(self):
        return [s for s in self._bookmarked_guids if s]

    def bookmarked_names(self):
        if self._bookmarked_names:
            return self._bookmarked_names
        self._bookmarked_names = database.get_names_from_guids(self.bookmarked_guids())
        return self._bookmarked_names

    def history_names(self):
        if self._history_names:
            return self._history_names
        names = database.get_names_from_guids(self._history_guids)
        self._history_names = list(filter(lambda a: a, map(lambda g: (g, names[g]) if g in names else None, self._history_guids)))[::-1]
        return self._history_names

    def stash_name(self, guid):
        self._bookmarked_guids.append(guid)

    def remove_name(self, guid):
        self._bookmarked_guids.remove(guid)

    def stash_history(self, guid):
        self._history_guids.append(guid)
        self._history_guids = self._history_guids[-14:]

    def increment_stat(self, stat):
        val = self._stats.get(stat, 0)
        self._stats[stat] = val + 1

    def get_stat(self, stat):
        return self._stats.get(stat, 0)

    def get_total_appraisal(self):
        return sum((
            self.get_stat('💚'),
            self.get_stat('👍'),
            self.get_stat('👎'),
            self.get_stat('💔'),
        ))

    def get_total_annotation(self):
        return sum((
            self.get_stat('👈'),
            self.get_stat('👉'),
            self.get_stat('👎👎'),
            self.get_stat('🙌'),
        ))

    def save(self, res):
        res.set_cookie(
            'stash',
            value=json.dumps(self._bookmarked_guids),
            max_age=self.MAX_AGE,
        )
        res.set_cookie(
            'history',
            value=json.dumps(self._history_guids),
            max_age=self.MAX_AGE,
        )
        res.set_cookie(
            'stats',
            value=json.dumps(self._stats),
            max_age=self.MAX_AGE,
        )
