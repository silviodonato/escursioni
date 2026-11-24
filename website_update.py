"""Pinned-repository updater. Installed privately; never updated by web requests.

Only a successful main-branch Tests workflow is eligible. A release is built in
private storage, checked, and activated with one atomic symlink replacement.
The public directory contains individual file links, never a directory link.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.request
import uuid
import zipfile

from activity_config import SETTINGS, SITE, STATE

FILES = (
    'index.html', 'activity.html', 'library.js', 'library.css',
    'activity-tools.js', 'progress.js', 'progress-tools.js', 'analysis-tools.js',
    'comparison.js', 'atlas.js', 'atlas-tools.js', 'efforts.js', 'routes.js',
    'route-tools.js', 'route-worker.js', 'quality.js', 'quality-tools.js',
    'journal.js', 'genera_indice.py', 'activity_metrics.py', 'activity_store.py',
    'activity_auth.py', 'activity_config.py', 'aggiorna_indice.cgi',
    'gestisci_attivita.cgi', 'sessione.cgi', 'site-update.js',
)
LIMIT = 8 * 1024 * 1024
SHA = re.compile(r'[a-f0-9]{40}')


class UpdateError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url, limit=LIMIT):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Escursioni-site-updater', 'Accept': 'application/vnd.github+json'})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=25) as response:
        if response.geturl() != url:
            raise UpdateError('Destinazione di download non valida.')
        body = response.read(limit + 1)
    if len(body) > limit:
        raise UpdateError('Aggiornamento troppo grande.')
    return body


def repository():
    repo = SETTINGS.get('repository', '')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise UpdateError('Repository non configurato.')
    return repo


def candidate():
    api = 'https://api.github.com/repos/' + repository()
    commit = json.loads(fetch(api + '/commits/main', 1024 * 1024))
    sha = commit.get('sha', '')
    if not SHA.fullmatch(sha):
        raise UpdateError('Versione GitHub non valida.')
    runs = json.loads(fetch(api + '/actions/runs?head_sha=' + sha +
                            '&event=push&per_page=100', 2 * 1024 * 1024))
    matching = [r for r in runs.get('workflow_runs', [])
                if r.get('head_sha') == sha and r.get('head_branch') == 'main'
                and r.get('event') == 'push' and r.get('path') == '.github/workflows/tests.yml']
    latest = max(matching, key=lambda r: r.get('run_number', 0)) if matching else {}
    if latest.get('status') != 'completed' or latest.get('conclusion') != 'success':
        raise UpdateError('I test dell’ultima versione non sono ancora riusciti. Riprova più tardi.')
    return {'sha': sha, 'title': str(commit.get('commit', {}).get('message', '')).split('\n')[0][:180]}


def root():
    return STATE / 'site-updates'


def target(link):
    path = root() / link
    if not path.is_symlink():
        return None
    resolved = path.resolve(strict=True)
    if resolved.parent != (root() / 'releases').resolve() or not resolved.is_dir():
        raise UpdateError('Cartella della versione non valida.')
    return resolved


def version(folder):
    return json.loads((folder / 'release.json').read_text(encoding='utf-8'))['sha'] if folder else None


def status():
    return {'current': version(target('current')), 'previous': version(target('previous'))}


def replace_link(name, folder):
    temporary = root() / ('.' + name + '-' + uuid.uuid4().hex)
    try:
        temporary.symlink_to(folder)
        os.replace(str(temporary), str(root() / name))
    finally:
        if temporary.is_symlink():
            temporary.unlink()


@contextmanager
def locked():
    # Same lock as index generation and rename/trash, so code cannot change
    # underneath a running management operation.
    key = hashlib.sha256(str(SITE).encode()).hexdigest()[:16]
    lock = Path(tempfile.gettempdir()) / ('escursioni-{}-{}.lock'.format(os.getuid(), key))
    fd = os.open(str(lock), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as handle:
        info = os.fstat(handle.fileno())
        if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise UpdateError('Blocco di aggiornamento non valido.')
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise UpdateError('Un’operazione è già in corso. Riprova tra poco.')
        yield


def unpack(raw, folder):
    extracted = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if len(entries) > 1000 or sum(e.file_size for e in entries) > 24 * 1024 * 1024:
            raise UpdateError('Archivio troppo grande.')
        roots = set()
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in entry.filename
                    or stat.S_ISLNK(entry.external_attr >> 16) or not path.parts):
                raise UpdateError('Percorso nell’archivio non valido.')
            roots.add(path.parts[0])
            if len(roots) != 1:
                raise UpdateError('Struttura dell’archivio non valida.')
            if len(path.parts) != 2 or path.name not in FILES or entry.is_dir():
                continue
            name = path.name
            if name in extracted or entry.file_size > 2 * 1024 * 1024:
                raise UpdateError('File duplicato o troppo grande.')
            body = archive.read(entry)
            if name.endswith(('.py', '.cgi')):
                compile(body, name, 'exec')
            elif name.endswith('.html') and b'<!doctype html>' not in body[:100].lower():
                raise UpdateError('Pagina HTML non valida.')
            destination = folder / name
            destination.write_bytes(body)
            destination.chmod(0o755 if name.endswith('.cgi') else 0o644)
            extracted[name] = hashlib.sha256(body).hexdigest()
    if set(extracted) != set(FILES):
        raise UpdateError('La versione non contiene tutti i file necessari.')
    return extracted


def verify(folder):
    metadata = json.loads((folder / 'release.json').read_text(encoding='utf-8'))
    hashes = metadata.get('files', {})
    if set(hashes) != set(FILES):
        raise UpdateError('Manifesto della versione non valido.')
    for name, digest in hashes.items():
        path = folder / name
        if not stat.S_ISREG(path.lstat().st_mode) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise UpdateError('La verifica dei file non è riuscita.')


def install(expected_sha):
    if not isinstance(expected_sha, str) or not SHA.fullmatch(expected_sha):
        raise UpdateError('Scegli prima una versione da installare.')
    selected = candidate()
    if selected['sha'] != expected_sha:
        raise UpdateError('È disponibile una versione diversa. Controlla di nuovo gli aggiornamenti.')
    current = target('current')
    if not current:
        raise UpdateError('Installazione iniziale non completata.')
    if version(current) == expected_sha:
        return dict(status(), changed=False)
    raw = fetch('https://codeload.github.com/' + repository() + '/zip/' + expected_sha)
    folder = root() / 'releases' / (expected_sha + '-' + uuid.uuid4().hex[:8])
    folder.mkdir(mode=0o755)
    activated = False
    try:
        hashes = unpack(raw, folder)
        (folder / 'site_config.json').write_text(json.dumps(SETTINGS), encoding='utf-8')
        (folder / 'site_config.json').chmod(0o600)
        (folder / 'release.json').write_text(json.dumps(dict(selected, files=hashes)), encoding='utf-8')
        verify(folder)
        # Import the candidate generator with this NAS's Python. --help exits
        # before reading or writing any activity data.
        result = subprocess.run(['/usr/bin/python3', str(folder / 'genera_indice.py'), '--help'],
                                cwd=str(folder), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
                                env={'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'})
        if result.returncode:
            raise UpdateError('La nuova versione non è compatibile con Python sul NAS.')
        replace_link('previous', current)
        replace_link('current', folder)
        activated = True
        # A failed final integrity check restores the original active version.
        verify(target('current'))
        return dict(status(), changed=True)
    except BaseException:
        if activated:
            replace_link('current', current)
        shutil.rmtree(str(folder))
        raise


def rollback():
    previous = target('previous')
    if not previous:
        raise UpdateError('Non c’è una versione precedente da ripristinare.')
    verify(previous)
    current = target('current')
    replace_link('current', previous)
    replace_link('previous', current)
    return dict(status(), changed=True)
