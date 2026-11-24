"""Private metadata and reversible activity management. Python 3.8 / DSM."""
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone
import os, json, hashlib, stat, tempfile, fcntl, uuid, shutil

STATE = Path('/var/services/homes/sdonato/.escursioni-library')
KINDS = {'hiking':'Escursione','walking':'Camminata','running':'Corsa','cycling':'Ciclismo',
         'swimming':'Nuoto','skiing':'Sci','kayaking':'Kayak','sup':'SUP','surfing':'Surf',
         'elliptical':'Ellittica','workout':'Allenamento generico','other':'Altro'}

class Conflict(ValueError):
    pass

def read_json(path, default):
    try:
        with path.open(encoding='utf-8') as source:return json.load(source)
    except FileNotFoundError:return default

def write_json(path, data):
    temp=path.with_name(path.name+'.tmp')
    with temp.open('w',encoding='utf-8') as output:
        json.dump(data,output,ensure_ascii=False,separators=(',',':'));output.flush();os.fsync(output.fileno())
    os.replace(str(temp),str(path))

def overrides():
    data=read_json(STATE/'metadata.json',{})
    if not isinstance(data,dict):raise ValueError('Metadati non validi')
    return data

def infer_kind(entry):
    sport=str(entry.get('sport') or '').lower()
    mapping={'hike':'hiking','hiking':'hiking','walking':'walking','walk':'walking','running':'running',
             'run':'running','biking':'cycling','cycling':'cycling','bike':'cycling','swimming':'swimming',
             'swim':'swimming','skiing':'skiing','ski':'skiing','alpineski':'skiing',
             'kayaking':'kayaking','kayak':'kayaking','ride':'cycling',
             'standuppaddling':'sup','surfing':'surfing','elliptical':'elliptical','workout':'workout'}
    if sport in mapping:return mapping[sport]
    name=(entry.get('name') or '').lower()
    if 'kayak' in name:return 'kayaking'
    return 'other'

def decorate(entries, custom=None):
    custom=overrides() if custom is None else custom
    for entry in entries:
        change=custom.get(entry['file'],{})
        if change.get('name'):entry['display_name']=change['name']
        else:entry.pop('display_name',None)
        entry['kind']=change.get('kind') if change.get('kind') in KINDS else infer_kind(entry)
    return entries

@contextmanager
def site_lock(here):
    key=hashlib.sha256(str(here).encode()).hexdigest()[:16]
    path=Path(tempfile.gettempdir())/('escursioni-{}-{}.lock'.format(os.getuid(),key))
    fd=os.open(str(path),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'r+') as handle:
        info=os.fstat(handle.fileno())
        if info.st_uid!=os.getuid() or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise PermissionError('Unsafe lock')
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise Conflict('Un aggiornamento è già in corso. Riprova tra poco.')
        yield

def safe_name(name):
    if not isinstance(name,str) or not name or name in ('.','..') or '/' in name or '\\' in name or '\x00' in name:
        raise ValueError('Nome file non valido')
    if Path(name).suffix.lower() not in ('.gpx','.tcx','.fit'):raise ValueError('Formato non supportato')
    return name

def journal():
    data=read_json(STATE/'journal.json',{})
    if not isinstance(data,dict):raise ValueError('Diario privato non valido')
    return data

def edit_journal(generator,file,favorite,notes,tags):
    file=safe_name(file)
    if not any(e['file']==file for e in index(generator)):raise Conflict('Attività non trovata. Aggiorna l’elenco.')
    regular(Path(generator.TRACCE)/file)
    if not isinstance(favorite,bool):raise ValueError('Preferito non valido')
    if not isinstance(notes,str) or len(notes)>4000 or any((ord(c)<32 and c not in '\r\n\t') or 0xd800<=ord(c)<=0xdfff for c in notes):
        raise ValueError('Le note possono contenere al massimo 4000 caratteri')
    if not isinstance(tags,list) or len(tags)>12:raise ValueError('Puoi usare al massimo 12 etichette')
    clean=[];seen=set()
    for tag in tags:
        if not isinstance(tag,str) or not 1<=len(tag.strip())<=32 or any(ord(c)<32 or 0xd800<=ord(c)<=0xdfff for c in tag):
            raise ValueError('Etichette non valide: usa da 1 a 32 caratteri')
        tag=tag.strip()
        if tag.casefold() not in seen:clean.append(tag);seen.add(tag.casefold())
    data=journal();record=dict(favorite=favorite,notes=notes.strip(),tags=clean)
    if favorite or record['notes'] or clean:data[file]=record
    else:data.pop(file,None)
    write_json(STATE/'journal.json',data)
    return {'file':file,'journal_entry':record}

def regular(path):
    if not stat.S_ISREG(path.lstat().st_mode):raise ValueError('File non valido')

def index(generator):
    entries=read_json(Path(generator.OUT),[])
    if not isinstance(entries,list):raise ValueError('Indice non valido')
    return entries

def save_index(generator,entries):
    decorate(entries)
    entries.sort(key=lambda e:e.get('date') or '',reverse=True)
    generator.write_index(entries,web_acl=True)

def edit(generator, file, name, kind):
    file=safe_name(file)
    if not isinstance(name,str) or not 1<=len(name.strip())<=160 or any(ord(c)<32 for c in name):
        raise ValueError('Inserisci un nome da 1 a 160 caratteri')
    if kind not in KINDS:raise ValueError('Tipo di attività non valido')
    entries=index(generator)
    if not any(e['file']==file for e in entries):raise Conflict('Attività non trovata. Aggiorna l’elenco.')
    regular(Path(generator.TRACCE)/file)
    custom=overrides();previous=dict(custom);custom[file]={'name':name.strip(),'kind':kind}
    write_json(STATE/'metadata.json',custom)
    try:save_index(generator,entries)
    except Exception:
        write_json(STATE/'metadata.json',previous);raise
    return {'file':file,'name':name.strip(),'kind':kind}

def trash(generator,file):
    file=safe_name(file);entries=index(generator)
    if not any(e['file']==file for e in entries):raise Conflict('Attività non trovata. Aggiorna l’elenco.')
    tracks=Path(generator.TRACCE);stem=Path(file).stem.casefold()
    files=sorted(p for p in tracks.iterdir() if p.suffix.lower() in ('.gpx','.tcx','.fit') and p.stem.casefold()==stem)
    for path in files:regular(path)
    folder=STATE/'trash'/uuid.uuid4().hex;folder.mkdir()
    manifest={'id':folder.name,'state':'prepared','deleted_at':datetime.now(timezone.utc).isoformat(),
              'files':[], 'entries':[e for e in entries if Path(e['file']).stem.casefold()==stem]}
    for path in files:
        raw,info=generator.read_snapshot(str(path))
        manifest['files'].append({'name':path.name,'sha256':hashlib.sha256(raw).hexdigest(),'metadata':generator.metadata(info)})
    write_json(folder/'manifest.json',manifest);moved=[]
    try:
        for record in manifest['files']:
            source=tracks/record['name']
            if generator.metadata(source.stat())!=record['metadata']:raise Conflict('Il file è cambiato. Aggiorna l’indice e riprova.')
            shutil.move(str(source),str(folder/record['name']));moved.append(record['name'])
        manifest['state']='deleted';write_json(folder/'manifest.json',manifest)
        save_index(generator,[e for e in entries if Path(e['file']).stem.casefold()!=stem])
    except Exception:
        for name in reversed(moved):
            if not (tracks/name).exists():shutil.move(str(folder/name),str(tracks/name))
        if not any((folder/r['name']).exists() for r in manifest['files']):shutil.rmtree(str(folder))
        raise
    return {'id':folder.name,'files':len(files)}

def trash_items():
    items=[]
    for folder in (STATE/'trash').iterdir():
        if not folder.is_dir() or folder.is_symlink():continue
        data=read_json(folder/'manifest.json',{})
        if data.get('state')!='deleted':continue
        entry=dict((data.get('entries') or [{}])[0]);entry['id']=folder.name;entry['deleted_at']=data['deleted_at']
        items.append({k:entry.get(k) for k in ('id','file','display_name','name','date','km','kind','deleted_at')})
    return sorted(items,key=lambda e:e['deleted_at'],reverse=True)

def restore(generator,trash_id):
    if not isinstance(trash_id,str) or len(trash_id)!=32 or any(c not in '0123456789abcdef' for c in trash_id):raise ValueError('Cestino non valido')
    folder=STATE/'trash'/trash_id
    if folder.is_symlink():raise ValueError('Cestino non valido')
    data=read_json(folder/'manifest.json',{})
    if data.get('state')!='deleted':raise Conflict('Attività non presente nel cestino')
    tracks=Path(generator.TRACCE)
    for record in data['files']:
        name=safe_name(record['name']);regular(folder/name)
        if (tracks/name).exists() or (tracks/name).is_symlink():raise Conflict('Un file con lo stesso nome esiste già. Nessun file è stato sovrascritto.')
        raw,_=generator.read_snapshot(str(folder/name))
        if hashlib.sha256(raw).hexdigest()!=record['sha256']:raise Conflict('Il file nel cestino è cambiato. Controllalo sul NAS prima di ripristinarlo.')
    old=index(generator);moved=[]
    try:
        for record in data['files']:
            name=record['name'];shutil.move(str(folder/name),str(tracks/name));moved.append(name)
        restored=[]
        for saved in data['entries']:
            entry=dict(saved);raw,info=generator.read_snapshot(str(tracks/entry['file']))
            entry.update(generator.metadata(info));entry['sha256']=hashlib.sha256(raw).hexdigest();restored.append(entry)
        names={e['file'] for e in restored};save_index(generator,[e for e in old if e['file'] not in names]+restored)
    except Exception:
        for name in reversed(moved):
            if not (folder/name).exists():shutil.move(str(tracks/name),str(folder/name))
        raise
    shutil.rmtree(str(folder))
    return {'files':len(moved)}
