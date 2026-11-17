(()=>{
class PhoneAudio {
  constructor(onChunk,onPlayback,onStarted){this.onChunk=onChunk;this.onPlayback=onPlayback;this.onStarted=onStarted;this.sources=new Set();this.next=0;this.muted=false;this.playedResponses=new Set();this.stopped=false;}
  async start(){
    if(!isSecureContext)throw new Error('Microphone access needs HTTPS on your phone (or localhost on this computer).');
    if(!navigator.mediaDevices?.getUserMedia||!window.AudioWorkletNode)throw new Error('Use a current Safari or Chrome browser with microphone support.');
    this.context=new AudioContext({latencyHint:'interactive'});await this.context.resume();
    this.stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});
    if(this.stopped){this.stream.getTracks().forEach(track=>track.stop());return;}
    await this.context.audioWorklet.addModule('/capture-worklet.js');
    if(this.stopped)return;
    this.input=this.context.createMediaStreamSource(this.stream);this.worklet=new AudioWorkletNode(this.context,'mic-capture');
    this.worklet.port.onmessage=event=>{
      if(this.muted||this.stopped)return;
      const bytes=new Uint8Array(event.data);let binary='';for(const byte of bytes)binary+=String.fromCharCode(byte);this.onChunk(btoa(binary));
    };
    this.silent=this.context.createGain();this.silent.gain.value=0;this.input.connect(this.worklet).connect(this.silent).connect(this.context.destination);
  }
  play(encoded,responseId){
    if(this.stopped||!this.context||this.context.state!=='running')throw new Error('Audio playback paused. End this block and restart with the screen awake.');
    const binary=atob(encoded),bytes=new Uint8Array(binary.length);for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);
    const pcm=new DataView(bytes.buffer);const buffer=this.context.createBuffer(1,bytes.length/2,16000);const channel=buffer.getChannelData(0);
    for(let i=0;i<channel.length;i++)channel[i]=pcm.getInt16(i*2,true)/32768;
    const source=this.context.createBufferSource();source.buffer=buffer;source.connect(this.context.destination);
    const when=Math.max(this.context.currentTime+.015,this.next);this.next=when+buffer.duration;this.sources.add(source);
    source.onended=()=>{this.sources.delete(source);this.onPlayback(Math.max(0,this.next-this.context.currentTime)*1000);};source.start(when);
    if(!this.playedResponses.has(responseId)){this.playedResponses.add(responseId);this.onStarted(responseId,(when-this.context.currentTime)*1000,this.context.baseLatency||0);}
    this.onPlayback(Math.max(0,this.next-this.context.currentTime)*1000);
  }
  mute(value){this.muted=value;this.stream?.getAudioTracks().forEach(track=>{track.enabled=!value;});}
  clear(){for(const source of this.sources){source.onended=null;source.stop();}this.sources.clear();this.next=0;this.onPlayback(0);}
  async stop(){this.stopped=true;this.clear();this.stream?.getTracks().forEach(track=>track.stop());this.input?.disconnect();this.worklet?.disconnect();if(this.worklet)this.worklet.port.onmessage=null;this.silent?.disconnect();if(this.context&&this.context.state!=='closed')await this.context.close();}
}

const modeLabels={inline:"Conversation model alone",background:"With background researcher"};
const sequences={1:[['robot','X'],['phone','Y']],2:[['phone','X'],['robot','Y']],3:[['robot','Y'],['phone','X']],4:[['phone','Y'],['robot','X']]};
const tasks={
  X:{title:'An exhibition sign.',description:'You want a small sign with cut lettering and an engraved detail. Use the project file and sample materials to prepare a plan to discuss with shop staff. Work out what is ready, what needs changing, and what still needs checking.'},
  Y:{title:'Labels for a project.',description:'You want a set of project labels with a cut outline and an engraved symbol. Use the project file and sample materials to prepare a plan to discuss with shop staff. Work out what is ready, what needs changing, and what still needs checking.'},
  practice:{title:'Start with an idea.',description:'Tell Ari about something you might like to make. Ask a follow-up, and try interrupting a response. This is a practice conversation; no machine operation.'}
};
const ratingItems=[
  ['clarity','I could understand the assistance.'],['comfort','I felt comfortable saying I was confused.'],
  ['effort','It took effort to keep the conversation going.'],['uncertainty','I could tell when the assistant was uncertain.'],
  ['verification','I knew when I needed to check with staff.'],['presence','I felt that I was interacting with a socially present partner.']
];
function csvCell(value){return '"'+String(value??'').replaceAll('"','""')+'"';}
function eventsCsv(record){
  const columns=['session_id','participant','interface','mode','task','engine','time','elapsed_ms','clock','event','fields'];
  const lines=record.events.map(entry=>[entry.session_id||record.id,record.participant,record.interface,record.mode,record.task,record.engine,entry.time,entry.elapsed_ms,entry.clock,entry.event,JSON.stringify(Object.fromEntries(Object.entries(entry).filter(([key])=>!['session_id','time','elapsed_ms','clock','event'].includes(key))))]);
  return [columns,...lines].map(line=>line.map(csvCell).join(',')).join('\r\n');
}

const $=id=>document.getElementById(id);
let mode='inline',configured=false,active=false,ready=false,muted=false,socket=null,audio=null,record=null,exported=false,clock=0,begin=0,demoTimers=[],wakeLock=null;
let lastSpeechStop=null,playbackTimer=null,startGeneration=0;
const storageKey='ari-study-current-v1'; // Preserve earlier records; legacy modes are displayed explicitly.

function notice(text){$('notice').textContent=text;$('notice').hidden=!text;}
function view(name){for(const section of ['conversation','desk'])$(section).hidden=section!==name;document.querySelectorAll('.nav-item').forEach(button=>button.classList.toggle('active',button.dataset.view===name));$('view-name').textContent=name==='desk'?'Research desk':'Conversation';window.scrollTo(0,0);}
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>view(button.dataset.view)));
function renderPlan(){
  $('plan').replaceChildren();
  sequences[$('sequence').value].forEach(([surface,task],index)=>{const row=document.createElement('div');row.className='plan-step';const num=document.createElement('span');num.className='step-number';num.textContent=`0${index+1}`;const text=document.createElement('div');const title=document.createElement('strong');title.textContent=`${surface==='phone'?'Phone':'Robot'} · Task ${task}`;const detail=document.createElement('small');detail.textContent=`${modeLabels[mode]} · fresh conversation`;text.append(title,detail);row.append(num,text);$('plan').append(row);});
}
function updateTask(){const task=tasks[$('task').value];$('task-title').textContent=task.title;$('task-description').textContent=task.description;$('task-number').textContent=$('task').value==='practice'?'PRACTICE / NOT STUDY DATA':`TASK ${$('task').value} / PREPARATION`;}
$('sequence').addEventListener('change',()=>{$('task').value=sequences[$('sequence').value].find(([surface])=>surface==='phone')[1];renderPlan();updateTask();configured=false;});
$('setup-fields').addEventListener('change',()=>{configured=false;$('mode-label').textContent='SETUP CHANGED · APPLY SETTINGS';});
$('task').addEventListener('change',updateTask);
document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>{if(active)return;mode=button.dataset.mode;configured=false;document.querySelectorAll('[data-mode]').forEach(item=>{const selected=item===button;item.classList.toggle('selected',selected);item.setAttribute('aria-pressed',String(selected));});renderPlan();}));
$('setup-form').addEventListener('submit',event=>{event.preventDefault();if(active)return;configured=true;updateTask();renderPlan();$('mode-label').textContent=$('engine').value==='demo'?'SCRIPTED PREVIEW · NOT A LIVE MODEL':`PHONE · ${modeLabels[mode].toUpperCase()}`;notice('');view('conversation');});
function backendURL(){const entered=$('backend').value.trim();const url=new URL(entered||location.origin);if(!['http:','https:'].includes(url.protocol)||url.username||url.password||url.pathname!=='/'||url.search||url.hash)throw new Error('Use a server origin only, such as https://voice.example.com.');if(location.protocol==='https:'&&url.protocol!=='https:')throw new Error('An HTTPS phone page needs an HTTPS voice server.');return url;}
$('health-check').addEventListener('click',async()=>{try{const response=await fetch(new URL('/api/health',backendURL()),{signal:AbortSignal.timeout(8000)});if(!response.ok)throw new Error(`Server returned ${response.status}.`);const health=await response.json();$('health-status').textContent=`Server reachable. Shared search ${health.search_configured?"configured":"needs a search API key"}. Background researcher ${health.background_configured?'configured':'needs a Claude key and model ID'}. ${health.uses_default_allocator?'Voice uses the Hugging Face allocator; live access still needs checking.':'Direct voice endpoint configured.'}`;}catch(error){$('health-status').textContent=error.message;}});
function state(name,title,caption){$('voice-stage').dataset.state=name;$('voice-title').textContent=title;$('voice-caption').textContent=caption;}
function persist(){if(!record)return;try{localStorage.setItem(storageKey,JSON.stringify(record));}catch{notice('This browser could not save the record. Export JSON now to preserve it.');}}
function log(event,fields={}){if(!record)return;append({time:new Date().toISOString(),elapsed_ms:active?Math.round(performance.now()-begin):null,clock:'browser',entry_phase:active?'session':'post_session',event,...fields});}
function append(entry){record.events.push(entry);exported=false;persist();renderRecord();}
function renderRecord(){
  if(!record){$('events').textContent='No session yet.';$('record-meta').textContent='No session yet.';return;}
  $('record-meta').textContent=`${record.participant} · ${record.interface} · ${modeLabels[record.mode]||("Legacy mode: "+record.mode)} · Task ${record.task} · ${record.engine==='demo'?'SCRIPTED PREVIEW':record.status} · ${record.events.length} events`;
  $('events').replaceChildren();
  for(const entry of record.events.slice(-80)){const row=document.createElement('div');row.className='event-row';const time=document.createElement('time');time.textContent=entry.elapsed_ms===null?'After block':`${(entry.elapsed_ms/1000).toFixed(1)}s ${entry.clock==='server'?'S':'B'}`;const detail=document.createElement('div');detail.textContent=entry.event.replaceAll('_',' ');if(entry.text||entry.message||entry.label){const p=document.createElement('p');p.textContent=entry.role?`${entry.role}: ${entry.text}`:(entry.text||entry.message||entry.label);detail.append(p);}row.append(time,detail);$('events').append(row);}
  $('events').scrollTop=$('events').scrollHeight;
}
function setActive(value){active=value;$('setup-fields').disabled=value;$('setup-form').querySelector('button[type=submit]').disabled=value;$('start').hidden=value;$('end').hidden=!value;$('mute').hidden=!value||record?.engine==='demo';$('connection-dot').classList.toggle('live',value);$('connection-text').textContent=value?'Session active':'Ready to set up';}
async function end(reason='completed'){
  startGeneration++;if(!active)return;log('block_ended',{reason});record.status=reason;persist();ready=false;setActive(false);
  clearInterval(clock);clearTimeout(playbackTimer);for(const timer of demoTimers)clearTimeout(timer);demoTimers=[];
  if(socket){socket.onclose=null;socket.send&&socket.readyState===1&&socket.send(JSON.stringify({type:'stop'}));socket.close();socket=null;}
  if(audio){const current=audio;audio=null;await current.stop();}await wakeLock?.release().catch(()=>{});wakeLock=null;
  state('idle','A moment to reflect.','Thank you. Let the researcher know you’re ready.');$('mode-label').textContent='SESSION ENDED';$('start').textContent='Start a fresh conversation';renderRecord();
}
function runDemo(){
  const messages=mode==='background'?[
    [600,'transcript',{role:'user',text:'Why might two laser-cut pieces not fit together as expected?'}],
    [1300,'lookup_requested',{question:'Explain kerf and fit in a laser-cut joint.',research_id:1}],
    [1800,'transcript',{role:'assistant',text:'I’ll check the explanation. Are the pieces too loose, or too tight?'}],
    [4000,'transcript',{role:'user',text:'They are a little loose.'}],
    [6500,'research_ready',{research_id:1,snippets:['The cut removes some material; the resulting gap can affect fit.']}],
    [7300,'transcript',{role:'assistant',text:'That loose fit you mentioned could be related to the gap left by the cut. Bring a small test-fit plan to staff before cutting.'}]
  ]:[
    [600,'transcript',{role:'user',text:'Why might two laser-cut pieces not fit together as expected?'}],
    [1800,'transcript',{role:'assistant',text:'From what I know, the cut removes some material, which can affect fit. I’ll check the sources. Are the pieces too loose, or too tight?'}],
    [2600,'lookup_requested',{question:'Explain kerf and fit in a laser-cut joint.',mode:'inline'}],
    [4500,'search_ready',{sources:[{title:'Example source',url:'https://example.com'}]}],
    [6000,'transcript',{role:'assistant',text:'The search excerpts describe the gap left by the cut. That could affect the fit; bring a test-fit plan to staff before cutting.'}]
  ];
  notice('Scripted preview: no microphone, no live model, and no actual research. Open the research desk to inspect the example events.');
  for(const [delay,event,fields]of messages)demoTimers.push(setTimeout(()=>{log(event,{...fields,scripted:true});if(event==='transcript')state(fields.role==='assistant'?'speaking':'listening',fields.role==='assistant'?'Ari’s example response':'Example question',fields.text);},delay));
  demoTimers.push(setTimeout(()=>end('demo_completed'),10500));
}
async function start(){
  if(!configured){notice('Set the participant, task, inference architecture, and session engine in the research desk first.');view('desk');return;}
  if(record&&!exported&&!confirm('The previous block has not been exported. Replace the browser record? Cancel to export it first.'))return;
  const engine=$('engine').value;
  if(engine==='live'&&!$('consent').checked){notice('Confirm the consent step in the research desk before a live session.');view('desk');return;}
  if(!/^[A-Za-z0-9_-]{1,32}$/.test($('participant').value)){notice('Enter a participant code using letters, numbers, _ or -.');view('desk');return;}
  begin=performance.now();lastSpeechStop=null;record={schema:2,id:crypto.randomUUID(),participant:$('participant').value,interface:'phone',mode,task:$('task').value,sequence:$('sequence').value,engine,status:'active',created:new Date().toISOString(),consent_confirmed:engine==='live',events:[],ratings:{},notes:'',device:navigator.userAgent};exported=false;
  $('observer-notes').value='';for(const [key] of ratingItems)$(`rating-${key}`).value='';notice('');setActive(true);muted=false;$('mute').textContent='Mute microphone';
  log('block_started',{camera:false,raw_audio_saved:false});clock=setInterval(()=>{const seconds=Math.floor((performance.now()-begin)/1000);$('session-timer').textContent=`${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;},500);
  if(engine==='demo'){runDemo();return;}
  const generation=++startGeneration;
  state('connecting','Connecting to Ari…','Please allow microphone access when asked.');
  try{
    const target=backendURL();target.protocol=target.protocol==='https:'?'wss:':'ws:';target.pathname='/api/voice';
    audio=new PhoneAudio(chunk=>{if(ready&&socket?.readyState===1)socket.send(JSON.stringify({type:'audio',audio:chunk}));},remaining=>{
      if(ready&&socket?.readyState===1)socket.send(JSON.stringify({type:'playback',remaining_ms:remaining}));
      clearTimeout(playbackTimer);playbackTimer=setTimeout(()=>{if(active&&!muted)state('listening','I’m listening.','What would you like to work out?');},remaining+150);
    },(response_id,scheduled_delay_ms,base_latency_s)=>{log('audio_playback_scheduled',{response_id,scheduled_delay_ms,base_latency_s,turn_to_scheduled_audio_ms:lastSpeechStop===null?null:Math.round(performance.now()-lastSpeechStop+scheduled_delay_ms),measurement:'browser_schedule_estimate_not_acoustic_onset'});});
    await audio.start();if(generation!==startGeneration)return;
    log('microphone_started',{sample_rate_sent:16000});
    if(navigator.wakeLock)try{wakeLock=await navigator.wakeLock.request('screen');}catch{log('wake_lock_unavailable');}
    socket=new WebSocket(target);
    socket.onopen=()=>socket.send(JSON.stringify({type:'start',interface:'phone',participant:record.participant,mode:record.mode,task:record.task,consent:true,token:$('access-token').value}));
    socket.onmessage=event=>{
      try{
        const message=JSON.parse(event.data);
        if(message.type==='ready'){ready=true;record.server_session_id=message.session_id;log('voice_ready');state('listening','I’m listening.','Start with what you’re trying to make.');}
        else if(message.type==='log'){append(message.entry);if(message.entry.event==='speech_stopped')lastSpeechStop=performance.now();}
        else if(message.type==='audio')audio.play(message.audio,message.response_id);
        else if(message.type==='clear_audio'){audio.clear();clearTimeout(playbackTimer);}
        else if(message.type==='activity'&&!muted){const captions={listening:['I’m listening.','Take your time.'],thinking:['Thinking it through…','You can keep talking.'],speaking:['Ari is speaking.','You can interrupt or ask a follow-up.']};state(message.state,...(captions[message.state]||['Connected','']));}
        else if(message.type==='error'){notice(message.message);void end('connection_error');}
        else if(message.type==='notice')notice(message.message);
      }catch(error){notice(error.message||'The session could not continue.');void end('client_error');}
    };
    socket.onerror=()=>{notice('Could not connect to the voice server. Check its address, HTTPS, origin settings, and study access code.');void end('connection_error');};
    socket.onclose=()=>{if(active){notice('The voice connection ended. Export the partial block and start fresh after checking the connection.');void end('disconnected');}};
  }catch(error){notice(error.name==='NotAllowedError'?'Microphone permission was declined. Allow microphone access in your browser to try live voice.':error.message);await end('start_failed');}
}
$('start').addEventListener('click',()=>void start());$('end').addEventListener('click',()=>void end());
$('mute').addEventListener('click',()=>{muted=!muted;audio?.mute(muted);socket?.readyState===1&&socket.send(JSON.stringify({type:'mute',muted}));log('mic_toggle',{muted});$('mute').textContent=muted?'Unmute microphone':'Mute microphone';state(muted?'muted':'listening',muted?'Microphone paused.':'I’m listening.',muted?'Unmute whenever you’re ready.':'What would you like to work out?');});
$('participant-view').addEventListener('click',()=>{document.body.classList.add('participant-view');$('exit-participant').hidden=false;});$('exit-participant').addEventListener('click',()=>{document.body.classList.remove('participant-view');$('exit-participant').hidden=true;});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&active)void end('page_hidden');});
window.addEventListener('beforeunload',event=>{if(active){event.preventDefault();event.returnValue='';}});
function download(format){if(!record){notice('There is no session record to export yet.');return;}const value=format==='json'?JSON.stringify(record,null,2):eventsCsv(record);const url=URL.createObjectURL(new Blob([value],{type:format==='json'?'application/json':'text/csv'}));const link=document.createElement('a');link.href=url;link.download=`ari-${record.engine}-${record.participant}-${record.mode}-${record.task}-${record.id.slice(0,8)}.${format}`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);exported=true;}
$('export-json').onclick=()=>download('json');$('export-csv').onclick=()=>download('csv');
$('add-marker').onclick=()=>{if(!record){notice('Start a session before adding a marker.');return;}log('observer_marker',{label:$('marker').value});};
$('save-notes').onclick=()=>{if(!record){notice('Start a session before adding notes.');return;}record.notes=$('observer-notes').value;log('observer_notes_saved',{text:record.notes});};
for(const [key,text]of ratingItems){const label=document.createElement('label');label.textContent=text;const select=document.createElement('select');select.id=`rating-${key}`;for(const [value,name]of [['','Choose / skipped'],...Array.from({length:7},(_,i)=>[String(i+1),String(i+1)])]){const option=document.createElement('option');option.value=value;option.textContent=name;select.append(option);}label.append(select);$('ratings-fields').append(label);}
$('save-ratings').onclick=()=>{if(!record){notice('Start a session before saving ratings.');return;}record.ratings=Object.fromEntries(ratingItems.map(([key])=>[key,$(`rating-${key}`).value?Number($(`rating-${key}`).value):null]));log('ratings_saved',{ratings:record.ratings});};
$('clear-record').onclick=()=>{if(active){notice('End the block before clearing it.');return;}if(record&&confirm('Permanently remove this browser record? Export it first if needed.')){localStorage.removeItem(storageKey);record=null;exported=false;renderRecord();}};
try{record=JSON.parse(localStorage.getItem(storageKey)||'null');if(record){if(record.status==='active')record.status='interrupted_reload';$('observer-notes').value=record.notes||'';for(const[key]of ratingItems)$(`rating-${key}`).value=record.ratings?.[key]||'';notice('The previous browser record is available in the research desk. Export it before starting a new block.');renderRecord();}}catch{notice('The saved browser record could not be read.');}
renderPlan();updateTask();

})();
