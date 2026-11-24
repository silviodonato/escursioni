/* Visit density counts each activity once per 250 m cell, independent of GPS sampling rate. */
(function(root){'use strict';
const A=typeof module==='object'&&module.exports?require('./analysis-tools.js'):root.AnalysisTools;
const R=6378137;
function project(p){const lat=Math.max(-85,Math.min(85,p[0]))*Math.PI/180;return [R*p[1]*Math.PI/180,R*Math.log(Math.tan(Math.PI/4+lat/2))];}
function unproject(p){return [Math.atan(Math.sinh(p[1]/R))*180/Math.PI,p[0]/R*180/Math.PI];}
function heatCells(rows,cell=250){const cells=new Map();
 for(const track of rows){const visited=new Set();
  for(const segment of A.routes(track)){let previous=null;for(const point of segment){const p=project(point);if(previous){const dx=p[0]-previous[0],dy=p[1]-previous[1],distance=Math.hypot(dx,dy);if(distance<=30000){let x=Math.floor(previous[0]/cell),y=Math.floor(previous[1]/cell);const endX=Math.floor(p[0]/cell),endY=Math.floor(p[1]/cell),stepX=Math.sign(dx),stepY=Math.sign(dy),deltaX=dx?cell/Math.abs(dx):Infinity,deltaY=dy?cell/Math.abs(dy):Infinity;let nextX=dx?((stepX>0?(x+1)*cell:x*cell)-previous[0])/dx:Infinity,nextY=dy?((stepY>0?(y+1)*cell:y*cell)-previous[1])/dy:Infinity;visited.add(x+','+y);while(x!==endX||y!==endY){if(nextX<nextY){x+=stepX;nextX+=deltaX;}else if(nextY<nextX){y+=stepY;nextY+=deltaY;}else{x+=stepX;y+=stepY;nextX+=deltaX;nextY+=deltaY;}visited.add(x+','+y);}}}visited.add(Math.floor(p[0]/cell)+','+Math.floor(p[1]/cell));previous=p;}}
  for(const key of visited){const existing=cells.get(key);if(existing)existing.count++;else{const [x,y]=key.split(',').map(Number);cells.set(key,{key,point:unproject([(x+.5)*cell,(y+.5)*cell]),count:1});}}
 }
 return [...cells.values()];
}
/* Heat colouring: routes are stroked with a small alpha so overlaps accumulate; each pixel's
   alpha is turned back into a number of passages and mapped to a green-amber-red palette. */
const STEP=.06,KEEP=Math.log(1-STEP),STOPS=[[0,[106,44,200]],[.5,[245,130,0]],[1,[220,16,40]]];
const PALETTE=Array.from({length:256},(_,i)=>{const t=i/255,k=t<.5?0:1,[a,ca]=STOPS[k],[b,cb]=STOPS[k+1],f=(t-a)/(b-a);return ca.map((v,j)=>Math.round(v+(cb[j]-v)*f));});
function passages(alpha){return alpha?Math.log(1-Math.min(alpha,254)/255)/KEEP:0;}
function heatColor(alpha,max){const n=passages(alpha);if(!n)return [0,0,0,0];const t=Math.min(1,Math.log1p(n)/Math.log1p(Math.max(2,max))),c=PALETTE[Math.round(t*255)];return [c[0],c[1],c[2],Math.round(255*(.8+.2*t)*Math.min(1,n))];}
function lineWidth(zoom){return Math.max(3,Math.min(12,zoom*1.3-10));}
const api={project,unproject,heatCells,STEP,passages,heatColor,lineWidth};if(typeof module==='object'&&module.exports)module.exports=api;else root.AtlasTools=api;
})(typeof globalThis!=='undefined'?globalThis:this);
