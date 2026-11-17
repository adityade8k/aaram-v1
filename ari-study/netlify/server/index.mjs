import { createApp } from '../../server/app.mjs';
export const config={path:'/api/*',scale:{min:0,max:1}};
export default createApp();
