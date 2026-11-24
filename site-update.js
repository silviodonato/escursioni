(()=>{'use strict';
const $=id=>document.getElementById(id);let selected=null,busy=false;
async function request(action,extra={}){
 const response=await fetch('aggiorna_sito.cgi',{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json','X-Escursioni-Action':'update-site'},body:JSON.stringify({action,...extra})});
 if(response.status===401)throw Error('La sessione è scaduta. Accedi di nuovo alla gestione.');
 if(response.status===403)throw Error('Aggiornamento disponibile solo dalla rete di casa.');
 if(!response.ok)throw Error('Servizio di aggiornamento non disponibile.');
 const data=await response.json();if(!data.ok||data.error)throw Error(data.message||'Operazione non riuscita.');return data;
}
function show(data){$('site-current').textContent=data.current?data.current.slice(0,12):'Versione iniziale';$('site-rollback').hidden=!data.previous;}
async function run(action){if(busy)return;busy=true;for(const id of ['site-check','site-install','site-rollback'])$(id).disabled=true;$('site-error').textContent='';
 try{if(action==='check'){$('site-status').textContent='Controllo della versione e dei test su GitHub…';const data=await request('check');show(data);selected=data.candidate.sha;const fresh=selected!==data.current;$('site-status').textContent=fresh?'Disponibile: '+selected.slice(0,12)+' · '+data.candidate.title:'Il sito è già aggiornato.';$('site-install').hidden=!fresh;}
 else if(action==='status'){show(await request('status'));$('site-status').textContent='Controlla gli aggiornamenti per vedere l’ultima versione verificata.';}
 else{$('site-status').textContent=action==='install'?'Download e installazione… Attendi il completamento.':'Ripristino della versione precedente…';const data=await request(action,action==='install'?{sha:selected}:{});show(data);$('site-status').textContent=action==='install'?'Sito aggiornato. Premi “Ricarica il sito” per aprire la nuova versione.':'Versione precedente ripristinata. Premi “Ricarica il sito”.';$('site-install').hidden=true;$('site-reload').hidden=false;}}
 catch(error){$('site-status').textContent='';$('site-error').textContent=error.message;}finally{busy=false;for(const id of ['site-check','site-install','site-rollback'])$(id).disabled=false;}}
$('update-site').addEventListener('click',()=>{selected=null;$('site-install').hidden=true;$('site-reload').hidden=true;$('site-dialog').showModal();run('status');});
$('site-check').onclick=()=>run('check');$('site-install').onclick=()=>run('install');$('site-rollback').onclick=()=>run('rollback');$('site-reload').onclick=()=>location.reload();
$('site-dialog').addEventListener('cancel',e=>{if(busy)e.preventDefault();});
})();
