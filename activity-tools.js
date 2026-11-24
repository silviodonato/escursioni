/* Shared list ordering and distance to complete, segmented routes. */
(function(root){
'use strict';
function distanceToRoute(track,point){
  const scale=Math.cos(point[0]*Math.PI/180),meter=111195;
  let best=Infinity;
  for(const segment of track.routes||[]){
    let previous=null;
    for(const p of segment){
      const x=(p[1]-point[1])*meter*scale,y=(p[0]-point[0])*meter;
      if(previous){const [ax,ay]=previous,dx=x-ax,dy=y-ay,n=dx*dx+dy*dy;
        const t=n?Math.max(0,Math.min(1,-(ax*dx+ay*dy)/n)):0;
        best=Math.min(best,Math.hypot(ax+t*dx,ay+t*dy));
      }else best=Math.min(best,Math.hypot(x,y));
      previous=[x,y];
    }
  }
  return best;
}
const KINDS={hiking:'Escursione',walking:'Camminata',running:'Corsa',cycling:'Ciclismo',swimming:'Nuoto',skiing:'Sci',kayaking:'Kayak',sup:'SUP',surfing:'Surf',elliptical:'Ellittica',workout:'Allenamento generico',other:'Altro / da classificare'};
const SORTS={newest:['date',-1],oldest:['date',1],longest:['km',-1],shortest:['km',1],
  'gain-desc':['gain',-1],'gain-asc':['gain',1],'duration-desc':['dur_s',-1],'duration-asc':['dur_s',1],
  'kind-asc':['kind',1],'kind-desc':['kind',-1],'name-asc':['name',1],'name-desc':['name',-1]};
const collator=new Intl.Collator('it',{numeric:true,sensitivity:'base'});
function sortTracks(rows,order,options={}){
  const [key,direction]=SORTS[order]||SORTS.newest;
  const value=t=>{
    if(key==='kind')return KINDS[t.kind]&&t.kind!=='other'?KINDS[t.kind]:null;
    if(key==='name')return options.label?options.label(t):(t.display_name||t.name||t.file||null);
    if(key==='date'){const n=t.date?Date.parse(t.date):NaN;return Number.isFinite(n)?n:null;}
    if(t[key]===null||t[key]===undefined||t[key]==='')return null;
    const n=Number(t[key]);return Number.isFinite(n)&&n>=0?n:null;
  };
  return rows.slice().sort((a,b)=>{
    const av=value(a),bv=value(b);
    // Missing values and unclassified types stay at the end in either direction.
    if(av===null&&bv!==null)return 1;
    if(bv===null&&av!==null)return -1;
    const d=av===null?0:(typeof av==='string'?collator.compare(av,bv):av-bv)*direction;
    if(d)return d;
    // Keep the newest activities first within each type or equal measurement.
    if(key!=='date'){
      const ad=a.date?Date.parse(a.date):NaN,bd=b.date?Date.parse(b.date):NaN;
      if(Number.isFinite(ad)&&Number.isFinite(bd)&&ad!==bd)return bd-ad;
      if(Number.isFinite(ad)!==Number.isFinite(bd))return Number.isFinite(ad)?-1:1;
    }
    return String(a.file||'').localeCompare(String(b.file||''));
  });
}
const api={distanceToRoute,sortTracks,KINDS,SORTS};
if(typeof module==='object'&&module.exports)module.exports=api;else root.ActivityTools=api;
})(typeof globalThis!=='undefined'?globalThis:this);
