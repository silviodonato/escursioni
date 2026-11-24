const assert=require('node:assert/strict');
const {sortTracks,SORTS}=require('./activity-tools.js');
const files=rows=>rows.map(t=>t.file);
const rows=[
 {file:'a',name:'Percorso 10',date:'2025-01-01',kind:'running',km:10,gain:300,dur_s:500},
 {file:'b',name:'Álpi',date:'2026-01-01',kind:'walking',km:20,gain:100,dur_s:1000},
 {file:'c',name:'Percorso 2',date:null,kind:'hiking',km:0,gain:0,dur_s:0},
 {file:'z',name:'ZZZ',date:'invalid',kind:'other',km:null,gain:null,dur_s:null}
];
const expected={newest:'bacz',oldest:'abcz',longest:'bacz',shortest:'cabz',
 'gain-desc':'abcz','gain-asc':'cbaz','duration-desc':'bacz','duration-asc':'cabz',
 'kind-asc':'bacz','kind-desc':'cabz','name-asc':'bcaz','name-desc':'zacb'};
for(const order of Object.keys(SORTS))assert.equal(files(sortTracks(rows,order)).join(''),expected[order],order);
assert.deepEqual(files(rows),['a','b','c','z'],'input is not mutated');
for(const order of ['gain-asc','gain-desc','longest','shortest','duration-asc','duration-desc']){
 const key=SORTS[order][0];
 const result=sortTracks([{file:'missing', [key]:''},{file:'bad',[key]:'bad'},{file:'negative',[key]:-1},{file:'zero',[key]:0},{file:'positive',[key]:1}],order);
 assert.deepEqual(new Set(files(result.slice(-3))),new Set(['missing','bad','negative']),order+' keeps unknown values last');
}
assert.deepEqual(files(sortTracks([{file:'a',kind:'running',date:'2020-01-01'},{file:'b',kind:'running',date:'2025-01-01'}],'kind-asc')),['b','a']);
assert.deepEqual(files(sortTracks([{file:'a',name:'Z'},{file:'b',name:'A'}],'name-asc',{label:t=>t.file==='a'?'Alpi':'Monte'})),['a','b'],'sort uses displayed labels');
assert.deepEqual(files(sortTracks(rows,'invalid')),files(sortTracks(rows,'newest')));
console.log('22 sorting checks passed (12 orders, missing values, ties, displayed names, immutability).');
