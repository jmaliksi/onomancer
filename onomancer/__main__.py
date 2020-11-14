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

profanity.load_words([
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
def vote(message=''):
    name = request.args.get('name', None)
    if not name:
        if not message:
            message = 'A card is drawn...'
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
            database.annotate_egg(name, first=1)
            message += 'The ink shifts left...'
        elif judgement == 128073:  # right
            database.annotate_egg(name, second=1)
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
    if 'examples' in request.args:
        message = 'Observe context...'
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
def leaderboard(message=None, patience=None):
    names = database.get_leaders(top=50)
    patience_cookie = request.cookies.get('patience')
    if not message and patience_cookie:
        message = 'Them that descend still settle...'
    res = make_response(render_template(
        'leaderboard.html',
        names=names,
        message=message,
        patience=patience or patience_cookie,
        rotkey=session['USER_CSRF'] + session['rotkey'],
    ))
    if patience:
        res.set_cookie(
            'patience',
            value=str(patience),
            max_age=patience,
        )
    return res


@app.route('/downLeader', methods=['POST'])
@require_csrf
@limiter.limit('6/minute')
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
        database.upvote_name(name, thumbs=-2)
        message = "A judgement made, the Chosen shift..."
    else:
        message = "Hmm?"
    return leaderboard(message=message, patience=10)

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
        message += ' The Onomancer nods...'
    elif judgement == 128154:  # love
        database.upvote_name(name, thumbs=3)
        try:
            eggs = name.split(' ', 1)
            database.annotate_egg(eggs[0], first=1)
            database.annotate_egg(eggs[1], second=1)
        except KeyError:
            pass
        message += ' The Onomancer smiles...'
    elif judgement == 128148:  # hate
        database.upvote_name(name, thumbs=-2)
        flipped = ' '.join(name.split(' ')[::-1])
        database.upvote_name(flipped, thumbs=-1, hit_eggs=False)
        message += ' The Onomancer frowns...'
    elif judgement == 128078:  # thumbs down
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
@require_csrf
def collect():
    if request.method == 'POST':
        token = request.form['token']
        collection = [
            super_safe_decrypt(urllib.parse.unquote(name), token * 10)
            for name in json.loads(request.form['collection'])
        ]
        command = request.form['command']
        name_to_burn = 'name' in request.form and super_safe_decrypt(
            urllib.parse.unquote(request.form['name']),
            token * 10,
        )
        anim = {}
        if command == 'flip':
            flipped = ' '.join(name_to_burn.split(' ')[::-1])
            database.upvote_name(flipped, thumbs=0)
            collection[collection.index(name_to_burn)] = flipped
            anim = {'type': 'reverb', 'who': flipped}
        elif command == 'fire':
            rookie = database.collect(1)[0]
            collection[collection.index(name_to_burn)] = rookie
            anim = {'type': 'burning', 'who': rookie}
        elif command == 'reverb':
            collection = sorted(collection, key=lambda _: random.random())
            anim = {'type': 'reverb_all', 'who': None}
        elif command == 'fireworks':
            anim = {'type': 'burn_all', 'who': None}
            res = redirect(url_for('collect'))
            res.set_cookie('anim', json.dumps(anim), max_age=10)
            return res
        res = redirect(url_for(
            'collect',
            t=token[:8],
            f=_curse_collection(*collection),
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

    saves = {
        'save1': request.cookies.get('save1'),
        'save2': request.cookies.get('save2'),
        'save3': request.cookies.get('save3'),
    }
    # f is for friends
    if request.args.get('load'):
        loaded = saves[request.args['load']]
        collection = [
            (
                name,
                range(_curse_name(name)[0]),
                _curse_name(name)[1],
                '',
            )
            for name in _uncurse_collection(loaded)
        ]
    else:
        collection = [
            (
                name,
                range(_curse_name(name)[0]),
                _curse_name(name)[1],
                _get_animation(name, anim),
            )
            for name in _uncurse_collection(request.args['f'])
        ]
    friends = [n[0] for n in collection]
    friend_code = _curse_collection(*friends).decode()
    if request.args.get('save'):
        saves[request.args['save']] = friend_code
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
    ))
    if request.args.get('save'):
        res.set_cookie(request.args['save'], value=friend_code, max_age=100000000)
    if request.args.get('clear'):
        res.delete_cookie(request.args['clear'])
    return res


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


@app.route('/api/getName')
@limiter.limit('10/second')
def get_name():
    return jsonify(database.get_random_name())


@app.route('/api/getNames')
def get_names():
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
    return jsonify(database.get_names(threshold, limit, offset, rand))


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


@app.route('/shareName/<guid>')
def shareName(guid):
    name = database.get_name_from_guid(guid)
    img_url = database.get_image_url(name=name)
    return make_response(render_template(
        'share.html',
        name=name,
        message='The token shared...',
        share_image=img_url,
        share_url=f'https://onomancer.sibr.dev/shareName/{guid}',
    ))


@app.route('/shareCollection/<friends>')
def shareCollection(friends):
    collection = [
        (
            name,
            range(_curse_name(name)[0]),
            _curse_name(name)[1],
            '',
        )
        for name in _uncurse_collection(friends)
    ]
    img_url = database.get_collection_image_url(*collection)
    return make_response(render_template(
        'shareCollection.html',
        lineup=collection[:9],
        rotation=collection[9:],
        message='Gathered and sowed...',
        share_image=img_url,
        share_url=f'https://onomancer.sibr.dev/shareCollection/{friends}',
    ))


if __name__ == '__main__':
    debug = False
    if 'test' in sys.argv:
        debug = True
    app.run(host='0.0.0.0', port=5001, debug=debug)
