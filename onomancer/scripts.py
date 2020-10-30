import secrets
import random
import sys


def generate_csrf_key():
    with open('data/csrf.key', 'w') as f:
        key = ''
        encoding = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'
        length = random.randint(40, 50)
        for _ in range(length):
            key += random.choice(encoding)
        f.write(key)


def generate_mod_key():
    with open('data/mod.key', 'w') as f:
        sec = secrets.token_urlsafe(32)
        f.write(sec)
    print(sec)


if __name__ == '__main__':
    if 'generate_csrf_key' in sys.argv:
        generate_csrf_key()
    if 'generate_mod_key' in sys.argv:
        generate_mod_key()
