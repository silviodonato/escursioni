(function(){'use strict';
const $=id=>document.getElementById(id),A=AnalysisTools,K=ActivityTools.KINDS;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const COLORS=['#286d61','#b76031','#5967a9'];
function download(rows,options,name){const url=URL.createObjectURL(new Blob([A.csv(rows,options)],{type:'text/csv;charset=utf-8'})),link=document.createElement('a');link.href=url;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
window.ActivityComparison={download,create({label,date,number,duration,viewerLink,onChange,initialFiles=[]}){
 let selected=[...new Set(initialFiles)].slice(0,3),all=[],map=null,layers=null;
 const chosen=()=>selected.map(file=>all.find(t=>t.file===file)).filter(Boolean);
 function drawBar(){const items=chosen();$('comparison-bar').hidden=!items.length;document.body.classList.toggle('comparison-active',items.length>0);$('compare-status').textContent=items.length+' di 3 attività selezionate';$('open-comparison').disabled=items.length<2;$('compare-selection').innerHTML=items.map((t,i)=>`<button class="compare-tag" data-remove-comparison="${esc(t.file)}" title="${esc(label(t))}" aria-label="Rimuovi dal confronto ${esc(label(t))}"><i style="background:${COLORS[i]}"></i><span>${esc(label(t))}</span><span aria-hidden="true">×</span></button>`).join('');}
 $('compare-selection').onclick=e=>{const b=e.target.closest('[data-remove-comparison]');if(b){selected=selected.filter(f=>f!==b.dataset.removeComparison);onChange();}};
 $('clear-comparison').onclick=()=>{selected=[];onChange();};
 function showMap(items){
  const routes=items.map(A.routes),missing=routes.filter(r=>!r.length).length,hasAny=missing<items.length;
  $('comparison-map').hidden=!hasAny;
  if(!hasAny){$('comparison-map-note').textContent='Le attività selezionate non contengono percorsi GPS visualizzabili.';return;}
  if(typeof L==='undefined'){$('comparison-map').hidden=true;$('comparison-map-note').textContent='Mappa temporaneamente non disponibile. Puoi comunque confrontare tutti i dati.';return;}
  try{
   if(!map){map=L.map('comparison-map',{scrollWheelZoom:false});L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}).addTo(map);layers=L.featureGroup().addTo(map);}
   layers.clearLayers();
   routes.forEach((parts,i)=>parts.forEach(segment=>{L.polyline(segment,{color:COLORS[i],weight:4,opacity:.8}).addTo(layers);L.circleMarker(segment[0],{radius:4,color:COLORS[i],fillOpacity:1}).addTo(layers);}));
   map.invalidateSize();map.fitBounds(layers.getBounds(),{padding:[20,20],maxZoom:16});
   $('comparison-map-note').textContent='Percorsi semplificati, nello stesso colore delle colonne. Il punto indica l’inizio di ogni segmento.'+(missing?' '+missing+' attività senza percorso GPS.':'');
  }catch(e){$('comparison-map').hidden=true;$('comparison-map-note').textContent='Non è stato possibile mostrare la mappa. I dati del confronto restano disponibili.';}
 }
 function drawComparison(){const items=chosen();
  const value=(t,key,decimals=0,u='')=>{const n=A.numeric(t[key]);return n===null?'—':number(n,decimals)+(u?' '+u:'');};
  const pace=t=>{const seconds=A.pace(t);if(seconds===null)return '—';const rounded=Math.round(seconds);return Math.floor(rounded/60)+':'+String(rounded%60).padStart(2,'0')+' min/km';};
  const elapsed=t=>{const n=A.numeric(t.dur_s);if(n===null)return '—';const seconds=Math.round(n);return [Math.floor(seconds/3600),Math.floor(seconds%3600/60),seconds%60].map(v=>String(v).padStart(2,'0')).join(':');};
  const measures=[['Data',t=>esc(date(t.date))],['Disciplina',t=>esc(K[t.kind]||K.other)],['Distanza',t=>value(t,'km',1,'km')],['Dislivello positivo',t=>value(t,'gain',0,'m')],['Durata totale',elapsed],['Velocità su tempo totale',t=>A.speed(t)===null?'—':number(A.speed(t),1)+' km/h'],['Passo su tempo totale',pace]];
  $('comparison-table').innerHTML='<caption class="sr-only">Confronto delle attività selezionate</caption><thead><tr><th scope="col">Misura</th>'+items.map((t,i)=>`<th scope="col"><span class="comparison-color" style="background:${COLORS[i]}"></span><a href="${esc(viewerLink(t))}">${esc(label(t))}</a></th>`).join('')+'</tr></thead><tbody>'+measures.map(([title,format])=>`<tr><th scope="row">${title}</th>${items.map(t=>'<td>'+format(t)+'</td>').join('')}</tr>`).join('')+'</tbody>';
  const kinds=new Set(items.map(t=>t.kind||'other'));$('comparison-discipline-note').textContent=kinds.size>1?'Hai selezionato discipline diverse: tempi e velocità vanno letti nel contesto di ciascuna attività.':'Percorsi, terreno e soste possono cambiare: i valori descrivono ciascuna uscita.';
  $('compare-dialog').showModal();showMap(items);
 }
 $('open-comparison').onclick=()=>{if(chosen().length>=2)drawComparison();};
 $('export-comparison').onclick=()=>download(chosen(),{label,kind:t=>K[t.kind]||K.other},'confronto-attivita.csv');
 return {openFiles(files){selected=[...new Set(files)].filter(f=>all.some(t=>t.file===f)).slice(0,3);onChange();if(chosen().length>=2)drawComparison();},get files(){return selected.slice();},update(tracks){all=tracks;const names=new Set(all.map(t=>t.file));selected=selected.filter(file=>names.has(file));drawBar();},toggle(file,checked){if(!all.some(t=>t.file===file))return false;if(checked&&!selected.includes(file)){if(selected.length===3){$('compare-status').textContent='Puoi confrontare al massimo 3 attività. Rimuovine una per cambiarla.';return false;}selected.push(file);}else if(!checked)selected=selected.filter(f=>f!==file);onChange();return true;}};
}};
})();
