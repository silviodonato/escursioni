#!/usr/bin/python3
"""Regenerate this site's fixed GPX index for the authenticated DSM owner."""
import fcntl
import hashlib
from http.cookies import SimpleCookie, CookieError
import ipaddress
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

RUNTIME = Path(__file__).resolve().parent
sys.path.insert(0, str(RUNTIME))
from activity_config import SITE, OWNER, HOSTS, NETWORKS
HERE = SITE
AUTHENTICATOR = '/usr/syno/synoman/webman/modules/authenticate.cgi'


def reply(status, message, **extra):
    reasons = {200: 'OK', 400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden',
               405: 'Method Not Allowed', 409: 'Conflict',
               500: 'Internal Server Error', 504: 'Gateway Timeout'}
    print('Status: {} {}'.format(status, reasons[status]))
    print('Content-Type: application/json; charset=utf-8')
    print('Cache-Control: no-store')
    print('X-Content-Type-Options: nosniff')
    print('Content-Security-Policy: default-src \'none\'')
    if status == 405:
        print('Allow: POST')
    print()
    print(json.dumps(dict(ok=status == 200, message=message, **extra),
                     ensure_ascii=True))


def same_origin_request(expected_action='update-index'):
    host = os.environ.get('HTTP_HOST', '').lower()
    origin = os.environ.get('HTTP_ORIGIN', '')
    try:
        parsed = urlsplit(origin)
        return (parsed.scheme in ('http', 'https')
                and parsed.hostname in HOSTS
                and parsed.netloc.lower() == host
                and not parsed.path and not parsed.query and not parsed.fragment
                and os.environ.get('HTTP_X_ESCURSIONI_ACTION') == expected_action)
    except ValueError:
        return False


def direct_lan_request():
    # Funnel and Serve add forwarded headers; neither is an admin entry point.
    # The NAS nginx passes its own validated client address as REMOTE_ADDR.
    if any(os.environ.get(name) for name in
           ('HTTP_X_FORWARDED_FOR', 'HTTP_X_FORWARDED_HOST', 'HTTP_FORWARDED')):
        return False
    try:
        address = ipaddress.ip_address(os.environ.get('REMOTE_ADDR', ''))
        return any(address in network for network in NETWORKS) or (bool(NETWORKS) and address.is_loopback)
    except ValueError:
        return False


def authenticated_owner():
    from activity_auth import valid_session
    if valid_session():
        return True
    try:
        cookies = SimpleCookie(os.environ.get('HTTP_COOKIE', ''))
        if not cookies.get('id') or not cookies['id'].value:
            return False
    except CookieError:
        return False
    result = subprocess.run([AUTHENTICATOR], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            timeout=5)
    return result.returncode == 0 and result.stdout.strip() == OWNER.encode('utf-8')


def regenerate():
    # Keep the lock outside the public site and refuse symlinks or foreign files.
    key = hashlib.sha256(str(HERE).encode('utf-8')).hexdigest()[:16]
    lock = Path(tempfile.gettempdir()) / ('escursioni-{}-{}.lock'.format(os.getuid(), key))
    fd = os.open(str(lock), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as handle:
        info = os.fstat(handle.fileno())
        if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise PermissionError('Unsafe lock file')
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            reply(409, 'Un aggiornamento è già in corso. Riprova tra poco.')
            return
        result = subprocess.run(
            ['/usr/bin/python3', str(HERE / 'genera_indice.py'), '--json', '--web-acl',
             '--max-files', '20', '--max-seconds', '20'],
            cwd=str(HERE), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={'PATH': '/usr/bin:/bin', 'LANG': 'en_US.UTF-8'},
            encoding='utf-8', errors='replace', timeout=120)
        if result.returncode:
            print('Index generator failed: ' + result.stderr[-2000:], file=sys.stderr)
            reply(500, 'Non è stato possibile aggiornare l’indice. Controlla i permessi sul NAS.')
            return
        with (HERE / 'tracce' / 'index.json').open(encoding='utf-8') as index:
            tracks = json.load(index)
        if not isinstance(tracks, list):
            raise ValueError('Invalid index')
        summary = json.loads(result.stdout)
        reply(200, 'Indice aggiornato.' if summary['written'] else 'Nessuna modifica.',
              count=len(tracks), processed=summary['processed'], reused=summary['reused'],
              removed=summary['removed'], errors=summary['errors'], written=summary['written'],
              pending=summary.get('pending', 0))


def main():
    if os.environ.get('REQUEST_METHOD') != 'POST':
        reply(405, 'Usa il pulsante Aggiorna indice nella pagina delle escursioni.')
        return
    if not direct_lan_request() or not same_origin_request():
        reply(403, 'Aggiornamento disponibile solo dalla rete di casa su l’indirizzo locale configurato.')
        return
    try:
        if not authenticated_owner():
            reply(401, 'Accedi alla gestione con l’account proprietario, poi riprova.')
            return
        regenerate()
    except subprocess.TimeoutExpired:
        reply(504, 'Il NAS non ha risposto in tempo. Riprova tra poco.')
    except Exception as error:
        print('Index update error: {}'.format(error), file=sys.stderr)
        reply(500, 'Aggiornamento non disponibile. Controlla la configurazione del NAS.')


if __name__ == '__main__':
    main()
