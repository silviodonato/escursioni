/* Progress dashboard; reads the same index as the library. */
(function(){'use strict';
const $=id=>document.getElementById(id),P=ProgressTools,K=ActivityTools.KINDS;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const GOAL_KEY='escursioni.monthlyGoal.v1';
window.ActivityProgress={create(options){
 const {label,date,number,duration,viewerLink,onChange}=options;
 const VIEWS=['list','atlas','efforts','routes','progress','quality'];
 let view=VIEWS.includes(options.initialView)?options.initialView:'list',state=null,calendarMonth=P.dayKey(new Date()).slice(0,7),lastRange=null,yearSignature='',goal=null;
 const monthName=key=>new Date(key+'-01T12:00:00').toLocaleDateString('it-IT',{month:'long',year:'numeric'});
 const metricValue=(value,key)=>key==='dur_s'?number(value/3600,1):number(value,key==='km'?1:0);
 const unit=key=>({km:'km',gain:'m',dur_s:'ore',count:'attività'})[key];
 function validGoal(value){return value&&['km','gain','hours','count'].includes(value.metric)&&Number.isFinite(value.target)&&value.target>0&&value.target<=1000000&&(value.kind===''||Object.hasOwn(K,value.kind));}
 try{const saved=JSON.parse(localStorage.getItem(GOAL_KEY));if(validGoal(saved))goal=saved;}catch(e){}
 function showView(next,notify=true){view=next;for(const name of VIEWS){const selected=name===view,button=$('view-'+name);button.setAttribute('aria-selected',String(selected));button.tabIndex=selected?0:-1;} for(const name of VIEWS)$(name==='list'?'activity-panel':name+'-panel').hidden=view!==name;if(notify)onChange();}
 function selectRange(from,to,list=false){$('from-date').value=from;$('to-date').value=to;if(list)showView('list',false);onChange();if(list){$('list-title').tabIndex=-1;$('list-title').focus({preventScroll:true});$('activity-panel').scrollIntoView({block:'start'});}}
 function quickRange(kind){const today=P.dayKey(new Date());if(kind==='all')return {from:'',to:''};if(kind==='year')return {from:today.slice(0,4)+'-01-01',to:today.slice(0,4)+'-12-31'};if(kind==='month')return P.monthRange(today.slice(0,7));const day=new Date(today+'T12:00:00').getDay();return {from:P.shiftDay(today,-((day+6)%7)),to:today};}
 for(const name of VIEWS){
  $('view-'+name).onclick=()=>showView(name);
  $('view-'+name).onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const index=VIEWS.indexOf(view),next=e.key==='Home'?VIEWS[0]:e.key==='End'?VIEWS[VIEWS.length-1]:VIEWS[(index+(e.key==='ArrowRight'?1:-1)+VIEWS.length)%VIEWS.length];showView(next);$('view-'+next).focus();}};
 }
 document.querySelectorAll('[data-period]').forEach(b=>b.onclick=()=>{const r=quickRange(b.dataset.period);selectRange(r.from,r.to);});
 $('period-year').onchange=()=>{const y=$('period-year').value;if(y==='custom')return;selectRange(y?y+'-01-01':'',y?y+'-12-31':'');};
 $('chart-metric').onchange=()=>{if(state){renderChart();renderTrends();}};
 $('weekly-chart').onclick=e=>{const b=e.target.closest('[data-week-from]');if(b)selectRange(b.dataset.weekFrom,b.dataset.weekTo,true);};
 $('annual-chart').onclick=e=>{const b=e.target.closest('[data-year-end]');if(b)selectRange(b.dataset.yearEnd.slice(0,4)+'-01-01',b.dataset.yearEnd,true);};
 $('monthly-chart').onclick=e=>{const b=e.target.closest('[data-month]');if(b){const r=P.monthRange(b.dataset.month);selectRange(r.from,r.to,true);}};
 $('discipline-chart').onclick=e=>{const b=e.target.closest('[data-discipline]');if(b){$('kind').value=b.dataset.discipline;onChange();}};
 $('calendar-prev').onclick=()=>{calendarMonth=P.shiftMonth(calendarMonth,-1);renderCalendar();};
 $('calendar-next').onclick=()=>{calendarMonth=P.shiftMonth(calendarMonth,1);renderCalendar();};
 $('calendar-today').onclick=()=>{calendarMonth=P.dayKey(new Date()).slice(0,7);renderCalendar();};
 $('activity-calendar').onclick=e=>{const b=e.target.closest('[data-day]');if(b)selectRange(b.dataset.day,b.dataset.day,true);};
 $('goal-kind').innerHTML='<option value="">Tutte le discipline</option>'+Object.entries(K).map(([key,text])=>`<option value="${key}">${esc(text)}</option>`).join('');
 $('edit-goal').onclick=()=>{$('goal-kind').value=goal?.kind||'';$('goal-metric').value=goal?.metric||'km';$('goal-target').value=goal?.target||'';$('remove-goal').hidden=!goal;$('goal-error').textContent='';$('goal-dialog').showModal();};
 $('goal-form').onsubmit=e=>{e.preventDefault();const next={kind:$('goal-kind').value,metric:$('goal-metric').value,target:Number($('goal-target').value)};if(!validGoal(next)||(next.metric==='count'&&!Number.isInteger(next.target))){$('goal-error').textContent='Inserisci un traguardo positivo; per le attività usa un numero intero.';return;}try{localStorage.setItem(GOAL_KEY,JSON.stringify(next));goal=next;$('goal-dialog').close();renderGoal();}catch(error){$('goal-error').textContent='Questo browser non consente il salvataggio. Abilita lo spazio di archiviazione del sito e riprova.';}};
 $('remove-goal').onclick=()=>{try{localStorage.removeItem(GOAL_KEY);goal=null;$('goal-dialog').close();renderGoal();}catch(e){$('goal-error').textContent='Impossibile rimuovere l’obiettivo salvato. Riprova.';}};
 function renderMetrics(){
  const totals=P.summary(state.valid),previous=P.previousRange(state.from,state.to),before=previous?P.summary(P.inRange(P.dated(state.baseline),previous.from,previous.to)):null;
  $('progress-context').textContent=(state.kind?K[state.kind]+' · ':'')+(state.from||state.to?`${state.from?date(state.from+'T12:00:00'):'Inizio raccolta'} – ${state.to?date(state.to+'T12:00:00'):'Oggi'}`:'Tutta la raccolta')+' · '+totals.count+' attività';
  $('progress-comparison').textContent=previous?'Confronto: '+date(previous.from+'T12:00:00')+' – '+date(previous.to+'T12:00:00'):'';
  $('progress-metrics').innerHTML=[['km','Distanza','km'],['gain','Dislivello positivo','m'],['dur_s','Tempo registrato','ore'],['days','Giorni attivi','giorni']].map(([key,title,u])=>{
   const change=before?P.delta(totals[key],before[key]):null;
   const comparison=before?(change===null?(totals[key]>0?'Nessun dato nel periodo precedente':'Nessuna variazione'):(Math.abs(change)<0.1?'Variazione inferiore allo 0,1%':(change>0?'+':'')+number(change,1)+'% sul periodo precedente')):'Nel periodo selezionato';
   return `<div class="progress-metric"><span>${title}</span><strong>${key==='dur_s'?number(totals[key]/3600,1):number(totals[key],key==='km'?1:0)} <small>${u}</small></strong><p>${esc(comparison)}</p></div>`;
  }).join('');
  const missing=state.rows.length-state.valid.length;
  $('progress-data-note').textContent=(missing?missing+' attività con data mancante, non valida o futura escluse dalle statistiche. ':'')+'I filtri di ricerca, tipo e mappa valgono anche per questi risultati. I giorni sono quelli del tuo fuso orario.';
 }
 function renderChart(){
  const metric=$('chart-metric').value;let year=null;
  if(state.from&&state.to&&state.from.slice(0,4)===state.to.slice(0,4))year=+state.from.slice(0,4);
  else if(state.to)year=+state.to.slice(0,4);else if(state.from)year=+state.from.slice(0,4);
  const bins=P.monthBins(state.valid,year,metric),maximum=Math.max(1,...bins.map(b=>b.value));
  $('monthly-context').textContent=year?'Andamento nel '+year:'Ultimi 12 mesi · '+monthName(bins[0].month)+' – '+monthName(bins[11].month);
  $('monthly-chart').innerHTML=bins.map(b=>{const display=metricValue(b.value,metric),text=monthName(b.month)+': '+display+' '+unit(metric)+', '+b.count+' attività';return `<button class="month-column" data-month="${b.month}" ${b.count?'':'disabled'} aria-label="${esc(text)}" title="${esc(text)}"><span class="month-value">${display}</span><span class="month-track"><i style="height:${b.value?Math.max(2,b.value/maximum*100):0}%"></i></span><span>${esc(new Date(b.month+'-01T12:00:00').toLocaleDateString('it-IT',{month:'short'}))}</span></button>`;}).join('');
  const counts=new Map();for(const t of state.valid){const k=Object.hasOwn(K,t.kind)?t.kind:'other';counts.set(k,(counts.get(k)||0)+1);}
  $('discipline-chart').innerHTML=counts.size?[...counts].sort((a,b)=>b[1]-a[1]).map(([k,n])=>`<button class="discipline-row" data-discipline="${k}" aria-label="Filtra ${esc(K[k])}: ${n} attività"><span>${esc(K[k])}</span><strong>${n}</strong><span class="discipline-track"><i style="width:${n/state.valid.length*100}%"></i></span></button>`).join(''):'<p class="muted">Nessuna attività nel periodo selezionato.</p>';
 }
 function renderTrends(){
  const metric=$('chart-metric').value,bins=AnalysisTools.weeklyBins(state.valid,metric,state.from,state.to),maximum=Math.max(1,...bins.map(b=>b.value));
  $('weekly-context').textContent=bins.length?date(bins[0].from+'T12:00:00')+' – '+date(bins[bins.length-1].to+'T12:00:00')+' · settimane da lunedì a domenica, entro il periodo selezionato':'Nessun periodo disponibile.';
  $('weekly-chart').innerHTML=bins.map(b=>{const text=date(b.from+'T12:00:00')+' – '+date(b.to+'T12:00:00')+': '+metricValue(b.value,metric)+' '+unit(metric)+', '+b.count+' attività';return `<button class="month-column" data-week-from="${b.from}" data-week-to="${b.to}" ${b.count?'':'disabled'} aria-label="${esc(text)}" title="${esc(text)}"><span class="month-value">${metricValue(b.value,metric)}</span><span class="month-track"><i style="height:${b.value?Math.max(2,b.value/maximum*100):0}%"></i></span><span>${esc(new Date(b.from+'T12:00:00').toLocaleDateString('it-IT',{day:'numeric',month:'short'}))}</span></button>`;}).join('');
  const year=Math.min(+(state.to||state.from||P.dayKey(new Date())).slice(0,4),new Date().getFullYear()),annual=AnalysisTools.annualComparison(state.baseline,year,metric),top=Math.max(1,...annual.bins.flatMap(b=>[b.current||0,b.previous||0]));
  $('annual-context').textContent='Totale cumulativo: '+year+' e '+annual.previousYear+' · fino al '+date(annual.limit+'T12:00:00');
  $('annual-legend').innerHTML=`<span><i></i>${year}: ${metricValue(annual.current,metric)} ${unit(metric)}</span><span><i class="previous-year"></i>${annual.previousYear}: ${metricValue(annual.previous,metric)} ${unit(metric)}</span>`;
  $('annual-chart').innerHTML=annual.bins.map(b=>{const unavailable=b.current===null,text=unavailable?'Periodo non ancora trascorso':date(b.to+'T12:00:00')+': '+year+' '+metricValue(b.current,metric)+' '+unit(metric)+', '+annual.previousYear+' '+metricValue(b.previous,metric)+' '+unit(metric);return `<button class="month-column annual-column" data-year-end="${b.to}" ${unavailable?'disabled':''} title="${esc(text)}" aria-label="${esc(text)}"><span class="month-track"><i style="height:${b.current?Math.max(2,b.current/top*100):0}%"></i><i class="previous-year" style="height:${b.previous?Math.max(2,b.previous/top*100):0}%"></i></span><span>${esc(new Date(b.month+'-01T12:00:00').toLocaleDateString('it-IT',{month:'short'}))}</span></button>`;}).join('');
  $('annual-note').textContent=(annual.previousCount?'':'Nessuna attività disponibile per l’anno precedente. ')+'Il confronto usa l’anno intero, fino allo stesso giorno per l’anno in corso. Mantiene ricerca, tipo e mappa; seleziona un mese per aprire le attività accumulate da gennaio.';
 }
 function renderCalendar(){
  if(!state)return;
  const r=P.monthRange(calendarMonth),days=new Map();for(const t of state.valid){const key=P.dayKey(t.date);if(key.slice(0,7)===calendarMonth){if(!days.has(key))days.set(key,[]);days.get(key).push(t);}}
  const first=new Date(r.from+'T12:00:00'),offset=(first.getDay()+6)%7,last=+r.to.slice(8),today=P.dayKey(new Date());
  $('calendar-month').textContent=monthName(calendarMonth);
  $('activity-calendar').innerHTML=['Lun','Mar','Mer','Gio','Ven','Sab','Dom'].map(d=>`<span class="weekday">${d}</span>`).join('')+'<span class="calendar-spacer" aria-hidden="true" style="grid-column:span '+(offset||1)+';'+(offset?'':'display:none')+'"></span>'+Array.from({length:last},(_,i)=>{
   const day=r.from.slice(0,8)+String(i+1).padStart(2,'0'),activities=days.get(day)||[],total=P.summary(activities),title=date(day+'T12:00:00')+': '+activities.length+' attività'+(activities.length?', '+number(total.km,1)+' km':'');
   return `<button class="calendar-day ${activities.length?'has-activity':''} ${day===today?'today':''}" ${activities.length?'':'disabled'} data-day="${day}" title="${esc(title)}" aria-label="${esc(title)}" ${day===today?'aria-current="date"':''}><span>${i+1}</span>${activities.length?'<small>'+activities.length+'</small>':''}</button>`;
  }).join('');
  $('calendar-total').textContent=[...days.values()].reduce((n,a)=>n+a.length,0)+' attività · '+days.size+(days.size===1?' giorno attivo':' giorni attivi');
  $('calendar-next').disabled=calendarMonth>=today.slice(0,7);
  const earliest=P.dated(state.tracks).map(t=>P.dayKey(t.date)).sort()[0]||today;
  $('calendar-prev').disabled=calendarMonth<=earliest.slice(0,7);
 }
 function renderRecords(){const records=P.records(state.valid),streak=P.streak(state.valid);
  $('streak-info').textContent='Serie massima: '+streak.best+' '+(streak.best===1?'giorno attivo':'giorni attivi consecutivi');
  $('personal-records').innerHTML=[['km','La più lunga'],['gain','La salita maggiore'],['dur_s','La durata maggiore']].map(([key,title])=>{const t=records[key];return `<div class="record-card"><p>${title}</p>${t?`<strong>${key==='dur_s'?duration(t[key]):number(t[key],key==='km'?1:0)+' '+unit(key)}</strong><a href="${esc(viewerLink(t))}">${esc(label(t))}</a><span class="muted">${esc(date(t.date))} · ${esc(K[t.kind]||K.other)}</span>`:'<span class="muted">Nessun dato disponibile</span>'}</div>`;}).join('');
 }
 function renderGoal(){if(!state)return;
  $('edit-goal').textContent=goal?'Modifica obiettivo':'Imposta obiettivo';
  if(!goal){$('goal-progress').innerHTML='<div class="goal-empty"><span class="goal-symbol" aria-hidden="true">◎</span><p>Scegli una distanza, un dislivello o un numero di uscite da raggiungere ogni mese.</p></div>';return;}
  const now=new Date(),r=P.monthRange(P.dayKey(now).slice(0,7)),rows=P.inRange(P.dated(state.tracks,now),r.from,r.to).filter(t=>!goal.kind||(t.kind||'other')===goal.kind),total=P.summary(rows),value=goal.metric==='hours'?total.dur_s/3600:total[goal.metric],units={km:'km',gain:'m',hours:'ore',count:'attività'},percent=value/goal.target*100;
  $('goal-progress').innerHTML=`<p class="goal-month">${esc(monthName(r.from.slice(0,7)))} · ${esc(goal.kind?K[goal.kind]:'Tutte le discipline')}</p><p class="goal-value"><strong>${number(value,goal.metric==='count'||goal.metric==='gain'?0:1)}</strong> / ${number(goal.target,1)} ${units[goal.metric]}</p><progress max="${goal.target}" value="${Math.min(value,goal.target)}" aria-label="Obiettivo mensile: ${number(percent)} per cento"></progress><p>${percent>=100?'Traguardo raggiunto! '+number(percent)+'% dell’obiettivo.':'Hai raggiunto il '+number(percent)+'% del tuo obiettivo.'}</p>`;
 }
 function update(data){state={...data,valid:P.dated(data.rows)};
  const years=[...new Set(P.dated(data.tracks).map(t=>P.dayKey(t.date).slice(0,4)))].sort().reverse();const sig=years.join(',');if(yearSignature!==sig){$('period-year').innerHTML='<option value="">Tutti gli anni</option>'+years.map(y=>`<option value="${y}">${y}</option>`).join('')+'<option value="custom">Periodo personalizzato</option>';yearSignature=sig;}
  $('period-year').value=!data.from&&!data.to?'':data.from&&data.from.endsWith('-01-01')&&data.to===data.from.slice(0,4)+'-12-31'?data.from.slice(0,4):'custom';
  for(const b of document.querySelectorAll('[data-period]')){const r=quickRange(b.dataset.period);b.setAttribute('aria-pressed',String(data.from===r.from&&data.to===r.to));}
  const range=data.from+'|'+data.to;if(lastRange!==range){if(data.from){const yearRange=data.from.endsWith('-01-01')&&data.to===data.from.slice(0,4)+'-12-31';const today=P.dayKey(new Date());calendarMonth=yearRange&&data.from.slice(0,4)===today.slice(0,4)?today.slice(0,7):data.from.slice(0,7);}lastRange=range;}
  if(view==='progress'){renderMetrics();renderChart();renderTrends();renderCalendar();renderRecords();renderGoal();}
 }
 showView(view,false);
 return {get view(){return view;},showView,update};
}};
})();
