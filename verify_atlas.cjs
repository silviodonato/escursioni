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
const fs=require('node:fs'),path='/tmp/escursioni-progress-preview/tracce/index.json';if(fs.existsSync(path)){const rows=JSON.parse(fs.readFileSync(path));const started=Date.now(),actual=A.heatCells(rows);console.log('Real collection density: '+actual.length+' cells, '+(Date.now()-started)+' ms.');}
console.log(n+' atlas checks passed: visit counts, sampling density, broken segments and invalid coordinates.');
