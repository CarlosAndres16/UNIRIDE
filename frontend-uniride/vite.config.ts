import {defineConfig,loadEnv} from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig(({mode})=>{
  const env=loadEnv(mode,process.cwd(),'');
  const target=env.GATEWAY_URL||'http://127.0.0.1:8080';
  const gateway=new URL(target);
  if(!['http:','https:'].includes(gateway.protocol)||gateway.username||gateway.password||gateway.pathname!=='/'||gateway.search||gateway.hash)throw new Error('GATEWAY_URL debe ser un origen HTTP sin credenciales ni rutas.');
  const proxy={'/api':{target,changeOrigin:true}};
  return {plugins:[react()],server:{host:'localhost',port:3000,strictPort:true,proxy},preview:{host:'localhost',port:3000,strictPort:true,proxy}};
});
