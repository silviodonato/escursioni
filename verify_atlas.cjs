const assert=require('node:assert/strict'),A=require('./atlas-tools.js');let n=0;const eq=(a,b)=>{assert.deepEqual(a,b);n++;};
for(const p of [[0,0],[44,9],[-33,18],[60,-120]]){const q=A.unproject(A.project(p));assert(Math.abs(q[0]-p[0])<1e-8&&Math.abs(q[1]-p[1])<1e-8);n++;}
const route={routes:[[[44,9],[44,9.1]]]};const dense={routes:[Array.from({length:101},(_,i)=>[44,9+i*.001])]};
let cells=A.heatCells([route]);assert(cells.length>20);n++;eq(Math.max(...cells.map(c=>c.count)),1);
eq(A.heatCells([dense]).map(c=>c.key).sort(),cells.map(c=>c.key).sort());
eq(A.heatCells([route,dense]).every(c=>c.count===2),true);
eq(A.heatCells([{routes:[[[44,9],[44,9]],[[44,9],[44,9]]]}]).length,1);
eq(A.heatCells([{routes:[[[44,9],[44,9]],[[45,10],[45,10]]]}]).length,2);
eq(A.heatCells([{routes:[[[44,9],[45,10]]]}]).length,2);
eq(A.heatCells([{routes:[]}]),[]);eq(A.heatCells([{routes:[[[999,9],[44,9]]]}]),[]);
eq(A.heatColor(0,10),[0,0,0,0]);
{const one=Math.round(255*A.STEP);assert(Math.abs(A.passages(one)-1)<.1);n++;
 const low=A.heatColor(one,50),high=A.heatColor(250,50);assert(low[3]>=200&&high[3]===255);n++;
 const rare=A.heatColor(one,1000);assert(rare[2]>rare[0]&&high[0]>high[2]&&low[2]>high[2]);n++; // violet when rare, red when most frequent
 const edge=A.heatColor(Math.round(one/3),50);assert(edge[3]<low[3]);n++;} // antialiased edges stay soft
eq([7,11,14,20].map(A.lineWidth).map(w=>Math.round(w*10)/10),[3,4.3,8.2,12]);
const fs=require('node:fs'),path='/tmp/escursioni-progress-preview/tracce/index.json';if(fs.existsSync(path)){const rows=JSON.parse(fs.readFileSync(path));const started=Date.now(),actual=A.heatCells(rows);console.log('Real collection density: '+actual.length+' cells, '+(Date.now()-started)+' ms.');}
console.log(n+' atlas checks passed: visit counts, sampling density, broken segments, invalid coordinates and heat colours.');
