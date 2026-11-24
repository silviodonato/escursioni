/* Read-only activity comparison, export and trend calculations. */
(function(root){'use strict';
const P=typeof module==='object'&&module.exports?require('./progress-tools.js'):root.ProgressTools;
function weeklyBins(rows,metric='km',from='',to='',now=new Date()){
 const today=P.dayKey(now),end=to&&to<today?to:today;if(from&&from>end)return [];
 const monday=day=>P.shiftDay(day,-((new Date(day+'T12:00:00Z').getUTCDay()+6)%7));
 const last=monday(end);let start=P.shiftDay(last,-77);if(from&&monday(from)>start)start=monday(from);
 const bins=[];for(let day=start;day<=last;day=P.shiftDay(day,7)){const finish=P.shiftDay(day,6);bins.push({week:day,from:from&&from>day?from:day,to:finish>end?end:finish,value:0,count:0});}
 for(const t of P.dated(P.inRange(rows,from,to),now)){const day=P.dayKey(t.date);const b=bins.find(b=>day>=b.from&&day<=b.to);if(b){b.count++;b.value+=metric==='count'?1:P.positive(t[metric]);}}
 return bins;
}
function annualComparison(rows,year,metric='km',now=new Date()){
 year=Number(year);const today=P.dayKey(now),thisYear=+today.slice(0,4),limit=year===thisYear?today:`${year}-12-31`;
 const prevYear=year-1,last=P.monthRange(`${prevYear}-${limit.slice(5,7)}`).to;
 const prevLimit=`${prevYear}-${limit.slice(5,7)}-${String(Math.min(+limit.slice(8),+last.slice(8))).padStart(2,'0')}`;
 const a=P.monthBins(P.inRange(rows,`${year}-01-01`,limit),year,metric,now);
 const b=P.monthBins(P.inRange(rows,`${prevYear}-01-01`,prevLimit),prevYear,metric,now);
 let current=0,previous=0;const bins=a.map((entry,i)=>{current+=entry.value;previous+=b[i].value;const unavailable=year>thisYear||entry.month>limit.slice(0,7);return {month:entry.month,to:entry.month===limit.slice(0,7)?limit:P.monthRange(entry.month).to,current:unavailable?null:current,previous:unavailable?null:previous,count:entry.count,previousCount:b[i].count};});
 return {year,previousYear:prevYear,limit,previousLimit:prevLimit,bins,current,previous,previousCount:b.reduce((s,e)=>s+e.count,0)};
}
function numeric(value){return (typeof value==='number'||typeof value==='string')&&value!==''&&Number.isFinite(+value)&&+value>=0?+value:null;}
function speed(t){const km=numeric(t.km),seconds=numeric(t.dur_s);return km!==null&&seconds>0?km/seconds*3600:null;}
function pace(t){const km=numeric(t.km),seconds=numeric(t.dur_s);return km>0&&seconds>0?seconds/km:null;}
function routes(t){return (Array.isArray(t.routes)?t.routes:[]).flatMap(segment=>{
 const parts=[];let current=[];for(const point of Array.isArray(segment)?segment:[]){if(Array.isArray(point)&&typeof point[0]==='number'&&typeof point[1]==='number'&&Number.isFinite(point[0])&&Number.isFinite(point[1])&&Math.abs(point[0])<=90&&Math.abs(point[1])<=180)current.push([point[0],point[1]]);else{if(current.length>1)parts.push(current);current=[];}}
 if(current.length>1)parts.push(current);return parts;
});}
function csvCell(value){let s=String(value??'');if(/^[\s\u0000-\u001f]*[=+\-@]/.test(s)||/^[\t\r\n]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';}
function csv(rows,{label=t=>t.display_name||t.name||t.file,kind=t=>t.kind||'other'}={}){
 const numericCell=v=>{const n=numeric(v);return n===null?'':String(n).replace('.',',');};
 const headers=['Nome','File','Data originale','Tipo','Distanza (km)','Dislivello positivo (m)','Durata totale (s)','Velocità su tempo totale (km/h)','Passo su tempo totale (s/km)'];
 return '\ufeff'+[headers,...rows.map(t=>[label(t),t.file,t.date||'',kind(t),numericCell(t.km),numericCell(t.gain),numericCell(t.dur_s),numericCell(speed(t)),numericCell(pace(t))])].map(row=>row.map(csvCell).join(';')).join('\r\n')+'\r\n';
}
const api={weeklyBins,annualComparison,numeric,speed,pace,routes,csv,csvCell};if(typeof module==='object'&&module.exports)module.exports=api;else root.AnalysisTools=api;
})(typeof globalThis!=='undefined'?globalThis:this);
