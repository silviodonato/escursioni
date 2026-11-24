const assert=require('node:assert/strict'),Q=require('./quality-tools.js');
const a={file:'a',sha256:'a'.repeat(64),date:'2026-01-01T10:00:00Z',kind:'running',km:10,dur_s:3600};
assert.deepEqual(Q.duplicates([a,{...a,file:'b'}]).exact,[['a','b']]);assert.deepEqual(Q.duplicates([a,{...a,file:'b'}]).possible,[]);
assert.deepEqual(Q.duplicates([a,{...a,file:'b',sha256:'b'.repeat(64),date:'2026-01-01T10:00:20Z',km:10.2}]).possible,[['a','b']]);
for(const changes of [{kind:'cycling'},{date:'2026-01-01T10:10:00Z'},{km:12},{dur_s:8000}])assert.deepEqual(Q.duplicates([a,{...a,file:'b',sha256:'b'.repeat(64),...changes}]).possible,[]);
assert(Q.issues({date:'2126-01-01',kind:'other'},new Date('2026-11-24')).some(i=>i.key==='date'));
assert(Q.issues({date:'bad',kind:'running'}).some(i=>i.key==='date'));assert(Q.issues({...a,quality:{gps_jumps:1,clock_errors:2}}).some(i=>i.key==='gps'));
assert.deepEqual(Q.issues(a,new Date('2026-11-24')),[]);
console.log('Quality checks passed: exact/possible duplicates, date issues, GPS, clocks and sport separation.');

assert.equal(Q.typeHint({name:'Sci sull’Argentiere',kind:'running'}),'skiing');assert.equal(Q.typeHint({name:'Sci sull’Argentiere',kind:'skiing'}),null);assert(Q.issues({...a,name:'Sci sull’Argentiere'}).some(i=>i.key==='kind'));
