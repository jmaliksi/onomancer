import sys
from onomancer.app import app as application

if __name__ == '__main__':
    debug = False
    if 'test' in sys.argv:
        debug = True
        application.wsgi_app.url_scheme = 'http'
    application.run(host='0.0.0.0', port=5001, debug=debug)
