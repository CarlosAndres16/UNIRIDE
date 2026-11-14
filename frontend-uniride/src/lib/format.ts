export const fecha = (value: string) => new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value.slice(0,10)}T12:00:00`));
export const hora = (value: string) => value.slice(0,5);
export const hoy = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; };
export const iniciales = (value: string) => value.trim().split(/\s+/).slice(0,2).map(s => s[0]).join('').toUpperCase();
export const estadoTexto = (value: string) => ({ ACTIVO:'Activo', INACTIVO:'Inactivo', FINALIZADO:'Finalizado', CANCELADO:'Cancelado', CONFIRMADA:'Confirmada', CANCELADA:'Cancelada', PENDIENTE:'Pendiente' }[value] ?? value);
