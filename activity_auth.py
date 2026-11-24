"""Validate the NAS owner's password and issue a short, activity-only session."""
from pathlib import Path
from http.cookies import SimpleCookie,CookieError
import os,json,time,secrets,hashlib,re,stat,fcntl,urllib.request,urllib.parse

STATE=Path('/var/services/homes/sdonato/.escursioni-library')
OWNER='sdonato'
COOKIE='escursioni_admin'
TTL=1800
API='http://127.0.0.1:5000/webapi/entry.cgi'

class LoginError(Exception):
    def __init__(self,message,code=401,otp=False):
        super().__init__(message);self.code=code;self.otp=otp

def fingerprint():
    return hashlib.sha256((os.environ.get('REMOTE_ADDR','')+'\0'+os.environ.get('HTTP_USER_AGENT','')).encode()).hexdigest()

def token():
    try:value=SimpleCookie(os.environ.get('HTTP_COOKIE','')).get(COOKIE)
    except CookieError:return None
    value=value.value if value else ''
    return value if re.fullmatch(r'[A-Za-z0-9_-]{43}',value) else None

def session_path(value):
    return STATE/'sessions'/(hashlib.sha256(value.encode()).hexdigest()+'.json')

def valid_session():
    value=token()
    if not value:return False
    try:
        fd=os.open(str(session_path(value)),os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd) as source:
            info=os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid():return False
            data=json.load(source)
        valid=(data.get('owner')==OWNER and data.get('binding')==fingerprint()
               and isinstance(data.get('expires'),(int,float)) and time.time()<data['expires'])
        if not valid:session_path(value).unlink()
        return valid
    except (OSError,ValueError,TypeError):return False

def issue_session():
    folder=STATE/'sessions';folder.mkdir(exist_ok=True)
    if folder.is_symlink():raise OSError('Invalid session folder')
    now=time.time()
    for path in list(folder.glob('*.json'))[:1000]:
        if not path.is_symlink() and path.stat().st_mtime<now-TTL:
            try:path.unlink()
            except OSError:pass
    value=secrets.token_urlsafe(32)
    data={'owner':OWNER,'created':now,'expires':now+TTL,'binding':fingerprint()}
    fd=os.open(str(session_path(value)),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as output:json.dump(data,output)
    return value

def revoke_session():
    value=token()
    if value:
        try:session_path(value).unlink()
        except FileNotFoundError:pass

def cookie_header(value='',clear=False):
    secure='; Secure' if os.environ.get('HTTPS','').lower() in ('on','1') else ''
    return '{}={}; Path=/escursioni/; HttpOnly; SameSite=Strict; Max-Age={}{}'.format(COOKIE,value,0 if clear else TTL,secure)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None

def dsm_api(params):
    payload=urllib.parse.urlencode(dict(api='SYNO.API.Auth',version='6',**params)).encode()
    request=urllib.request.Request(API,data=payload,headers={'Content-Type':'application/x-www-form-urlencoded'})
    with urllib.request.build_opener(NoRedirect()).open(request,timeout=15) as response:
        # Credentials remain in the POST body and are never included in a URL.
        if response.geturl()!=API:raise LoginError('Il servizio di accesso DSM non è disponibile.',503)
        raw=response.read(65537)
    if len(raw)>65536:raise LoginError('Risposta DSM non valida.',503)
    result=json.loads(raw)
    if not isinstance(result,dict):raise LoginError('Risposta DSM non valida.',503)
    return result

def rate_check():
    path=STATE/'login-attempts.json';lock=STATE/'login-attempts.lock'
    fd=os.open(str(lock),os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'r+') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        try:
            with path.open() as source:data=json.load(source)
        except FileNotFoundError:data={}
        now=time.time();key=hashlib.sha256(os.environ.get('REMOTE_ADDR','').encode()).hexdigest()
        data={k:[t for t in v if now-t<300] for k,v in data.items()}
        data={k:v for k,v in data.items() if v}
        attempts=data.setdefault(key,[])
        if len(attempts)>=5:raise LoginError('Troppi tentativi. Attendi cinque minuti e riprova.',429)
        attempts.append(now)
        temporary=path.with_suffix('.tmp')
        with temporary.open('w') as output:json.dump(data,output)
        os.replace(str(temporary),str(path))

def login(password,otp=''):
    if not isinstance(password,str) or not password or len(password)>1024:raise LoginError('Inserisci la password DSM.')
    if not isinstance(otp,str) or len(otp)>16:raise LoginError('Codice di verifica non valido.')
    rate_check()
    params={'method':'login','account':OWNER,'passwd':password,'session':'Escursioni','format':'sid'}
    if otp.strip():params['otp_code']=otp.strip()
    try:result=dsm_api(params)
    except LoginError:raise
    except Exception:raise LoginError('Non riesco a contattare DSM. Riprova tra poco.',503) from None
    if result.get('success') is not True:
        code=(result.get('error') or {}).get('code')
        if code in (403,406):raise LoginError('Inserisci anche il codice di verifica a due fattori.',401,True)
        if code==404:raise LoginError('Codice di verifica non corretto. Riprova.',401,True)
        if code==407:raise LoginError('DSM ha bloccato temporaneamente gli accessi. Controlla le impostazioni DSM.',429)
        if code in (408,409,410):raise LoginError('La password DSM deve essere aggiornata. Accedi prima a DSM.',401)
        raise LoginError('Password non corretta oppure accesso DSM non consentito.')
    sid=(result.get('data') or {}).get('sid')
    if not isinstance(sid,str) or not 1<=len(sid)<=1024:raise LoginError('DSM non ha confermato l’accesso.',503)
    # The DSM session is used only to validate this login, then immediately closed.
    # Neither the password nor the DSM session identifier is saved or returned.
    try:
        ended=dsm_api({'method':'logout','session':'Escursioni','_sid':sid})
        if ended.get('success') is not True:raise ValueError('Logout failed')
    except Exception:raise LoginError('Verifica DSM incompleta. Riprova tra poco.',503) from None
    return issue_session()
