'use strict';
importScripts('progress-tools.js?v=1','analysis-tools.js?v=1','route-tools.js?v=1');
onmessage=event=>{try{postMessage({groups:RouteTools.groups(event.data)});}catch(error){postMessage({error:true});}};
