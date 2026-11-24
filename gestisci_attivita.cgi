#!/usr/bin/python3
"""Fixed, owner-authenticated library actions; no shell commands from user input."""
import os,sys,json,importlib.machinery,importlib.util,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
loader=importlib.machinery.SourceFileLoader('index_auth',str(HERE/'aggiorna_indice.cgi'))
spec=importlib.util.spec_from_loader(loader.name,loader);auth=importlib.util.module_from_spec(spec);loader.exec_module(auth)
import activity_store as store
import genera_indice as generator

def main():
    if os.environ.get('REQUEST_METHOD')!='POST':auth.reply(405,'Usa i pulsanti della raccolta attività.');return
    if not auth.direct_lan_request() or not auth.same_origin_request('manage-activity'):
        auth.reply(403,'Gestione disponibile solo dalla rete di casa sull’indirizzo locale configurato.');return
    try:
        if not auth.authenticated_owner():auth.reply(401,'Accedi alla gestione con l’account proprietario, poi riprova.');return
        if os.environ.get('CONTENT_TYPE','').split(';')[0]!='application/json':raise ValueError('Richiesta non valida')
        length=int(os.environ.get('CONTENT_LENGTH','0'))
        if not 0<length<=24576:raise ValueError('Richiesta troppo grande o vuota')
        data=json.loads(sys.stdin.read(length))
        if not isinstance(data,dict):raise ValueError('Richiesta non valida')
        action=data.get('action')
        with store.site_lock(auth.HERE):
            ready=(store.STATE/'trash').is_dir()
            if action!='status' and not ready:raise store.Conflict('La gestione non è ancora disponibile.')
            if action=='status':result={'ready':ready,'trash':store.trash_items() if ready else [],'journal':store.journal() if ready else {}}
            elif action=='journal_edit':result=store.edit_journal(generator,data.get('file'),data.get('favorite'),data.get('notes'),data.get('tags'))
            elif action=='edit':result=store.edit(generator,data.get('file'),data.get('name'),data.get('kind'))
            elif action=='trash':result=store.trash(generator,data.get('file'))
            elif action=='restore':result=store.restore(generator,data.get('id'))
            else:raise ValueError('Azione non valida')
        auth.reply(200,'Modifiche salvate.',**result)
    except store.Conflict as error:auth.reply(409,str(error))
    except (ValueError,TypeError) as error:auth.reply(400,str(error))
    except subprocess.TimeoutExpired:auth.reply(504,'Il NAS non ha risposto in tempo. Riprova.')
    except Exception as error:
        print('Activity management error: {}'.format(error),file=sys.stderr)
        auth.reply(500,'Operazione non riuscita. I file nel cestino restano recuperabili sul NAS.')
if __name__=='__main__':main()
