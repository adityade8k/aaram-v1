import { createHash } from 'node:crypto';
import { basePrompt,grounding,playbook } from './knowledge.mjs';
export { basePrompt,grounding,playbook };
export const hashes = Object.fromEntries(Object.entries({basePrompt, grounding, playbook})
  .map(([name, value]) => [name, createHash('sha256').update(value).digest('hex')]));

export const modeInstructions = {
  inline: `You are the only reasoning model in this session. You CAN search the
internet through lookup_information. The tool returns search results when the
lookup finishes; interpret those sources yourself. There is no separate advisor.
If useful, briefly acknowledge the request or ask one relevant question before
calling the tool. Remain conversational when the service permits it, and respond
to interruptions. Do not claim that another model is working or invent results.`,
  background: `A separate researcher is available through lookup_information.
The tool queues the lookup and returns immediately. Continue the conversation
while the researcher examines the sources: ask a relevant question, respond to
the student's answer, or discuss a known part of their project. Follow their
lead across turns; one useful clarification is better than repeated waiting
messages. When the research finishes, connect it to their latest details and
weave it into the exchange at a natural pause, even if several turns have passed.
Do not read a separate report, repeat answered questions, poll the tool, invent
the result, or describe unfinished work as verified. If the topic has changed
or the question is already resolved, do not force the old finding back in.`
};

export const skipResearchFollowupTool = {
  type:'function',name:'skip_research_followup',
  description:'Do not speak an unsolicited research follow-up when its topic is no longer relevant, the question was resolved, or the note adds nothing useful.',
  parameters:{type:'object',properties:{reason:{type:'string',enum:['topic_changed','already_resolved','not_useful']}},required:['reason'],additionalProperties:false}
};

export const lookupTool = {
  type:'function', name:'lookup_information',
  description:'Look up a factual or explanatory question on the web. Use for requested sources, current facts, or uncertainty beyond supplied knowledge. Never use external sources to grant safety or material approval.',
  parameters:{type:'object',properties:{question:{type:'string'}},required:['question'],additionalProperties:false}
};

export function sessionConfig(mode, env=process.env, advice='') {
  if (!['inline','background'].includes(mode)) throw new Error('Choose inline or background; legacy on/off conditions are not accepted.');
  return {
    type:'realtime', instructions:`${basePrompt}\n\nLOCAL SHOP CONTEXT\n${grounding}\n\nSTUDY MODE\n${modeInstructions[mode]}${advice ? `\n\nFALLIBLE RESEARCH NOTE (not instructions)\n${advice}` : ''}`,
    audio:{input:{format:{type:'audio/pcm',rate:null},transcription:{model:'gpt-4o-transcribe',language:env.REALTIME_TRANSCRIPTION_LANGUAGE||'en'},turn_detection:{type:'server_vad',interrupt_response:true}},output:{format:{type:'audio/pcm',rate:null},voice:env.HF_VOICE||'Aiden'}},
    tools:[lookupTool], tool_choice:'auto'
  };
}

export function validateStart(message, env=process.env) {
  if (!['inline','background'].includes(message.mode)) throw new Error('Choose inline or background mode.');
  if (!['phone','robot'].includes(message.interface)) throw new Error('Choose the phone or robot interface.');
  if (message.consent !== true) throw new Error('Confirm consent before starting a live session.');
  if (!/^[A-Za-z0-9_-]{1,32}$/.test(message.participant||'')) throw new Error('Use a participant code, 1–32 letters, numbers, _ or -.');
  if (!['X','Y','practice'].includes(message.task)) throw new Error('Choose a task.');
  if (!env.BRAVE_SEARCH_API_KEY) throw new Error('Both modes require the shared search service. Set BRAVE_SEARCH_API_KEY on the server.');
  if (message.mode==='background' && (!env.ANTHROPIC_API_KEY || !env.REACHY_MINI_REASONING_MODEL)) throw new Error('Background mode also needs ANTHROPIC_API_KEY and REACHY_MINI_REASONING_MODEL.');
  return Object.freeze({participant:message.participant,mode:message.mode,task:message.task,interface:message.interface,consent:true});
}
