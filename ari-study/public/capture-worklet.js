class MicCapture extends AudioWorkletProcessor {
  constructor(){super();this.samples=new Int16Array(640);this.index=0;this.weight=0;this.sum=0;}
  process(inputs){
    const channel=inputs[0]?.[0];if(!channel)return true;
    const ratio=sampleRate/16000;
    for(const value of channel){
      let remaining=1;
      while(remaining>1e-8){
        const take=Math.min(remaining,ratio-this.weight);this.sum+=value*take;this.weight+=take;remaining-=take;
        if(this.weight>=ratio-1e-8){
          this.samples[this.index++]=Math.round(Math.max(-1,Math.min(1,this.sum/ratio))*32767);this.weight=0;this.sum=0;
          if(this.index===this.samples.length){this.port.postMessage(this.samples.buffer,[this.samples.buffer]);this.samples=new Int16Array(640);this.index=0;}
        }
      }
    }
    return true;
  }
}
registerProcessor('mic-capture',MicCapture);
