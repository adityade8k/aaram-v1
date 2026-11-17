import { randomUUID } from 'node:crypto';
import { sessionConfig, hashes, skipResearchFollowupTool } from './policy.mjs';

export class StudySession {
  constructor(client, voice, condition, providers, env=process.env) {
    this.client=client; this.voice=voice; this.condition=condition; this.providers=providers; this.env=env;
    this.id=randomUUID(); this.started=performance.now(); this.closed=false;
    this.turn=0; this.speaking=false; this.responding=false; this.playbackUntil=0;
    this.transcript=[]; this.toolResults=[]; this.pending=null; this.controller=null;
    this.requestId=0; this.lastQuestion=''; this.lastRequestAt=0; this.researchCount=0; this.injectedTurn=null; this.researchRunning=false; this.inlineCall=null;
    this.ready=false; this.firstAudio=false; this.speechStop=null; this.seenCalls=new Set();
    this.quietSince=0;this.followupId=null;this.followupInterrupted=false;this.silentToolResults=[];
    this.onVoice=(bytes)=>{try{this.handleVoice(JSON.parse(bytes.toString()));}catch{this.fail('Voice service returned an invalid event.');}};
    voice.on('message',this.onVoice);
    voice.on('error',()=>this.fail('Voice connection failed. Start a fresh block after checking the connection.'));
    voice.on('close',()=>{if(!this.closed)this.fail('Voice connection closed. This block has ended.');});
    this.timer=setInterval(()=>this.flush(),100);
    this.heartbeat=setInterval(()=>{if(voice.readyState===1)voice.ping();},25000);
    this.limit=setTimeout(()=>this.fail('The 25-minute session limit was reached. Export this block before continuing.'),25*60*1000);
    this.startup=setTimeout(()=>this.fail('Voice service did not confirm the session configuration.'),20000);
    this.sendVoice({type:'session.update',session:sessionConfig(condition.mode,env)});
    this.log('session_started',{condition,hashes,voice:env.HF_VOICE||'Aiden',voice_provider:'Hugging Face',voice_model:'provider-managed; pin externally for study',reasoner:condition.mode==='background'?env.REACHY_MINI_REASONING_MODEL:null,web_enabled:true,search_provider:'Brave Search',camera:false,memory:false,sample_rate:16000,followup_quiet_window_ms:750,client_version:'0.2.0'});
  }
  send(message){if(this.client.readyState===1)this.client.send(JSON.stringify(message));}
  sendVoice(message){if(!this.closed&&this.voice.readyState===1)this.voice.send(JSON.stringify(message));}
  log(event,fields={}){this.send({type:'log',entry:{schema:2,session_id:this.id,time:new Date().toISOString(),elapsed_ms:Math.round(performance.now()-this.started),clock:'server',event,...fields}});}
  fail(message){this.log('session_error',{message});this.send({type:'error',message});this.close();if(this.client.readyState===1)this.client.close(1011,'Session ended');}
  handleClient(message) {
    if(this.closed)return;
    if(message.type==='audio'&&this.ready&&typeof message.audio==='string'&&message.audio.length<=44000&&/^[A-Za-z0-9+/]*={0,2}$/.test(message.audio)) {
      this.sendVoice({type:'input_audio_buffer.append',audio:message.audio});
    } else if(message.type==='playback'&&Number.isFinite(message.remaining_ms)) {
      this.playbackUntil=performance.now()+Math.max(0,Math.min(message.remaining_ms,30000))+350;
    } else if(message.type==='mute'&&typeof message.muted==='boolean') {
      this.log('microphone_muted',{muted:message.muted});
      if(message.muted)this.sendVoice({type:'input_audio_buffer.clear'});
    } else if(message.type==='stop') this.close();
    else this.log('client_message_rejected',{type:String(message.type).slice(0,80)});
  }
  handleVoice(event) {
    if(this.closed)return;
    if(event.type==='session.updated'&&!this.ready){
      this.ready=true;clearTimeout(this.startup);this.send({type:'ready',session_id:this.id,sample_rate:16000,condition:this.condition});this.log('session_ready');
    }
    if(event.type==='error'){
      this.log('provider_error',{code:event.error?.code||'unknown'});
      if(!this.ready)this.fail('Voice service rejected the session configuration. Check the configured backend version.');
      else this.fail('Voice service rejected an event. This block has ended; export it and check backend compatibility before restarting.');
      return;
    }
    if(event.type==='input_audio_buffer.speech_started'){
      this.speaking=true;this.turn++;this.playbackUntil=0;this.speechStop=null;
      if(this.followupId!==null)this.followupInterrupted=true;
      if(this.injectedTurn!==null&&this.turn-this.injectedTurn>8){this.sendVoice({type:'session.update',session:sessionConfig(this.condition.mode,this.env)});this.injectedTurn=null;this.log('research_context_expired');}
      this.log('speech_started',{turn:this.turn,interrupted_response:this.responding});this.send({type:'activity',state:'listening'});this.send({type:'clear_audio'});
    }
    if(event.type==='input_audio_buffer.speech_stopped'){
      this.speaking=false;this.speechStop=performance.now();this.quietSince=performance.now();this.log('speech_stopped',{turn:this.turn});this.send({type:'activity',state:'thinking'});
    }
    if(event.type==='response.created'){
      this.responding=true;this.firstAudio=false;this.log('response_started',{turn:this.turn,response_id:event.response?.id});
    }
    if(['response.output_audio.delta','response.audio.delta'].includes(event.type)){
      if(!this.firstAudio){this.firstAudio=true;this.log('first_audio_received',{turn:this.turn,response_id:event.response_id,latency_ms:this.speechStop===null?null:Math.round(performance.now()-this.speechStop)});}
      this.send({type:'audio',audio:event.delta,response_id:event.response_id});this.send({type:'activity',state:'speaking'});
      this.playbackUntil=Math.max(this.playbackUntil,performance.now()+500);
    }
    if(event.type==='conversation.item.input_audio_transcription.completed') this.addTranscript('user',event.transcript,event.item_id);
    if(event.type==='conversation.item.input_audio_transcription.failed') this.log('transcription_failed',{turn:this.turn});
    if(['response.output_audio_transcript.done','response.audio_transcript.done'].includes(event.type)) this.addTranscript('assistant',event.transcript,event.item_id);
    if(event.type==='response.function_call_arguments.done') this.handleTool(event);
    if(event.type==='response.done'){
      this.responding=false;this.quietSince=performance.now();this.log('response_done',{turn:this.turn,status:event.response?.status});
      for(const item of event.response?.output||[])if(item.type==='function_call')this.handleTool(item);
      if(this.followupId!==null){
        this.log('research_followup_finished',{research_id:this.followupId,interrupted:this.followupInterrupted});
        if(!this.followupInterrupted){this.sendVoice({type:'session.update',session:sessionConfig(this.condition.mode,this.env)});this.injectedTurn=null;}
        this.followupId=null;
      }
      this.flush();
    }
  }
  addTranscript(role,text,item_id){
    if(typeof text!=='string'||!text.trim())return;
    this.transcript.push({role,text:text.slice(0,6000)});this.transcript=this.transcript.slice(-20);
    this.log('transcript',{role,text,turn:this.turn,item_id});
  }
  handleTool(event){
    if(!event.call_id||this.seenCalls.has(event.call_id))return;
    this.seenCalls.add(event.call_id);
    if(event.name==='skip_research_followup'&&this.followupId!==null){
      let reason='not_useful';
      try{const args=JSON.parse(event.arguments);if(['topic_changed','already_resolved','not_useful'].includes(args.reason))reason=args.reason;}catch{this.log('followup_skip_argument_invalid');}
      this.log('research_followup_skipped',{research_id:this.followupId,reason});
      this.silentToolResults.push({type:'conversation.item.create',item:{type:'function_call_output',call_id:event.call_id,output:JSON.stringify({status:'skipped'})}});
      this.flush();return;
    }
    let result;
    if(event.name!=='lookup_information') {
      result={error:'This tool is unavailable. Use lookup_information when external information is needed.'};
      this.log('tool_blocked',{name:event.name,mode:this.condition.mode});
    } else {
      let args;
      try{args=JSON.parse(event.arguments);}catch{args={};}
      if(typeof args.question!=='string'||!args.question.trim()||args.question.length>2000)result={error:'A nonempty question of at most 2000 characters is required.'};
      else if(this.lastQuestion===args.question&&performance.now()-this.lastRequestAt<15000)result={status:'already_requested',instruction:'Do not poll. Continue naturally.'};
      else if(this.researchCount>=12) result={error:'This session research limit was reached. Offer known facts and uncertainty.'};
      else {
        this.queueResearch(args.question,event.call_id);
        if(this.condition.mode==='inline')return;
        result={status:'researching',instruction:'Continue now with a known fact or one useful question. Do not wait or invent a result.'};
      }
    }
    this.toolResults.push({type:'conversation.item.create',item:{type:'function_call_output',call_id:event.call_id,output:JSON.stringify(result)}});
    this.flush();
  }
  queueResearch(question,callId){
    if(this.researchRunning)this.log('lookup_cancelled',{research_id:this.requestId,reason:'superseded'});
    if(this.inlineCall)this.toolResults.push({type:'conversation.item.create',item:{type:'function_call_output',call_id:this.inlineCall,output:JSON.stringify({error:'Superseded by a newer lookup. Do not use this earlier request.'})}});
    this.inlineCall=this.condition.mode==='inline'?callId:null;
    this.controller?.abort();this.pending=null;this.requestId++;this.researchCount++;
    if(this.injectedTurn!==null){this.sendVoice({type:'session.update',session:sessionConfig(this.condition.mode,this.env)});this.injectedTurn=null;}
    const requestId=this.requestId,turn=this.turn,started=performance.now();
    this.lastQuestion=question;this.lastRequestAt=started;this.controller=new AbortController();this.researchRunning=true;
    const signal=AbortSignal.any([this.controller.signal,AbortSignal.timeout(90000)]);
    this.log('lookup_requested',{research_id:requestId,question,turn,mode:this.condition.mode});
    const transcript=[...this.transcript];
    Promise.resolve().then(()=>this.providers.searchWeb(question,signal,this.env)).then(results=>{
      if(this.closed||requestId!==this.requestId||signal.aborted)return null;
      this.log('search_ready',{research_id:requestId,elapsed_search_ms:Math.round(performance.now()-started),...results});
      if(this.condition.mode==='inline')return results;
      this.log('background_inference_started',{research_id:requestId});
      return this.providers.research(question,transcript,results,signal,this.env);
    }).then(note=>{
      if(this.closed||requestId!==this.requestId||signal.aborted)return;
      this.researchRunning=false;
      if(this.condition.mode==='inline'){
        this.inlineCall=null;
        const stale=this.turn-turn>8;
        this.log(stale?'lookup_discarded':'lookup_ready',{research_id:requestId,elapsed_lookup_ms:Math.round(performance.now()-started)});
        this.toolResults.push({type:'conversation.item.create',item:{type:'function_call_output',call_id:callId,output:JSON.stringify(stale?{error:'This lookup is outdated. Answer the current question instead.'}:note)}});
        this.flush();return;
      }
      if(this.turn-turn>8){this.log('research_discarded',{research_id:requestId,reason:'more_than_eight_new_turns'});return;}
      this.log('research_ready',{research_id:requestId,elapsed_research_ms:Math.round(performance.now()-started),...note});
      this.pending={requestId,turn,question,requestedAt:started,note};this.flush();
    }).catch(error=>{
      if(this.closed||requestId!==this.requestId)return;
      this.researchRunning=false;
      this.log('lookup_failed',{research_id:requestId,reason:signal.aborted?'cancelled_or_timed_out':String(error.message).slice(0,200)});
      if(this.condition.mode==='inline'){
        this.inlineCall=null;this.toolResults.push({type:'conversation.item.create',item:{type:'function_call_output',call_id:callId,output:JSON.stringify({error:'Lookup failed or timed out. No result was verified.'})}});this.flush();return;
      }
      this.pending={requestId,turn,question,requestedAt:started,note:{snippets:[],uncertainty:'Research failed or timed out. No result was verified. State that briefly and continue from known facts.'}};
    });
  }
  flush(){
    if(this.closed||!this.ready||this.responding||this.speaking)return;
    for(const result of this.silentToolResults.splice(0))this.sendVoice(result);
    if(this.toolResults.length){
      for(const result of this.toolResults.splice(0)){this.sendVoice(result);this.log('tool_output_sent',{call_id:result.item.call_id});}
      this.responding=true;this.sendVoice({type:'response.create'});return;
    }
    if(this.pending&&performance.now()>Math.max(this.playbackUntil,this.quietSince)+750){
      const pending=this.pending;this.pending=null;
      if(this.turn-pending.turn>8||performance.now()-pending.requestedAt>180000){this.log('research_discarded',{research_id:pending.requestId,reason:'stale_at_delivery'});return;}
      const contextualNote=JSON.stringify({question:pending.question,requested_on_turn:pending.turn,...pending.note});
      this.sendVoice({type:'session.update',session:sessionConfig(this.condition.mode,this.env,contextualNote)});
      this.injectedTurn=pending.turn;
      this.log('research_injected',{research_id:pending.requestId,turn:this.turn});
      this.responding=true;this.followupId=pending.requestId;this.followupInterrupted=false;
      this.log('research_followup_requested',{research_id:pending.requestId,intervening_turns:this.turn-pending.turn});
      this.sendVoice({type:'response.create',response:{tools:[skipResearchFollowupTool],tool_choice:'auto',instructions:sessionConfig(this.condition.mode,this.env,contextualNote).instructions+'\nA research note has just arrived. Use the latest conversation, not only the original question. If the finding is still useful, naturally connect it to the student\'s latest details in one or two sentences. Do not repeat answered questions or announce a separate research report. If the topic changed, the question is resolved, or the note adds nothing, call skip_research_followup without speaking.'}});
    }
  }
  close(){
    if(this.closed)return;
    if(this.researchRunning)this.log('lookup_cancelled',{research_id:this.requestId,reason:'session_ended'});
    this.log('session_ended');this.closed=true;this.controller?.abort();
    clearInterval(this.timer);clearInterval(this.heartbeat);clearTimeout(this.limit);clearTimeout(this.startup);
    this.pending=null;this.toolResults=[];this.silentToolResults=[];this.transcript=[];this.voice.close();
  }
}
