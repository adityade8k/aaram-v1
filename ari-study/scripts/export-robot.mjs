import { writeFile,mkdir } from 'node:fs/promises';
import { sessionConfig } from '../server/policy.mjs';
for(const mode of ['inline','background']){
  const directory=new URL('../robot/prompts/',import.meta.url);await mkdir(directory,{recursive:true});
  const prompt=sessionConfig(mode,{}).instructions;
  await writeFile(new URL(`${mode}.txt`,directory),`${prompt}\n`);
}
console.log('Shared prompt snapshots exported for audit. No robot configuration changed.');
