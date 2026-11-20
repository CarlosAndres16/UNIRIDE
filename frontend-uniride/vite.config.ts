import {defineConfig,loadEnv} from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig(({mode})=>{
  const env=loadEnv(mode,process.cwd(),'');
  const target=env.GATEWAY_URL||'http://127.0.0.1:8080';
  const gateway=new URL(target);
  if(!['http:','https:'].includes(gateway.protocol)||gateway.username||gateway.password||gateway.pathname!=='/'||gateway.search||gateway.hash)throw new Error('GATEWAY_URL debe ser un origen HTTP sin credenciales ni rutas.');
  const proxy={'/api':{target,changeOrigin:true}};
  const host=env.FRONTEND_HOST||'0.0.0.0';
  const port=Number(env.FRONTEND_PORT||3000);
  if(!Number.isInteger(port)||port<1||port>65535)throw new Error('FRONTEND_PORT debe estar entre 1 y 65535.');
  return {plugins:[react()],server:{host,port,strictPort:true,proxy},preview:{host,port,strictPort:true,proxy}};
});
