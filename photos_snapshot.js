const fs=require('node:fs'), path=require('node:path');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
function readPage(scroll=false){
 if(location.origin!=='https://photos.google.com')return {status:'no_photos_tab'};
 const account=[...document.querySelectorAll('[aria-label]')].find(e=>/^(Google Account|Tài khoản Google)\s*:/i.test(e.getAttribute('aria-label')||''));
 const label=account?.getAttribute('aria-label')||'';
 const account_key=label.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i)?.[0]?.toLowerCase()||'';
 const cdn=u=>{try{u=new URL(u);return u.protocol==='https:'&&(u.hostname==='photos.fife.usercontent.google.com'||u.hostname==='googleusercontent.com'||u.hostname.endsWith('.googleusercontent.com'))?u.href:'';}catch{return '';}};
 const avatar_url=[...(account?.querySelectorAll('img')||[])].map(e=>cdn(e.src)).find(Boolean)||'';
 const main=document.querySelector('[role="main"],main')||document.body,items=new Map();
 for(const link of main.querySelectorAll('a[href*="/photo/"],a[href^="photo/"]')){
  const url=new URL(link.href,location.href);if(url.origin!==location.origin)continue;
  const image=link.querySelector('img,[data-latest-bg],[role="img"],[style*="background-image"]');
  const bg=image?.getAttribute('data-latest-bg')||image?.style.backgroundImage||'';
  const thumbnail_url=cdn(image?.src||bg.match(/url\(["']?(.*?)["']?\)/)?.[1]||bg);
  const label=(link.getAttribute('aria-label')||image?.getAttribute('aria-label')||link.textContent||'').normalize('NFC');
  const duration=link.querySelector('[data-video-duration]')?.getAttribute('data-video-duration')||'';
  const kind=/video|vídeo/i.test(label)||duration?'video':/photo|ảnh/i.test(label)?'photo':'unknown';
  items.set(url.pathname,{media_key:url.pathname,photo_url:url.origin+url.pathname,thumbnail_url,label:label.slice(0,800),kind,duration});
 }
 const counts={photo:0,video:0,unknown:0};for(const item of items.values())counts[item.kind]++;
 const candidates=[main,...main.querySelectorAll('*')].filter(e=>e.clientHeight>100&&e.scrollHeight>e.clientHeight+5&&/(auto|scroll)/.test(getComputedStyle(e).overflowY));
 const scroller=candidates.sort((a,b)=>b.clientHeight-a.clientHeight)[0]||document.scrollingElement;
 const position={top:scroller.scrollTop,height:scroller.scrollHeight,viewport:scroller.clientHeight};
 const bottom=position.viewport>0&&position.top+position.viewport>=position.height-8;
 if(scroll&&items.size)scroller.scrollBy({top:Math.max(200,position.viewport*.75),behavior:'instant'});
 return {status:account_key?'account_visible':'unverified',account_key,account_label:label.slice(0,300),avatar_url,visible:counts,items:[...items.values()],page_url:location.href,position,bottom,total_photos:null,total_videos:null,scope:'loaded_page_only'};
}
async function main(){
 const lines=fs.readFileSync(path.join(process.argv[2],'DevToolsActivePort'),'utf8').trim().split(/\r?\n/);
 if(!/^\d+$/.test(lines[0])||!/^\/devtools\/browser\/[a-zA-Z0-9-]+$/.test(lines[1]))throw Error('bridge_required');
 const ws=new WebSocket(`ws://127.0.0.1:${Number(lines[0])}${lines[1]}`);
 await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=()=>reject(Error('unavailable'));});
 let seq=0;const pending=new Map();
 ws.onmessage=e=>{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error(m.error.message)):p.resolve(m.result);}};
 const call=(method,params={},sessionId)=>new Promise((resolve,reject)=>{const id=++seq;const timer=setTimeout(()=>{pending.delete(id);reject(Error('timeout'));},10000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params,sessionId}));});
 try{
  const {targetInfos}=await call('Target.getTargets');
  const pages=targetInfos.filter(t=>t.type==='page'&&t.url.startsWith('https://photos.google.com/'));
  if(pages.length!==1)throw Error(pages.length?'multiple_tabs':'no_photos_tab');
  const {sessionId}=await call('Target.attachToTarget',{targetId:pages[0].targetId,flatten:true});
  const scan=process.argv[3]==='scan',maxSteps=Math.min(2000,Math.max(1,Number(process.argv[4])||300));
  if(scan){
   const window=await call('Browser.getWindowForTarget',{targetId:pages[0].targetId});
   if(window.bounds.windowState==='minimized')await call('Browser.setWindowBounds',{windowId:window.windowId,bounds:{windowState:'normal'}});
   await call('Page.bringToFront',{},sessionId);
  }
  const read=async scroll=>{const r=await call('Runtime.evaluate',{expression:`(${readPage.toString()})(${scroll})`,returnByValue:true},sessionId);if(r.exceptionDetails||!r.result.value)throw Error('page_error');return r.result.value;};
  const first=await read(false);
  if(process.argv[3]==='preview'){
   const request=JSON.parse(fs.readFileSync(0,'utf8')),url=new URL(request.url);
   if(first.account_key!==request.account_key)throw Error('account_or_page_changed');
   if(url.protocol!=='https:'||!(url.hostname==='photos.fife.usercontent.google.com'||url.hostname.endsWith('.googleusercontent.com')))throw Error('invalid_thumbnail');
   const {frameTree}=await call('Page.getFrameTree',{},sessionId);
   const {resource}=await call('Network.loadNetworkResource',{frameId:frameTree.frame.id,url:url.href,options:{disableCache:false,includeCredentials:true}},sessionId);
   if(!resource.success||resource.httpStatusCode!==200||!resource.stream)throw Error('thumbnail_unavailable');
   const chunks=[];let total=0;
   try{while(true){const part=await call('IO.read',{handle:resource.stream,size:65536},sessionId);const bytes=Buffer.from(part.data,part.base64Encoded?'base64':'utf8');total+=bytes.length;if(total>8*1024*1024)throw Error('thumbnail_too_large');chunks.push(bytes);if(part.eof)break;}}finally{await call('IO.close',{handle:resource.stream},sessionId);}
   console.log(JSON.stringify({image:Buffer.concat(chunks).toString('base64')}));return;
  }
  if(!scan){delete first.items;console.log(JSON.stringify(first));return;}
  if(!/^\/(?:u\/\d+\/)?(?:photos)?\/?$/.test(new URL(first.page_url).pathname))throw Error('open_library_grid');
  if(!first.account_key)throw Error('account_unverified');
  let stable=0,empty=0,signature='',seen=new Set();
  for(let step=0;step<maxSteps;step++){
   const data=await read(true);
   if(data.account_key!==first.account_key||data.page_url!==first.page_url)throw Error('account_or_page_changed');
   let added=0;for(const item of data.items){if(!seen.has(item.media_key)){seen.add(item.media_key);added++;}}
   empty=data.items.length?0:empty+1;
   const next=JSON.stringify(data.position);
   stable=data.bottom&&!added&&next===signature?stable+1:0;signature=next;
   const stop=empty>=20?'no_media_loaded':stable>=6?'end_observed':step===maxSteps-1?'limit_reached':null;
   console.log(JSON.stringify({...data,step:step+1,scan_status:stop||'running'}));
   if(stop)return;await pause(1000);
  }
 }finally{ws.close();}
}
if(require.main===module){const deadline=setTimeout(()=>{console.log(JSON.stringify({status:'timeout'}));process.exit(0);},2100000);main().catch(e=>console.log(JSON.stringify({status:['bridge_required','multiple_tabs','no_photos_tab','open_library_grid','account_unverified','account_or_page_changed'].includes(e.message)?e.message:'unavailable',error:e.message.slice(0,200)}))).finally(()=>clearTimeout(deadline));}
module.exports={readPage};
