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
const api={project,unproject,heatCells};if(typeof module==='object'&&module.exports)module.exports=api;else root.AtlasTools=api;
})(typeof globalThis!=='undefined'?globalThis:this);
