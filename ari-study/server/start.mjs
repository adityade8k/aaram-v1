import { createApp } from './app.mjs';
const host=process.env.HOST||'127.0.0.1';
if(!['127.0.0.1','localhost','::1'].includes(host)&&!process.env.STUDY_ACCESS_TOKEN)throw new Error('Set STUDY_ACCESS_TOKEN before accepting network connections.');
const server=createApp();
server.listen(Number(process.env.PORT||4173),host,()=>console.log(`Ari study: http://${host}:${server.address().port}`));
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>{for(const client of server.studySockets.clients)client.close(1012,'Server stopping');server.close();});
