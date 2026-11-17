export const modeLabels={inline:"Conversation model alone",background:"With background researcher"};
export const sequences={1:[['robot','X'],['phone','Y']],2:[['phone','X'],['robot','Y']],3:[['robot','Y'],['phone','X']],4:[['phone','Y'],['robot','X']]};
export const tasks={
  X:{title:'An exhibition sign.',description:'You want a small sign with cut lettering and an engraved detail. Use the project file and sample materials to prepare a plan to discuss with shop staff. Work out what is ready, what needs changing, and what still needs checking.'},
  Y:{title:'Labels for a project.',description:'You want a set of project labels with a cut outline and an engraved symbol. Use the project file and sample materials to prepare a plan to discuss with shop staff. Work out what is ready, what needs changing, and what still needs checking.'},
  practice:{title:'Start with an idea.',description:'Tell Ari about something you might like to make. Ask a follow-up, and try interrupting a response. This is a practice conversation; no machine operation.'}
};
export const ratingItems=[
  ['clarity','I could understand the assistance.'],['comfort','I felt comfortable saying I was confused.'],
  ['effort','It took effort to keep the conversation going.'],['uncertainty','I could tell when the assistant was uncertain.'],
  ['verification','I knew when I needed to check with staff.'],['presence','I felt that I was interacting with a socially present partner.']
];
export function csvCell(value){return '"'+String(value??'').replaceAll('"','""')+'"';}
export function eventsCsv(record){
  const columns=['session_id','participant','interface','mode','task','engine','time','elapsed_ms','clock','event','fields'];
  const lines=record.events.map(entry=>[entry.session_id||record.id,record.participant,record.interface,record.mode,record.task,record.engine,entry.time,entry.elapsed_ms,entry.clock,entry.event,JSON.stringify(Object.fromEntries(Object.entries(entry).filter(([key])=>!['session_id','time','elapsed_ms','clock','event'].includes(key))))]);
  return [columns,...lines].map(line=>line.map(csvCell).join(',')).join('\r\n');
}
