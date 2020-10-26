from flask import Flask

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
    return 'leaderboard'


@app.route('/submit')
def submit():
    """
    Submit one name.
    """
    return 'name'


@app.route('/rate')
def rate():
    """
    Rate a name.
    """
    return '+1'


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
