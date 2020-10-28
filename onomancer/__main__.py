from flask import Flask, make_response, render_template, request, jsonify
from onomancer import database

# why use many file when one file do
app = Flask(__name__)

@app.route('/')
def index():
    return vote()


@app.route('/vote')
def vote():
    names = database.get_random_names(limit=2)
    name = ' '.join(names)
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
    name = database.add_name(request.form['name'])
    return egg()


@app.route('/rate', methods=['POST'])
def rate():
    """
    Rate a name.
    """
    name = request.form['name']
    database.upvote_name(name)
    return vote()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
