import functools
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
        session['USER_CSRF'] = str(uuid.uuid4())
        session['CSRF_TOKEN'] = csrf.create(session['USER_CSRF'])


def require_csrf(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'POST':
            user_csrf = request.form.get('simplecsrf')
            if csrf.verify(user_csrf, session['CSRF_TOKEN']) is False:
                session.pop('USER_CSRF', None)
                session.pop('CSRF_TOKEN', None)
                return redirect(url_for('what'))
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
        rotkey = request.cookies.get('rotkey')
        if rotkey:
            name = super_safe_decrypt(name, rotkey)
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
    rotkey = secrets.token_urlsafe(100)
    res = make_response(render_template(
        'vote.html',
        name=name,
        message=message,
        rotkey=rotkey,
    ))
    res.set_cookie('rotkey', value=rotkey)
    return res


@app.route('/leaderboard')
def leaderboard(message=None, patience=None):
    names = database.get_leaders(top=20)
    patience_cookie = request.cookies.get('patience')
    if not message and patience_cookie:
        message = 'Them that descend still settle...'
    res = make_response(render_template(
        'leaderboard.html',
        names=names,
        message=message,
        patience=patience or patience_cookie,
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
def downLeader():
    if not request.form.get('name'):
        return leaderboard(message="Hmm?")
    database.upvote_name(request.form['name'], thumbs=-1)
    return leaderboard(message="A judgement made, the Chosen shift...", patience=20)

@app.route('/egg')
def egg(message=None):
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
            names = name.split(' ')
            if len(names) == 2:
                database.add_name(names[0])
                database.add_name(names[1])
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
    res = make_response(render_template('pool.html', names=names, rotkey=rotkey))
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
    judgement = ord(request.form['judgement'])

    message = f'Your judgement is rendered.'
    if judgement == 128077:  # upvote
        database.upvote_name(name, thumbs=1)
        message += ' The Onomancer nods...'
    elif judgement == 128154:  # love
        database.upvote_name(name, thumbs=2)
        message += ' The Onomancer smiles...'
    elif judgement == 128148:  # thumbs down
        database.upvote_name(name, thumbs=-2)
        message += ' The Onomancer frowns...'
    elif judgement == 128078:
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
    return make_response(render_template('moderate.html', leaders=mod_list['names'], eggs=mod_list['eggs'], key=key))


@app.route('/moderate/bad-eggs/<key>', methods=['GET'])
def get_bad_eggs(key):
    if app.config['MOD_KEY'] != key:
        return redirect(url_for('what'))
    return jsonify({
        'leaders': database.admin_leaders(),
        'eggs': database.admin_eggs(),
    })


if __name__ == '__main__':
    debug = False
    if 'test' in sys.argv:
        debug = True
    app.run(host='0.0.0.0', port=5001, debug=debug)
