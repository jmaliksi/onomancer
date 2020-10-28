import random

from flask import Flask, make_response, render_template, request, jsonify
from onomancer import database

# why use many file when one file do
app = Flask(__name__)

@app.route('/')
def index():
    return what()


@app.route('/about')
def what():
    return make_response(render_template('what.html'))


@app.route('/vote')
def vote():
    name = database.get_random_name()
    return make_response(render_template('vote.html', name=name))


@app.route('/leaderboard')
def leaderboard():
    names = database.get_leaders(top=20)
    return make_response(render_template('leaderboard.html', names=names))


@app.route('/egg')
def egg():
    return make_response(render_template('submit.html'))


@app.route('/submit', methods=['POST'])
def submit():
    """
    Submit one name.
    """
    # TODO validation
    # TODO captcha
    if request.form.get('name'):
        # egg
        database.add_name(request.form['name'])
    elif request.form.get('fullname'):
        database.upvote_name(request.form['fullname'])
    return egg()


@app.route('/rate', methods=['POST'])
def rate():
    """
    Rate a name.
    """
    name = request.form['name']
    judgement = ord(request.form['judgement'])

    if judgement == 128077:  # upvote
        database.upvote_name(name)
    elif judgement == 128154:  # love
        database.upvote_name(name, thumbs=2)
    elif judgement == 128148:  # thumbs down
        database.upvote_name(name, thumbs=-1)

    return vote()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
