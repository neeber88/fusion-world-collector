// Online-first app shell. Offline fallback keeps the installed PWA usable.
const CACHE='fusion-world-shell-v1.8.8-auto-20261031';
const SHELL=['./','./index.html','./manifest.webmanifest','./icon.svg'];
self.addEventListener('install',event=>{
 event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).catch(()=>{}));
 self.skipWaiting();
});
self.addEventListener('activate',event=>{
 event.waitUntil(caches.keys().then(keys=>Promise.all(
  keys.filter(k=>k.startsWith('fusion-world-shell-')&&k!==CACHE).map(k=>caches.delete(k))
 )));
 self.clients.claim();
});
self.addEventListener('fetch',event=>{
 const req=event.request,url=new URL(req.url);
 if(req.method!=='GET'||url.origin!==self.location.origin)return;
 if(req.mode==='navigate'||url.pathname.endsWith('/index.html')){
  event.respondWith(
   fetch(new Request(req,{cache:'no-store'}))
    .then(response=>{
     if(response.ok){
      const copy=response.clone();
      event.waitUntil(caches.open(CACHE).then(c=>c.put('./index.html',copy)));
     }
     return response;
    })
    .catch(async()=>await caches.match('./index.html')||Response.error())
  );
  return;
 }
 if(url.pathname.endsWith('/app.js')||url.pathname.endsWith('/styles.css')){
  event.respondWith(fetch(new Request(req,{cache:'no-store'}))
   .then(response=>{
    if(response.ok){
     const copy=response.clone();
     event.waitUntil(caches.open(CACHE).then(c=>c.put(req,copy)));
    }
    return response;
   }).catch(async()=>await caches.match(req)||Response.error()));
  return;
 }
 event.respondWith(caches.match(req).then(hit=>hit||fetch(req)));
});
