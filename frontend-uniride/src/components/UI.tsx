import { useEffect, useRef, useState, type ReactNode, type DependencyList } from 'react';
import { AlertCircle, ArrowRight, LoaderCircle, X, Route } from 'lucide-react';
import { ApiError } from '../lib/http';
import { estadoTexto } from '../lib/format';
import { uuid } from '../lib/uuid';

export function Logo() { return <span className="brand"><span className="brand-mark"><Route size={23}/></span><span>uni<span className="brand-light">ride</span><span className="brand-dot">.</span></span></span>; }
export function Status({value}: {value:string}) { return <span className={`status ${value.toLowerCase()}`}><i/>{estadoTexto(value)}</span>; }
export function Field({label,children,hint}: {label:string;children:ReactNode;hint?:string}) { return <label className="field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>; }
export function Loading() { return <div className="loading" role="status"><LoaderCircle className="spin" size={24}/>Cargando tus datos…</div>; }
export function Empty({title,description,action}: {title:string;description:string;action?:ReactNode}) { return <div className="empty"><span className="empty-icon"><Route size={30}/></span><h3>{title}</h3><p>{description}</p>{action}</div>; }
export function ErrorNotice({error,retry}: {error:unknown;retry?:()=>void}) {
  if (!error) return null;
  return <div className="error-notice" role="alert"><AlertCircle size={20}/><div><strong>{error instanceof Error ? error.message : 'Ocurrió un error inesperado.'}</strong>{error instanceof ApiError && <>{error.detalles.length>0 && <ul>{error.detalles.map((d,i)=><li key={i}>{d.campo}: {d.problema}</li>)}</ul>}{error.correlationId && <small>Referencia: {error.correlationId}</small>}</>}{retry && <button className="text-button" onClick={retry}>Volver a cargar <ArrowRight size={15}/></button>}</div></div>;
}
export function Modal({title,description,onClose,children,wide=false}: {title:string;description?:string;onClose:()=>void;children:ReactNode;wide?:boolean}) {
  const ref=useRef<HTMLDialogElement>(null);
  const id=useRef(uuid()).current;
  useEffect(()=>{const dialog=ref.current;dialog?.showModal();return()=>dialog?.close();},[]);
  return <dialog ref={ref} className={`modal ${wide?'wide':''}`} aria-labelledby={id} onCancel={e=>{e.preventDefault();onClose();}} onClick={e=>{if(e.target===e.currentTarget)onClose();}}><div className="modal-head"><div><h2 id={id}>{title}</h2>{description&&<p>{description}</p>}</div><button className="icon-button" type="button" aria-label="Cerrar ventana" onClick={onClose}><X size={21}/></button></div>{children}</dialog>;
}
export function useResource<T>(loader:()=>Promise<T>, deps:DependencyList) {
  const [data,setData]=useState<T>(); const [error,setError]=useState<unknown>(); const [loading,setLoading]=useState(true); const [version,setVersion]=useState(0);
  useEffect(()=>{let active=true; setLoading(true);setError(undefined);setData(undefined);loader().then(v=>{if(active)setData(v);}).catch(e=>{if(active)setError(e);}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[...deps,version]);
  return {data,error,loading,reload:()=>setVersion(v=>v+1)};
}
