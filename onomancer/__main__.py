from flask import Flask, request
from onomancer import database

# why use many file when one file do
app = Flask(__name__)

@app.route('/')
def index():
    return 'Hello world!'


@app.route('/pool')
def pool():
    """
    Return pool of all names
    """
    return []


@app.route('/leaderboard')
def leaderboard():
    return database.get_leaders(top=20)


@app.route('/submit', methods=['POST'])
def submit():
    """
    Submit one name.
    """
    name = database.add_name(request.form['name'])
    return name


@app.route('/rate', methods=['POST'])
def rate():
    """
    Rate a name.
    """
    return '+1'


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
