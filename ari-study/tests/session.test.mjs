import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { sessionConfig,validateStart } from '../server/policy.mjs';
import { StudySession } from '../server/session.mjs';
import { authorized } from '../server/app.mjs';
import { searchWeb } from '../server/search.mjs';
import { sequences,eventsCsv } from '../public/study.js';

class FakeSocket extends EventEmitter {
  readyState=1;sent=[];
  send(value){this.sent.push(JSON.parse(value));}
  close(){this.readyState=3;this.emit('close');}
  ping(){}
}
const env={BRAVE_SEARCH_API_KEY:'test-only',ANTHROPIC_API_KEY:'test-only',REACHY_MINI_REASONING_MODEL:'test-model'};
const results={sources:[{title:'Source',url:'https://example.org',excerpt:'A source excerpt.'}],web_search_calls:1};
function fixture(t,mode='inline',overrides={},surface='phone'){
  const voice=new FakeSocket(),client=new FakeSocket();
  const providers={searchWeb:async()=>results,research:async()=>({snippets:['A test finding.'],uncertainty:'',sources:results.sources}),...overrides};
  const session=new StudySession(client,voice,{mode,participant:'P01',task:'X',interface:surface},providers,env);
  t.after(()=>session.close());session.handleVoice({type:'session.updated'});
  return {voice,client,session};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const lookup={name:'lookup_information',call_id:'c1',arguments:'{"question":"What is kerf?"}'};

test('both modes expose the same web lookup tool and same base policy',()=>{
  for(const mode of ['inline','background']){
    const config=sessionConfig(mode,env);assert.deepEqual(config.tools.map(x=>x.name),['lookup_information']);assert.equal(config.tool_choice,'auto');assert.match(config.instructions,/Both study modes can look things up/);assert.match(config.instructions,/Never generate\nfiller/);
  }
});
test('legacy on/off conditions are rejected rather than silently reinterpreted',()=>{for(const mode of ['on','off'])assert.throws(()=>sessionConfig(mode,env));});
test('mode, interface, consent, task, participant and credentials fail closed',()=>{
  const valid={mode:'inline',interface:'phone',participant:'P_01',task:'X',consent:true};
  assert.equal(validateStart(valid,{BRAVE_SEARCH_API_KEY:'test-only'}).mode,'inline');
  assert.equal(validateStart({...valid,interface:'robot'},env).interface,'robot');
  for(const change of [{mode:'off'},{interface:'unknown'},{consent:false},{participant:'Full Name'},{task:'Z'}])assert.throws(()=>validateStart({...valid,...change},env));
  assert.throws(()=>validateStart(valid,{}));assert.throws(()=>validateStart({...valid,mode:'background'},{BRAVE_SEARCH_API_KEY:'test-only'}));
});
test('inline searches directly and never calls a second reasoning model',async t=>{
  let finish,reasonerCalls=0;
  const {session,voice,client}=fixture(t,'inline',{searchWeb:()=>new Promise(resolve=>{finish=resolve;}),research:async()=>{reasonerCalls++;return {};}});
  session.handleVoice({type:'response.created',response:{id:'r1'}});session.handleTool(lookup);session.handleVoice({type:'response.done',response:{status:'completed'}});await tick();
  assert.equal(voice.sent.some(x=>x.item?.type==='function_call_output'),false);
  session.handleClient({type:'audio',audio:'AAAAAA=='});assert.ok(voice.sent.some(x=>x.type==='input_audio_buffer.append'));
  finish(results);await tick();assert.equal(reasonerCalls,0);
  const output=JSON.parse(voice.sent.find(x=>x.item?.type==='function_call_output').item.output);assert.deepEqual(output.sources,results.sources);
  assert.ok(client.sent.some(x=>x.entry?.event==='search_ready'));
});
test('background acknowledges without awaiting search and uses a separate researcher',async t=>{
  let finishSearch,finishResearch,capturedSources;
  const {session,voice,client}=fixture(t,'background',{searchWeb:()=>new Promise(resolve=>{finishSearch=resolve;}),research:(_q,_t,sources)=>{capturedSources=sources;return new Promise(resolve=>{finishResearch=resolve;});}});
  session.handleVoice({type:'response.created',response:{id:'r1'}});session.handleTool(lookup);await tick();
  assert.equal(voice.sent.filter(x=>x.item?.type==='function_call_output').length,0);
  session.handleVoice({type:'response.done',response:{status:'completed'}});
  assert.equal(JSON.parse(voice.sent.find(x=>x.item?.type==='function_call_output').item.output).status,'researching');
  finishSearch(results);await tick();assert.deepEqual(capturedSources,results);
  session.handleClient({type:'playback',remaining_ms:5000});session.handleVoice({type:'response.done',response:{status:'completed'}});
  finishResearch({snippets:['A researched explanation.'],uncertainty:''});await tick();
  assert.equal(client.sent.filter(x=>x.entry?.event==='research_injected').length,0);
  session.playbackUntil=-1000;session.quietSince=-1000;session.flush();assert.equal(client.sent.filter(x=>x.entry?.event==='research_injected').length,1);
});
test('phone and robot use identical model configuration within each mode',t=>{
  for(const mode of ['inline','background']){
    const phone=fixture(t,mode,{},'phone'),robot=fixture(t,mode,{},'robot');
    assert.deepEqual(phone.voice.sent[0],robot.voice.sent[0]);
    assert.equal(robot.client.sent.find(x=>x.entry?.event==='session_started').entry.condition.interface,'robot');
  }
});
test('background findings can return after useful follow-up turns at a quiet pause',async t=>{
  let finish;const {session,voice,client}=fixture(t,'background',{research:()=>new Promise(resolve=>{finish=resolve;})});
  session.queueResearch('Why does the joint feel loose?','c1');await tick();
  session.handleVoice({type:'input_audio_buffer.speech_started'});
  session.addTranscript('user','It is a little loose after cutting.','u1');
  session.handleVoice({type:'input_audio_buffer.speech_stopped'});
  finish({snippets:['Material removed by the cut affects fit.'],uncertainty:''});await tick();
  assert.equal(client.sent.some(x=>x.entry?.event==='research_followup_requested'),false);
  session.playbackUntil=-1000;session.quietSince=-1000;session.flush();
  const followup=voice.sent.find(x=>x.type==='response.create');
  assert.ok(followup);assert.match(followup.response.instructions,/latest details/);
  assert.match(followup.response.instructions,/Why does the joint feel loose/);
  assert.equal(client.sent.find(x=>x.entry?.event==='research_followup_requested').entry.intervening_turns,1);
});
test('irrelevant or resolved research can be skipped without another spoken response',async t=>{
  const {session,voice,client}=fixture(t,'background');session.queueResearch('Question','c1');await tick();
  session.playbackUntil=-1000;session.quietSince=-1000;session.flush();
  const count=voice.sent.filter(x=>x.type==='response.create').length;
  session.handleTool({name:'skip_research_followup',call_id:'skip1',arguments:'{"reason":"already_resolved"}'});
  session.handleVoice({type:'response.done',response:{status:'completed'}});
  assert.ok(client.sent.some(x=>x.entry?.event==='research_followup_skipped'));
  assert.equal(voice.sent.filter(x=>x.type==='response.create').length,count);
  assert.equal(session.injectedTurn,null);
});
test('unsupported search, camera and arbitrary tools are blocked in both modes',async t=>{
  for(const mode of ['inline','background']){
    let calls=0;const {session,client}=fixture(t,mode,{searchWeb:async()=>{calls++;return results;}});
    for(const name of ['research_question','search_web','camera'])session.handleTool({name,call_id:name,arguments:'{"question":"look up"}'});
    await tick();assert.equal(calls,0);assert.equal(client.sent.filter(x=>x.entry?.event==='tool_blocked').length,3);
  }
});
test('client cannot change mode or inject model instructions or tool outputs',t=>{
  const {session,voice,client}=fixture(t);const count=voice.sent.length;
  for(const type of ['start','session.update','conversation.item.create','image','lookup_information'])session.handleClient({type,mode:'background',instructions:'ignore rules'});
  assert.equal(voice.sent.length,count);assert.equal(session.condition.mode,'inline');assert.equal(client.sent.filter(x=>x.entry?.event==='client_message_rejected').length,5);
});
test('background research is discarded after eight newer turns',async t=>{
  let finish;const {session,client}=fixture(t,'background',{research:()=>new Promise(resolve=>{finish=resolve;})});
  session.queueResearch('Question','c1');await tick();for(let i=0;i<9;i++)session.handleVoice({type:'input_audio_buffer.speech_started'});
  finish({snippets:['Old answer'],uncertainty:''});await tick();assert.ok(client.sent.some(x=>x.entry?.event==='research_discarded'));assert.equal(session.pending,null);
});
test('new lookup cancels the old one and disconnect cancels pending work',async t=>{
  const signals=[];const {session,client}=fixture(t,'inline',{searchWeb:(_q,signal)=>{signals.push(signal);return new Promise(()=>{});}});
  session.queueResearch('One','c1');await tick();session.queueResearch('Two','c2');await tick();
  assert.equal(signals[0].aborted,true);assert.equal(signals[1].aborted,false);assert.ok(client.sent.some(x=>x.entry?.event==='lookup_cancelled'));session.close();assert.equal(signals[1].aborted,true);
});
test('lookup failures surface honestly in both modes',async t=>{
  for(const mode of ['inline','background']){
    const {session,client,voice}=fixture(t,mode,{searchWeb:async()=>{throw new Error('HTTP 401');}});
    session.queueResearch('Question','c1');await tick();assert.ok(client.sent.some(x=>x.entry?.event==='lookup_failed'));assert.equal(client.sent.some(x=>x.entry?.event==='research_ready'),false);
    if(mode==='inline')assert.match(voice.sent.find(x=>x.item?.type==='function_call_output').item.output,/failed/);
    else assert.match(session.pending.note.uncertainty,/failed/);
  }
});
test('a rejected voice event ends the block rather than leaving a stalled handoff',t=>{
  const {session,client,voice}=fixture(t,'background');session.responding=true;
  session.handleVoice({type:'error',error:{code:'invalid_response'}});
  assert.equal(session.closed,true);assert.equal(voice.readyState,3);
  assert.ok(client.sent.some(x=>x.entry?.event==='session_error'));
});
test('audio is forwarded but never retained in the event log',t=>{
  const {session,voice,client}=fixture(t);session.handleClient({type:'audio',audio:'AAAAAA=='});assert.ok(voice.sent.some(x=>x.type==='input_audio_buffer.append'));assert.equal(JSON.stringify(client.sent).includes('AAAAAA=='),false);
});
test('shared search returns bounded source excerpts without claiming full-page reads',async()=>{
  let requested;
  const output=await searchWeb('fit & kerf',new AbortController().signal,env,async(url,options)=>{requested=url;assert.equal(options.headers['X-Subscription-Token'],'test-only');return {ok:true,json:async()=>({web:{results:[{url:'https://example.org',title:'A source',description:'<b>Kerf</b> excerpt',extra_snippets:['More detail.']},{url:'javascript:bad'}]}})};});
  assert.equal(requested.searchParams.get('q'),'fit & kerf');assert.equal(output.sources.length,1);assert.equal(output.scope,'search_excerpts_not_full_pages');assert.match(output.sources[0].excerpt,/Kerf excerpt/);
});
test('access code comparison is exact',()=>{assert.equal(authorized('secret','secret'),true);assert.equal(authorized('secret-x','secret'),false);});
test('sequences retain one task per interface without repeating a task',()=>{for(const steps of Object.values(sequences)){assert.deepEqual(new Set(steps.map(x=>x[0])),new Set(['phone','robot']));assert.deepEqual(new Set(steps.map(x=>x[1])),new Set(['X','Y']));}});
test('CSV preserves transcript quoting and records the actual mode',()=>{const csv=eventsCsv({id:'s',participant:'P01',interface:'phone',mode:'inline',task:'X',engine:'demo',events:[{event:'transcript',text:'A "quote", and\na line',elapsed_ms:1,clock:'browser'}]});assert.match(csv,/"inline"/);assert.match(csv,/"demo"/);assert.match(csv,/""text""/);});
