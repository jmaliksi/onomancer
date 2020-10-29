import random
import sys

from flask import Flask, make_response, render_template, request, jsonify
from profanity import profanity
from onomancer import database

# why use many file when one file do
app = Flask(__name__)

profanity.load_words(['trump'])

@app.route('/')
def index():
    return what()


@app.route('/about')
def what():
    return make_response(render_template('what.html'))


@app.route('/vote')
def vote(message=None):
    name = database.get_random_name()
    return make_response(render_template('vote.html', name=name, message=message))


@app.route('/leaderboard')
def leaderboard():
    names = database.get_leaders(top=20)
    return make_response(render_template('leaderboard.html', names=names))


@app.route('/egg')
def egg(message=None):
    return make_response(render_template('submit.html', message=message))


@app.route('/submit', methods=['POST'])
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
            database.upvote_name(name)
        else:
            raise ValueError()
    except ValueError:
        return egg(message='Naughty...')
    return egg(message=f'{name} is witnessed.')


@app.route('/pool', methods=['GET'])
def pool():
    return database.pool()


def _process_name(name):
    if not name:
        raise ValueError()
    profane = profanity.contains_profanity(name)
    if profane:
        raise ValueError()
    if name.lower() == name:
        # no capital letters, make some assumptions
        return name.title()
    return name


@app.route('/rate', methods=['POST'])
def rate():
    """
    Rate a name.
    """
    name = request.form['name']
    judgement = ord(request.form['judgement'])

    message = f'Your judgement is rendered.'
    if judgement == 128077:  # upvote
        database.upvote_name(name)
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


if __name__ == '__main__':
    debug = False
    if 'test' in sys.argv:
        debug = True
    app.run(host='0.0.0.0', port=5001, debug=debug)
