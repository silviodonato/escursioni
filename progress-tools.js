/* Statistics from cached activity metadata. No file parsing or network requests. */
(function(root){'use strict';
const pad=n=>String(n).padStart(2,'0');
function dayKey(value){if(!value)return null;const d=value instanceof Date?value:new Date(value);return Number.isFinite(d.getTime())?`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`:null;}
function isDay(key){if(!/^\d{4}-\d{2}-\d{2}$/.test(key||''))return false;const d=new Date(key+'T12:00:00Z');return Number.isFinite(+d)&&d.toISOString().slice(0,10)===key;}
function shiftDay(key,n){const d=new Date(key+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10);}
function monthRange(key){const [y,m]=key.split('-').map(Number);return {from:`${y}-${pad(m)}-01`,to:new Date(Date.UTC(y,m,0,12)).toISOString().slice(0,10)};}
function shiftMonth(key,n){const [y,m]=key.split('-').map(Number);const d=new Date(Date.UTC(y,m-1+n,1,12));return `${d.getUTCFullYear()}-${pad(d.getUTCMonth()+1)}`;}
const positive=v=>v===null||v===undefined||v===''?0:(Number.isFinite(+v)&&+v>=0?+v:0);
function inRange(rows,from='',to=''){return rows.filter(t=>{if(!from&&!to)return true;const day=dayKey(t.date);return day&&(!from||day>=from)&&(!to||day<=to);});}
function dated(rows,now=new Date()){const today=dayKey(now);return rows.filter(t=>{const d=dayKey(t.date);return d&&d<=today;});}
function summary(rows){const days=new Set();const totals={count:rows.length,km:0,gain:0,dur_s:0,days:0};for(const t of rows){for(const key of ['km','gain','dur_s'])totals[key]+=positive(t[key]);const d=dayKey(t.date);if(d)days.add(d);}totals.days=days.size;return totals;}
function previousRange(from,to,now=new Date()){
 if(!isDay(from)||!isDay(to)||from>to)return null;
 const today=dayKey(now);if(from>today)return null;const effective=to<today?to:today;
 // For calendar months and years compare the same elapsed part of the previous period.
 if(from.slice(5)==='01-01'&&to===from.slice(0,4)+'-12-31'){
  const y=+from.slice(0,4)-1,month=effective.slice(5,7),last=monthRange(`${y}-${month}`).to;
  return {from:`${y}-01-01`,to:`${y}-${month}-${pad(Math.min(+effective.slice(8),+last.slice(8)))}`};
 }
 const month=monthRange(from.slice(0,7));
 if(from===month.from&&to===month.to){const prev=monthRange(shiftMonth(from.slice(0,7),-1));return {from:prev.from,to:prev.from.slice(0,8)+pad(Math.min(+effective.slice(8),+prev.to.slice(8)))};}
 const span=Math.round((Date.parse(effective+'T12:00:00Z')-Date.parse(from+'T12:00:00Z'))/86400000)+1;
 return {from:shiftDay(from,-span),to:shiftDay(from,-1)};
}
function monthBins(rows,year,metric='km',now=new Date()){
 const today=dayKey(now);const first=year?`${year}-01`:shiftMonth(today.slice(0,7),-11);
 const bins=Array.from({length:12},(_,i)=>({month:shiftMonth(first,i),value:0,count:0}));const byMonth=new Map(bins.map(b=>[b.month,b]));
 for(const t of dated(rows,now)){const b=byMonth.get(dayKey(t.date).slice(0,7));if(b){b.count++;b.value+=metric==='count'?1:positive(t[metric]);}}
 return bins;
}
function streak(rows,now=new Date()){
 const days=[...new Set(dated(rows,now).map(t=>dayKey(t.date)))].sort();let best=0,run=0,previous=null;
 for(const day of days){run=previous&&shiftDay(previous,1)===day?run+1:1;best=Math.max(best,run);previous=day;}
 const set=new Set(days);let cursor=dayKey(now);if(!set.has(cursor))cursor=shiftDay(cursor,-1);let current=0;while(set.has(cursor)){current++;cursor=shiftDay(cursor,-1);}return {best,current};
}
function records(rows){const result={};for(const key of ['km','gain','dur_s']){result[key]=rows.filter(t=>positive(t[key])>0).slice().sort((a,b)=>positive(b[key])-positive(a[key])||String(a.file).localeCompare(String(b.file)))[0]||null;}return result;}
function delta(current,previous){return previous>0?(current-previous)/previous*100:null;}
const api={dayKey,isDay,shiftDay,monthRange,shiftMonth,positive,inRange,dated,summary,previousRange,monthBins,streak,records,delta};
if(typeof module==='object'&&module.exports)module.exports=api;else root.ProgressTools=api;
})(typeof globalThis!=='undefined'?globalThis:this);
