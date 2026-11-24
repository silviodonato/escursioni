#!/usr/bin/python3
"""Same-origin, local-only sign-in to activity management."""
import os,sys,json,importlib.machinery,importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import activity_auth as sessions
loader=importlib.machinery.SourceFileLoader('session_guard',str(HERE/'aggiorna_indice.cgi'));spec=importlib.util.spec_from_loader(loader.name,loader);guard=importlib.util.module_from_spec(spec);loader.exec_module(guard)

def reply(status,message,cookie=None,**extra):
    reasons={200:'OK',400:'Bad Request',401:'Unauthorized',403:'Forbidden',405:'Method Not Allowed',429:'Too Many Requests',500:'Internal Server Error',503:'Service Unavailable'}
    # Validation errors use a JSON envelope so DSM nginx's error-page interception
    # cannot replace the useful login/OTP message with an HTML page.
    transport=status if status in (403,405) else 200
    print('Status: {} {}'.format(transport,reasons[transport]))
    print('Content-Type: application/json; charset=utf-8\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff')
    print("Content-Security-Policy: default-src 'none'")
    if cookie:print('Set-Cookie: '+cookie)
    print();print(json.dumps(dict(ok=status==200,code=status,message=message,**extra),ensure_ascii=True))

def main():
    if os.environ.get('REQUEST_METHOD')!='POST':reply(405,'Usa il pulsante Gestisci attività.');return
    if not guard.direct_lan_request() or not guard.same_origin_request('activity-login'):
        reply(403,'Accesso disponibile solo dalla rete di casa sull’indirizzo locale configurato.');return
    try:
        if os.environ.get('CONTENT_TYPE','').split(';')[0]!='application/json':raise ValueError()
        length=int(os.environ.get('CONTENT_LENGTH','0'))
        if not 0<length<=4096:raise ValueError()
        data=json.loads(sys.stdin.read(length))
        if not isinstance(data,dict):raise ValueError()
        if data.get('action')=='capabilities':
            reply(200,'Gestione disponibile.',management=bool(sessions.OWNER))
        elif data.get('action')=='login':
            value=sessions.login(data.get('password'),data.get('otp',''))
            reply(200,'Accesso riuscito.',cookie=sessions.cookie_header(value),expires_in=sessions.TTL)
        elif data.get('action')=='logout':
            sessions.revoke_session();reply(200,'Sei uscito dalla gestione.',cookie=sessions.cookie_header(clear=True))
        else:reply(400,'Richiesta non valida.')
    except sessions.LoginError as error:reply(error.code,str(error),otp_required=error.otp)
    except (ValueError,TypeError):reply(400,'Richiesta non valida.')
    except Exception:
        print('Activity sign-in service error',file=sys.stderr)
        reply(503,'Accesso temporaneamente non disponibile. Riprova tra poco.')
if __name__=='__main__':main()
