import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { timingSafeEqual } from 'node:crypto';
import { WebSocketServer } from 'ws';
import { validateStart } from './policy.mjs';
import { connectVoice, research } from './providers.mjs';
import { searchWeb } from './search.mjs';
import { StudySession } from './session.mjs';

export function authorized(value, expected) {
  const actual=Buffer.from(typeof value==='string'?value:'');const target=Buffer.from(expected||'');
  return actual.length===target.length&&timingSafeEqual(actual,target);
}

export function createApp(env=process.env, providers={connectVoice,research,searchWeb}) {
  const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.json':'application/json'};
  const root=new URL('../public/',import.meta.url);
  const server=createServer(async(req,res)=>{
    if((env.ALLOWED_ORIGINS||'').split(',').includes(req.headers.origin))res.setHeader('Access-Control-Allow-Origin',req.headers.origin);
    res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Permissions-Policy','camera=()');
    if(!['GET','HEAD'].includes(req.method)){res.writeHead(405).end();return;}
    const url=new URL(req.url,'http://localhost');
    if(url.pathname==='/api/health'){
      res.setHeader('Content-Type','application/json');res.end(JSON.stringify({ok:true,search_configured:Boolean(env.BRAVE_SEARCH_API_KEY),background_configured:Boolean(env.ANTHROPIC_API_KEY&&env.REACHY_MINI_REASONING_MODEL),voice_configured:Boolean(env.HF_REALTIME_WS_URL||env.HF_TOKEN),uses_default_allocator:!env.HF_REALTIME_WS_URL,auth_required:Boolean(env.STUDY_ACCESS_TOKEN),version:'0.2.0'}));return;
    }
    const name=url.pathname==='/'?'index.html':url.pathname.slice(1);
    if(!/^[a-zA-Z0-9_./-]+$/.test(name)||name.includes('..')){res.writeHead(404).end();return;}
    try{const bytes=await readFile(new URL(name,root));res.setHeader('Content-Type',mime[name.slice(name.lastIndexOf('.'))]||'application/octet-stream');res.end(req.method==='HEAD'?undefined:bytes);}
    catch{res.writeHead(404).end('Not found');}
  });
  const wss=new WebSocketServer({noServer:true,maxPayload:64*1024});
  server.on('upgrade',(req,socket,head)=>{
    const origin=req.headers.origin;
    const local=['127.0.0.1','::1','::ffff:127.0.0.1'].includes(req.socket.remoteAddress);
    let originAllowed=false;
    try{const parsed=new URL(origin);originAllowed=(env.ALLOWED_ORIGINS||'').split(',').includes(origin)||parsed.host===req.headers.host;
      if(!env.STUDY_ACCESS_TOKEN)originAllowed=originAllowed&&local&&['localhost','127.0.0.1','[::1]'].includes(parsed.hostname);
    }catch{originAllowed=false;}
    if(req.url!=='/api/voice'||!originAllowed||(!env.STUDY_ACCESS_TOKEN&&!local)||wss.clients.size>=4){socket.write('HTTP/1.1 403 Forbidden\r\n\r\n');socket.destroy();return;}
    wss.handleUpgrade(req,socket,head,client=>wss.emit('connection',client));
  });
  wss.on('connection',client=>{
    let session=null,starting=false,closed=false;
    const timeout=setTimeout(()=>client.close(1008,'Setup timed out'),10000);
    client.on('error',()=>{closed=true;clearTimeout(timeout);session?.close();});
    client.on('close',()=>{closed=true;clearTimeout(timeout);session?.close();});
    client.on('message',async bytes=>{
      let message;
      try{message=JSON.parse(bytes.toString());}catch{client.close(1008,'Invalid message');return;}
      if(!message||typeof message!=='object'){client.close(1008,'Invalid message');return;}
      if(session){session.handleClient(message);return;}
      if(starting)return;
      if(message.type!=='start'||!authorized(message.token,env.STUDY_ACCESS_TOKEN)){client.close(1008,'Access denied');return;}
      starting=true;clearTimeout(timeout);
      try{
        const condition=validateStart(message,env);
        const voice=await providers.connectVoice(env);
        if(closed){voice.close();return;}
        session=new StudySession(client,voice,condition,providers,env);
      }catch(error){if(client.readyState===1){client.send(JSON.stringify({type:'error',message:String(error.message).slice(0,300)}));client.close(1011,'Unable to start');}}
    });
  });
  server.on('close',()=>{for(const client of wss.clients)client.close(1012,'Server stopping');wss.close();});
  server.studySockets=wss;
  return server;
}
