export class PhoneAudio {
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
