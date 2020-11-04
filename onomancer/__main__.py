from collections import Counter
import functools
import json
import random
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
    rotkey = secrets.token_urlsafe(100)
    res = make_response(render_template(
        'vote.html',
        name=name,
        message=message,
        rotkey=session['USER_CSRF'] + rotkey,
        flag_form=flag,
    ))
    session['rotkey'] = rotkey
    return res


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
@limiter.limit('3/minute')
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
    return leaderboard(message=message, patience=30)

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
        database.upvote_name(name, thumbs=2)
        message += ' The Onomancer nods...'
    elif judgement == 128154:  # love
        database.upvote_name(name, thumbs=3)
        message += ' The Onomancer smiles...'
    elif judgement == 128148:  # hate
        database.upvote_name(name, thumbs=-2)
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
    name = super_safe_decrypt(
        urllib.parse.unquote(request.form['name']),
        session['PREV_NONCE'] + session['rotkey'],
    )
    reason = request.form['reason'].strip()
    if len(reason) <= 5:
        rotkey = secrets.token_urlsafe(100)
        session['rotkey'] = rotkey
        return make_response(render_template(
            'vote.html',
            name=name,
            message='Provide a reason.',
            rotkey=session['USER_CSRF'] + rotkey,
            flag_form=True,
        ))
    database.flag_name(name, reason)
    rotkey = secrets.token_urlsafe(100)
    session['rotkey'] = rotkey
    return vote()


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
        command = request.form['command']
        name_to_burn = super_safe_decrypt(
            urllib.parse.unquote(request.form['name']),
            token * 10,
        )
        if command == 'flip':
            collection[collection.index(name_to_burn)] = ' '.join(name_to_burn.split(' ')[::-1])
        elif command == 'fire':
            collection[collection.index(name_to_burn)] = database.collect(1)[0]
        return redirect(url_for(
            'collect',
            token=token[:8],
            collection=[
                super_safe_encrypt(name, token * 10)
                for name in collection
            ],
        ))
    token = request.args.get('token')
    if not token:
        token = secrets.token_hex(4)
        return redirect(url_for(
            'collect',
            token=token,
            collection=[
                super_safe_encrypt(name, token * 10)
                for name in database.collect()
            ],
        ))
    collection = [
        (
            super_safe_decrypt(urllib.parse.unquote(name), token * 10),
            range(hash(name) % 6),
            bool(ord(name[0]) % 2),
        )
        for name in request.args.getlist('collection')
    ]
    return make_response(render_template(
        'collect.html',
        lineup=collection[:9],
        rotation=collection[9:],
        message=random.choice([
            'A collection of chosen...',
            'Your hand...',
            'A drawing of pages...',
            'What threads connect...',
        ]),
        token=token * 10,
        collection=json.dumps([
            super_safe_encrypt(name, token * 10)
            for (name, _, _) in collection
        ]),
    ))


if __name__ == '__main__':
    debug = False
    if 'test' in sys.argv:
        debug = True
    app.run(host='0.0.0.0', port=5001, debug=debug)
