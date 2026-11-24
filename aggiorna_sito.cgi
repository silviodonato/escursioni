#!/usr/bin/python3
"""Local authenticated website updates; no user-selected URLs or commands."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys
import urllib.error

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
loader = importlib.machinery.SourceFileLoader('website_guard', str(HERE / 'aggiorna_indice.cgi'))
spec = importlib.util.spec_from_loader(loader.name, loader)
guard = importlib.util.module_from_spec(spec)
loader.exec_module(guard)
import website_update as updates


def main():
    if os.environ.get('REQUEST_METHOD') != 'POST':
        guard.reply(405, 'Usa il pulsante Aggiorna sito.')
        return
    if not guard.direct_lan_request() or not guard.same_origin_request('update-site'):
        guard.reply(403, 'Aggiornamento disponibile solo dalla rete di casa.')
        return
    try:
        if not guard.authenticated_owner():
            guard.reply(401, 'Accedi alla gestione, poi riprova.')
            return
        if os.environ.get('CONTENT_TYPE', '').split(';')[0] != 'application/json':
            raise updates.UpdateError('Richiesta non valida.')
        length = int(os.environ.get('CONTENT_LENGTH', '0'))
        if not 0 < length <= 256:
            raise updates.UpdateError('Richiesta non valida.')
        data = json.loads(sys.stdin.read(length))
        if not isinstance(data, dict) or set(data) - {'action', 'sha'}:
            raise updates.UpdateError('Richiesta non valida.')
        with updates.locked():
            action = data.get('action')
            if action == 'status':
                result = updates.status()
            elif action == 'check':
                result = dict(updates.status(), candidate=updates.candidate())
            elif action == 'install':
                result = updates.install(data.get('sha'))
            elif action == 'rollback':
                result = updates.rollback()
            else:
                raise updates.UpdateError('Azione non valida.')
        guard.reply(200, 'Operazione completata.', **result)
    except (updates.UpdateError, ValueError, TypeError) as error:
        # Keep useful messages through DSM's error-page interception.
        guard.reply(200, str(error), error=True)
    except urllib.error.HTTPError as error:
        print('Website update GitHub HTTP {}'.format(error.code), file=sys.stderr)
        guard.reply(200, 'GitHub non è disponibile o il repository non è pubblico. Nessuna modifica applicata.', error=True)
    except Exception as error:
        print('Website update failed: {}'.format(type(error).__name__), file=sys.stderr)
        guard.reply(200, 'Aggiornamento non riuscito. La versione precedente resta disponibile.', error=True)


if __name__ == '__main__':
    main()
