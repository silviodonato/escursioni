const assert=require('node:assert/strict'),R=require('./route-tools.js');
const row=(file,offset=0,kind='running')=>({file,kind,routes:[Array.from({length:21},(_,i)=>[44+Math.sin(i/20*Math.PI)*.01+offset,9+i*.001])]});
const a=row('a'),b=row('b',.0001),c=row('c',.005),d=row('d',0,'cycling');
assert(R.similar(R.sample(a),R.sample(b)));assert(!R.similar(R.sample(a),R.sample(c)));assert(!R.similar(R.sample(a),R.sample(d)));
assert.deepEqual(R.groups([a,b,c,d]),[['a','b']]);
assert.equal(R.sample({file:'gap',routes:[a.routes[0],b.routes[0]]}),null);
assert.equal(R.sample({file:'tiny',routes:[[[44,9],[44,9.0001]]]}),null);
const reverse={...a,file:'reverse',routes:[a.routes[0].slice().reverse()]};assert(!R.similar(R.sample(a),R.sample(reverse)));
assert.equal(R.sample(a).points.length,64);
const fs=require('node:fs'),path='/tmp/escursioni-progress-preview/tracce/index.json';if(fs.existsSync(path)){const rows=JSON.parse(fs.readFileSync(path));let start=Date.now();const groups=R.groups(rows);console.log(groups.length+' actual route groups in '+(Date.now()-start)+' ms');}
console.log('Route checks passed: offsets, sport, direction, disconnected tracks and short routes.');
