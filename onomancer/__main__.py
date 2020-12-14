import base64
import functools
import json
import random
import math
import secrets
import sys
import time
import urllib.parse
import uuid

from flask import (
    Flask,
    make_response,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
)
from flask_simple_csrf import CSRF
from profanity import profanity
from flask_limiter import Limiter
from flask_limiter.util import get_ipaddr
from pylru import lrucache
from blaseball_mike.models import Player

from onomancer import database

# why use many file when one file do
app = Flask(__name__)
try:
    with open('data/csrf.key', 'r') as f:
        _key = f.read()
        CSRF_CONFIG = {
            'SECRET_CSRF_KEY': _key,
        }
        app.config['CSRF_CONFIG'] = CSRF_CONFIG

    with open('data/appsecret.key', 'r') as f:
        _key = f.read()
        app.secret_key = _key

    with open('data/mod.key', 'r') as f:
        app.config['MOD_KEY'] = f.read()
except Exception as e:
    print(e)

csrf = CSRF(config=CSRF_CONFIG)
app = csrf.init_app(app)

limiter = Limiter(
    app,
    key_func=get_ipaddr,
    default_limits=['5/second'],
)

class HttpsProxy(object):
    def __init__(self, app):
        self.app = app
        self.url_scheme = 'https'

    def __call__(self, environ, start_response):
        environ['wsgi.url_scheme'] = self.url_scheme
        return self.app(environ, start_response)

app.wsgi_app = HttpsProxy(app.wsgi_app)


profanity.load_words()
profanity.load_words(profanity.words + [
    'trump',
    'pewdipie',
    'rowling',
    'bollocks',
    'google',
    'ch00beh',
    ';--',
    'homestuck',
])

nonsense = lrucache(10000)


def super_secret(a, b):
    """shhhh"""
    return ''.join([chr(ord(aa) ^ ord(bb)) for aa, bb in zip(a, b)])


def super_safe_encrypt(a, b):
    return urllib.parse.quote(super_secret(a, b), safe='')


def super_safe_decrypt(a, b):
    return urllib.parse.unquote(super_secret(a, b))


app.jinja_env.globals.update(super_secret=super_safe_encrypt)
app.jinja_env.globals.update(testing=lambda: app.debug)


@app.before_request
def before_request():
    if 'CSRF_TOKEN' not in session or 'USER_CSRF' not in session:
        nonce = str(uuid.uuid4())
        session['USER_CSRF'] = nonce
        session['CSRF_TOKEN'] = csrf.create(session['USER_CSRF'])
    if 'rotkey' not in session:
        session['rotkey'] = secrets.token_urlsafe(100)


def require_csrf(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'POST':
            user_csrf = request.form.get('simplecsrf')

            if user_csrf in nonsense:
                session.pop('USER_CSRF', None)
                session.pop('CSRF_TOKEN', None)
                nonsense[user_csrf] = True
                return redirect(url_for('what'))
            nonsense[user_csrf] = True

            if csrf.verify(user_csrf, session['CSRF_TOKEN']) is False:
                session.pop('USER_CSRF', None)
                session.pop('CSRF_TOKEN', None)
                return redirect(url_for('what'))
            session['PREV_NONCE'] = session['USER_CSRF']
            session['USER_CSRF'] = str(uuid.uuid4())
            session['CSRF_TOKEN'] = csrf.create(session['USER_CSRF'])
            return f(*args, **kwargs)
        else:
            return f(*args, **kwargs)
    return decorated


@app.route('/')
def index():
    return what()


@app.route('/about')
def what():
    return make_response(render_template('what.html'))


@app.route('/vote', strict_slashes=False)
def vote(message='', guid=None):
    name = request.args.get('name', None)
    if not name:
        if not message:
            message = 'A card is drawn...'
        if guid:
            name = database.get_name_from_guid(guid)
        else:
            name = database.get_random_name()
    else:
        rotkey = session['rotkey']
        if rotkey:
            name = super_safe_decrypt(name, session['USER_CSRF'] + rotkey)
        if not message:
            message = 'The page turns...'
        names = name.split(' ')
        try:
            names = [_process_name(n) for n in names]
        except ValueError:
            name = database.get_random_name()
            message = 'Naughty...'
        if request.args.get('reverse'):
            # flip it turnwise
            name = ' '.join(names[::-1])
    flag = 'flagForm' in request.args
    if flag:
        message = 'What is your reason for flagging this name?'
    share_guid = database.share_guid(name)
    rotkey = secrets.token_urlsafe(100)
    res = make_response(render_template(
        'vote.html',
        name=name,
        message=message,
        rotkey=session['USER_CSRF'] + rotkey,
        flag_form=flag,
        share_guid=share_guid,
        reverse=request.args.get('reverse', False),
    ))
    session['rotkey'] = rotkey
    return res


@app.route('/annotate', methods=['GET', 'POST'], strict_slashes=False)
@require_csrf
def annotate():
    message = 'The margins stained...'

    if request.method == 'POST':
        name = request.form['name']
        rotkey = session['rotkey']
        name = super_safe_decrypt(
            urllib.parse.unquote(name),
            session['PREV_NONCE'] + rotkey,
        )
        message = 'A note taken. '
        judgement = ord(request.form['judgement'])
        if judgement == 128072:  # left
            database.annotate_egg(name, first=2)
            message += 'The ink shifts left...'
        elif judgement == 128073:  # right
            database.annotate_egg(name, second=2)
            message += 'The ink shifts right...'
        elif judgement == 128588:
            database.annotate_egg(name, first=1, second=1)
            message += random.choice([
                'The ink swirls...',
                'The ink settles...',
            ])
        elif judgement == 128078:
            database.upvote_name(name, thumbs=-1)
            message += 'The ink fades...'
        elif judgement == 129335:
            message = 'The next line...'

        rotkey = secrets.token_urlsafe(100)
        session['rotkey'] = rotkey

    name = request.args.get('name', None)
    if not name:
        name = database.get_eggs(limit=1, rand=1)[0]
    else:
        rotkey = session['rotkey']
        if rotkey:
            name = super_safe_decrypt(name, session['USER_CSRF'] + rotkey)
        try:
            name = _process_name(name)
        except ValueError:
            name = database.get_eggs(limit=1, rand=1)[0]
            message = 'Naughty...'

    flag = 'flagForm' in request.args
    if flag:
        message = 'What is your reason for flagging this egg?'
    examples = {}
    examples = database.get_annotate_examples(name)
    # rotkey already set by posts
    return make_response(render_template(
        'annotate.html',
        name=name,
        flag_form=flag,
        message=message,
        rotkey=session['USER_CSRF'] + session['rotkey'],
        examples=examples,
    ))


@app.route('/leaderboard')
def leaderboard(message=None):
    names = database.get_leaders(top=50)
    res = make_response(render_template(
        'leaderboard.html',
        names=names,
        message=message,
        rotkey=session['USER_CSRF'] + session['rotkey'],
    ))
    return res


@app.route('/downLeader', methods=['POST'])
@require_csrf
@limiter.limit('1/second')
def downLeader():
    command = request.form.get('command')
    if not command:
        return leaderboard(message="Hmm?")
    rotkey = session['rotkey']
    name = super_safe_decrypt(urllib.parse.unquote(request.form.get('name')), session['PREV_NONCE'] + rotkey)
    if command == 'flip':
        database.flip_leader(name)
        message = "The pages thrum with feedback..."
    elif command == 'down':
        database.upvote_name(name, thumbs=-1)
        message = "A judgement made, the Chosen shift..."
    else:
        message = "Hmm?"
    return leaderboard(message=message)

@app.route('/egg')
def egg(message='The Onomancer waits...'):
    return make_response(render_template('submit.html', message=message))


@app.route('/submit', methods=['POST'])
@require_csrf
def submit():
    """
    Submit one name.
    """
    # TODO captcha
    try:
        if request.form.get('name'):
            # egg
            name = _process_name(request.form.get('name'))
            database.add_name(name)
        elif request.form.get('fullname'):
            name = _process_name(request.form.get('fullname'))
            names = name.split(' ', 1)
            if len(names) == 1:
                # maybe accidental one name submission
                database.add_name(name)
            else:
                database.upvote_name(name, thumbs=0)
        else:
            raise ValueError()
    except ValueError:
        return egg(message='Naughty...')
    return egg(message=random.choice([
        'The scratching of ink to page...',
        'The words soak...',
        'That which is given, considered...',
        'A flutter of script...',
    ]))


@app.route('/pool', methods=['GET'])
def pool():
    names = database.random_pool()
    rotkey = secrets.token_urlsafe(100)
    res = make_response(render_template('pool.html', names=names, rotkey=session['USER_CSRF'] + rotkey))
    res.set_cookie('rotkey', value=rotkey)
    return res


def _process_name(name):
    if not name:
        raise ValueError()
    if len(name) > 25:
        raise ValueError()
    profane = profanity.contains_profanity(name)
    if profane:
        raise ValueError()
    name = name.strip()
    if name.lower() == name:
        # no capital letters, make some assumptions
        return name.title()
    return name


@app.route('/rate', methods=['POST'])
@require_csrf
def rate():
    """
    Rate a name.
    """
    name = request.form['name']
    rotkey = session['rotkey']
    name = super_safe_decrypt(urllib.parse.unquote(name), session['PREV_NONCE'] + rotkey)
    judgement = ord(request.form['judgement'])

    message = f'Your judgement is rendered.'
    if judgement == 128077:  # upvote
        database.upvote_name(name, thumbs=1)
        if request.form['reverse']:
            try:
                eggs = name.split(' ', 1)
                database.annotate_egg(eggs[0], first=1)
                database.annotate_egg(eggs[-1], second=1)
            except KeyError:
                pass
        message += ' The Onomancer nods...'
    elif judgement == 128154:  # love
        database.upvote_name(name, thumbs=3)
        try:
            eggs = name.split(' ', 1)
            database.annotate_egg(eggs[0], first=1)
            database.annotate_egg(eggs[-1], second=1)
        except KeyError:
            pass
        message += ' The Onomancer smiles...'
    elif judgement == 128148:  # hate
        database.upvote_name(name, thumbs=-2)
        flipped = ' '.join(name.split(' ')[::-1])
        database.upvote_name(flipped, thumbs=-2, hit_eggs=False)
        message += ' The Onomancer frowns...'
    elif judgement == 128078:  # thumbs down
        flipped = ' '.join(name.split(' ')[::-1])
        database.upvote_name(flipped, thumbs=-1, hit_eggs=False)
        database.upvote_name(name, thumbs=-1)
        message += ' The Onomancer stares...'

    return vote(message=message)


@app.route('/moderate/<key>', methods=['GET'])
@app.route('/moderate/<key>/<type_>', methods=['POST'])
@require_csrf
def moderate(key, type_=''):
    if app.config['MOD_KEY'] != key:
        return redirect(url_for('what'))
    if request.method == 'POST':
        mod_action = {
            id_: 0 if val == 'good' else -1
            for id_, val in request.form.items()
        }
        if type_ == 'names':
            database.moderate(names=mod_action)
        if type_ == 'eggs':
            database.moderate(eggs=mod_action)

    mod_list = database.get_mod_list()
    return make_response(render_template(
        'moderate.html',
        leaders=mod_list['names'],
        eggs=mod_list['eggs'],
        key=key,
    ))


@app.route('/moderate/bad-eggs/<key>', methods=['GET'])
def get_bad_eggs(key):
    if app.config['MOD_KEY'] != key:
        return redirect(url_for('what'))
    return jsonify({
        'leaders': database.admin_leaders(),
        'eggs': database.admin_eggs(),
    })


@app.route('/flag', methods=['POST'])
@require_csrf
def flag():
    is_egg = request.form.get('egg', False)
    name = super_safe_decrypt(
        urllib.parse.unquote(request.form['name']),
        session['PREV_NONCE'] + session['rotkey'],
    )
    reason = request.form['reason'].strip()
    if len(reason) <= 5:
        rotkey = secrets.token_urlsafe(100)
        session['rotkey'] = rotkey
        return make_response(render_template(
            'annotate.html' if is_egg else 'vote.html',
            name=name,
            message='Provide a reason.',
            rotkey=session['USER_CSRF'] + rotkey,
            flag_form=True,
        ))
    if is_egg:
        database.flag_egg(name, reason)
    else:
        database.flag_name(name, reason)
    rotkey = secrets.token_urlsafe(100)
    session['rotkey'] = rotkey
    return redirect(url_for('annotate')) if is_egg else vote()


@app.route('/moderate/admin-eggs/<key>', methods=['GET', 'POST'], strict_slashes=False)
@require_csrf
def admin_eggs(key):
    if app.config['MOD_KEY'] != key:
        return redirect(url_for('what'))

    if request.method == 'POST':
        id_ = request.form.get('id_')
        command = request.form.get(id_)
        is_leader = request.form.get('type_') == 'fullname'
        if command == 'reset':
            if is_leader:
                database.reset_leader(id_)
            else:
                database.reset_egg(id_)
        elif command == 'delete':
            if is_leader:
                database.delete_leader(id_)
            else:
                database.delete_egg(id_)
        else:
            database.mark_naughty(
                int(id_),
                is_leader=is_leader,
                naughty={
                    'good': 0,
                    'bad': -1,
                    'back to moderate queue': 1,
                }.get(request.form.get(id_), 1),
            )

    lookup = {
        'names': [],
        'eggs': [],
    }
    token = request.args.get('lookup') or request.form.get('token')
    only_good = request.args.get('onlyGood') or request.form.get('onlyGood')
    if token:
        lookup = database.lookup(token, only_good=only_good)
    return make_response(render_template(
        'admin_egg.html',
        lookup=lookup,
        key=key,
        naughty_map={
            -1: 'bad',
            0: 'good',
            1: 'pending moderation',
        }.get,
        token=token,
        only_good=only_good or '',
    ))


@app.route('/collect', methods=['GET', 'POST'])
def collect():
    if request.method == 'POST':
        token = request.form['token']
        collection = [
            super_safe_decrypt(urllib.parse.unquote(name), token * 10)
            for name in json.loads(request.form['collection'])
        ]
        cname = 'Collection'
        anim = {}
        if request.form.get('cname'):
            try:
                cname = ' '.join([
                    _process_name(n) for n in request.form['cname'].split(' ')
                ])
            except ValueError:
                cname = 'Collection'
        anchor = 'titleAnchor'
        if request.form.get('command'):
            command = request.form.get('command')
            name_to_burn = 'name' in request.form and super_safe_decrypt(
                urllib.parse.unquote(request.form['name']),
                token * 10,
            )
            idx = -1
            if command == 'flip':
                flipped = ' '.join(name_to_burn.split(' ')[::-1])
                database.upvote_name(flipped, thumbs=0)
                idx = collection.index(name_to_burn)
                collection[idx] = flipped
                anim = {'type': 'reverb', 'who': flipped}
            elif command == 'fire':
                rookie = database.collect(1)[0]
                idx = collection.index(name_to_burn)
                collection[idx] = rookie
                anim = {'type': 'burning', 'who': rookie}
            elif command == 'reverb':
                collection = sorted(collection, key=lambda _: random.random())
                anim = {'type': 'reverb_all', 'who': None}
            elif command == 'fireworks':
                anim = {'type': 'burn_all', 'who': None}
                res = redirect(url_for('collect'))
                res.set_cookie('anim', json.dumps(anim), max_age=10)
                return res
            elif command == 'feedback':
                stashed = json.loads(request.cookies.get('stash', '[]'))
                stashed = [s for s in stashed if s]
                if not stashed:
                    rookie = database.collect(1)[0]
                else:
                    rookie = database.get_name_from_guid(random.choice(stashed))
                idx = collection.index(name_to_burn)
                collection[idx] = rookie
                anim = {'type': 'feedback', 'who': rookie}
            if idx >= 9:
                anchor = 'rotationAnchor'
            elif idx >= 0:
                anchor = 'lineupAnchor'
            else:
                anchor = 'titleAnchor'
        res = redirect(url_for(
            'collect',
            _anchor=anchor,
            t=token[:8],
            f=_curse_collection(*collection),
            cname=cname,
        ))
        res.set_cookie('anim', json.dumps(anim), max_age=10)
        return res
    token = request.args.get('token') or request.args.get('t')
    if not token:
        token = secrets.token_hex(4)
        return redirect(url_for(
            'collect',
            t=token,
            f=_curse_collection(*database.collect()),
        ))

    anim = request.cookies.get('anim', {})
    if anim:
        anim = json.loads(anim)
    cname = request.args.get('cname', '')

    saves = {
        'save1': _parse_collection_cookie('save1'),
        'save2': _parse_collection_cookie('save2'),
        'save3': _parse_collection_cookie('save3'),
    }
    # f is for friends
    if request.args.get('load'):
        loaded = saves[request.args['load']]
        collection = _load_collection(loaded[0])
        cname = loaded[1]
    else:
        collection = _load_collection(request.args['f'], anim)
    friends = [n[0] for n in collection]
    friend_code = _curse_collection(*friends).decode()
    if request.args.get('save'):
        saves[request.args['save']] = (friend_code, cname)
    if request.args.get('clear'):
        saves[request.args['clear']] = None
    res = make_response(render_template(
        'collect.html',
        lineup=collection[:9],
        rotation=collection[9:],
        message=random.choice([
            'A collection of chosen...',
            'Your hand...',
            'A drawing of pages...',
        ]),
        token=token * 10,
        collection=json.dumps([super_secret(n, token * 10) for n in friends]),
        friends=friend_code,
        saves=saves,
        cname=cname,
        len=len,
    ))
    if request.args.get('save'):
        res.set_cookie(request.args['save'], value=f'{friend_code}:{cname}', max_age=100000000)
    if request.args.get('clear'):
        res.delete_cookie(request.args['clear'])
    return res


def _parse_collection_cookie(cookie_name):
    cookie = request.cookies.get(cookie_name)
    if not cookie:
        return (None, None)
    tokens = cookie.split(':')
    if len(tokens) == 2:
        return (tokens[0], tokens[1])
    return (cookie, None)


def _get_animation(name, anim):
    if not anim:
        return ''
    if anim['type'] == 'reverb_all':
        return 'reverb'
    if anim['type'] == 'burn_all':
        return 'burning'
    if anim['who'] == name:
        return anim['type']
    return ''


def _load_collection(friends, anim=None):
    names = _uncurse_collection(friends)
    collection = []
    for i, name in enumerate(names):
        player = Player.make_random(seed=name)
        if i < 9:
            rating = player.batting_stars
        else:
            rating = player.pitching_stars
        rating = math.modf(rating)
        collection.append((
            name,
            range(int(rating[1])),
            rating[0] >= .5,
            _get_animation(name, anim),
        ))

    return collection


@functools.lru_cache()
def _curse_name(name):
    try:
        h = int((''.join(str(ord(c)) for c in name) * 4)[:19])
        half_star = h % 2 == 0
        h = str(int(abs(h)))
        rating = round((float(h[1:7]) + float(h[7:13]) + float(h[13:])) / 500000.0) - ((int(h[0]) % 3) - 1)
        return rating, half_star
    except Exception:
        h = hash(name)
        half_star = h < 0
        return h % 6, half_star


@functools.lru_cache(100)
def _curse_collection(*names):
    name_ids = database.get_collection_ids(names)
    bt = []
    for name in names:
        id_ = name_ids[name]
        if not id_:
            id_ = 0
        tokens = str(id_)
        for c in tokens:
            bt.append(int(c))
        bt.append(11)
    return base64.urlsafe_b64encode(bytes(bt))


@functools.lru_cache(100)
def _uncurse_collection(code):
    bt = base64.urlsafe_b64decode(code)
    ids = []
    while 11 in bt:
        dex = bt.index(11)
        chunk = bt[:dex]
        bt = bt[dex + 1:]
        ids.append(int(''.join([str(c) for c in chunk])))
    if bt:
        ids.append(int(''.join(bt)))
    return database.get_names_from_ids(ids)


@app.route('/moderate/dumpEggs/<key>')
@limiter.limit('1/minute')
def mod_dump_eggs(key):
    if app.config['MOD_KEY'] != key:
        return redirect(url_for('what'))
    return jsonify(database.dump_names())


@app.route('/moderate/dumpNames/<key>')
@limiter.limit('1/minute')
def mod_dump_names(key):
    if app.config['MOD_KEY'] != key:
        return redirect(url_for('what'))
    return jsonify(database.dump_leaders())


@app.route('/chart/names')
@limiter.limit('1/second')
def chart_names():
    count, votes = database.chart_leaders()
    type_ = request.args.get('type', 'linear')
    return make_response(render_template(
        'name_chart.html',
        count=count,
        votes=votes,
        type_=type_,
    ))


@app.route('/chart/eggs')
@limiter.limit('1/second')
def chart_eggs():
    start = request.args.get('start', 1)
    end = request.args.get('end', None)
    good, bad = database.chart_eggs(start=start, end=end)
    return make_response(render_template(
        'egg_chart.html',
        good_eggs=good,
        bad_eggs=bad,
    ))


@app.route('/chart/eggVotes')
@limiter.limit('1/second')
def chart_egg_votes():
    start = request.args.get('start', 1)
    end = request.args.get('end', None)
    votes = database.chart_egg_votes(start=start, end=end)
    return make_response(render_template(
        'egg_vote_chart.html',
        eggs=votes,
        ids=[v['id'] for v in votes],
    ))


@app.route('/api/getName')
@limiter.limit('10/second')
def get_name():
    name = database.get_random_name()
    with_stats = request.args.get('with_stats', False)
    if with_stats:
        return _make_player_json(name)
    return jsonify(name)


@app.route('/api/getNames')
def get_names():
    valid_args = {
        'threshold',
        'limit',
        'offset',
        'random',
        'with_stats',
    }
    for arg in request.args:
        if arg not in valid_args:
            return jsonify({'error': f'unrecognized query parameter `{arg}`'}), 400
    threshold = int(request.args.get('threshold', 0))
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    rand = request.args.get('random', 0)

    names = database.get_names(threshold, limit, offset, rand)
    with_stats = request.args.get('with_stats', False)
    if with_stats:
        return jsonify([_make_player_json(name) for name in names])

    return jsonify(names)


@app.route('/api/getEggs')
def get_eggs():
    valid_args = {
        'threshold',
        'limit',
        'offset',
        'random',
    }
    for arg in request.args:
        if arg not in valid_args:
            return jsonify({'error': f'unrecognized query parameter `{arg}`'}), 400
    threshold = int(request.args.get('threshold', 0))
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    rand = request.args.get('random', 0)
    return jsonify(database.get_eggs(threshold, limit, offset, rand))


@app.route('/api/generateStats/<name>')
@limiter.limit('1/second')
def generateStats(name):
    return jsonify(_make_player_json(name))


@app.route('/api/getStats')
def getStats():
    guids = request.args.get('ids', '').split(',')
    if not guids:
        return jsonify({'error': 'missing argument `ids`'}), 400
    names = database.get_names_from_guids(guids)
    res = {}
    for guid, name in names.items():
        res[guid] = _make_player_json(name, id_=guid)
    return jsonify(res)

@app.route('/shareName/<guid>')
def shareName(guid, message='The token shared...'):
    try:
        name = database.get_name_from_guid(guid)
    except TypeError:
        guid = database.get_guid_for_name(guid)
        return redirect(url_for('shareName', guid=guid))
    img_url = database.get_image_url(name=name)
    flag = 'flagForm' in request.args
    if flag:
        message = 'What is your reason for flagging this name?'
    examine = 'examine' in request.args
    interview = None

    player = _make_player_json(name)
    stars = [
        ('Batting', range(int(player['batting_stars'])), math.modf(player['batting_stars'])[0]),
        ('Pitching', range(int(player['pitching_stars'])), math.modf(player['pitching_stars'])[0]),
        ('Baserunning', range(int(player['baserunning_stars'])), math.modf(player['baserunning_stars'])[0]),
        ('Defense', range(int(player['defense_stars'])), math.modf(player['defense_stars'])[0]),
    ]

    if examine:
        message = 'The notes lift...'
        interview = [
            ('Evolution', 'Base'),
            ('Pregame Ritual', ['Appraisal', 'Regarding', 'Offering'][player['fate'] % 3]),
            ('Coffee Style', 'Coffee?'),
            ('Blood Type', 'Blood?'),
            ('Fate', player['fate']),
            ('Soulscream', player['soulscream']),

        ]

    share_desc = '\n'.join([
        f'Batting: {"★" * len(stars[0][1])}{"☆" if stars[0][2] else ""}',
        f'Pitching: {"★" * len(stars[1][1])}{"☆" if stars[1][2] else ""}',
        f'Baserunning: {"★" * len(stars[2][1])}{"☆" if stars[2][2] else ""}',
        f'Defense: {"★" * len(stars[3][1])}{"☆" if stars[3][2] else ""}',
        f'Soulscream: {player["soulscream"]}',
    ])
    return make_response(render_template(
        'share.html',
        name=name,
        message=message,
        share_image=img_url,
        share_url=f'https://onomancer.sibr.dev/shareName/{guid}',
        share_guid=guid,
        flag_form=flag,
        rotkey=session['USER_CSRF'] + secrets.token_urlsafe(100),
        examine=examine,
        stars=stars,
        interview=interview,
        share_title=name,
        share_desc=share_desc,
    ))


@app.route('/shareCollection/<friends>')
def shareCollection(friends):
    collection = _load_collection(friends)
    img_url = database.get_collection_image_url(*collection)
    return make_response(render_template(
        'shareCollection.html',
        lineup=collection[:9],
        rotation=collection[9:],
        message='Gathered and sowed...',
        share_image=img_url,
        share_url=f'https://onomancer.sibr.dev/shareCollection/{friends}',
        cname=request.args.get('cname', 'Collection'),
        share_title=request.args.get('cname', 'Collection'),
    ))


@app.route('/stash', methods=['GET', 'POST'])
@require_csrf
def stash():
    stashed = json.loads(request.cookies.get('stash', '[]'))
    stashed = [s for s in stashed if s]

    message = ''
    if request.method == 'POST':
        command = request.form['command']
        guid = request.form['guid']
        redirect = request.form.get('redirect', 'share')
        if command == 'eject':
            stashed.remove(guid)
            message = 'The monicker expunged.'
        if command == 'stash':
            stashed.append(guid)
            if redirect == 'vote':
                res = vote(
                    message='The name stashed.',
                    guid=guid,
                )
                res.set_cookie(
                    'stash',
                    value=json.dumps(stashed),
                    max_age=1000000000,
                )
                return res
            message = 'An appelation stashed.'

    names = {}
    if stashed:
        stashed = list(set(stashed))
        names = database.get_names_from_guids(stashed)
    if not names:
        message = 'An empty stash'

    res = make_response(render_template(
        'stash.html',
        names=names,
        message=message,
    ))
    res.set_cookie(
        'stash',
        value=json.dumps(stashed),
        max_age=1000000000,
    )
    return res


def _make_player_json(name, id_=None):
    player = Player.make_random(name=name, seed=name)
    js = player.json()
    props = [
        'soulscream',
        'batting_rating',
        'batting_stars',
        'pitching_rating',
        'pitching_stars',
        'baserunning_rating',
        'baserunning_stars',
        'defense_rating',
        'defense_stars',
    ]
    for prop in props:
        js[prop] = getattr(player, prop)
    if id_:
        js['id'] = id_
    return js


if __name__ == '__main__':
    debug = False
    if 'test' in sys.argv:
        debug = True
        app.wsgi_app.url_scheme = 'http'
    app.run(host='0.0.0.0', port=5001, debug=debug)
