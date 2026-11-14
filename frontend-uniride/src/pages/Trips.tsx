import { useEffect, useState } from 'react';
import { ArrowDown, ArrowRight, CalendarDays, CarFront, CheckCircle2, ChevronLeft, ChevronRight, Clock3, MapPin, Pencil, Plus, Search, Users, XCircle } from 'lucide-react';
import type { Api } from '../lib/api';
import { fecha, hora } from '../lib/format';
import type { PaginaViajes, Vehiculo, Viaje } from '../types';
import { Modal, ErrorNotice, Empty, Loading, Status, Field } from '../components/UI';
import { TripForm } from '../components/TripForm';
import './trips.css';

interface Props { api: Api; onReservations: (trip: Viaje) => void; onChanged: () => void }
type Decision = { kind: 'cancel' | 'finish'; trip: Viaje };

export function Trips({ api, onReservations, onChanged }: Props) {
  const [result, setResult] = useState<PaginaViajes | null>(null);
  const [vehicles, setVehicles] = useState<Vehiculo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [vehicleError, setVehicleError] = useState<unknown>(null);
  const [revision, setRevision] = useState(0);
  const [page, setPage] = useState(1);
  const [state, setState] = useState('TODOS');
  const [from, setFrom] = useState('');
  const [until, setUntil] = useState('');
  const [search, setSearch] = useState('');
  const [form, setForm] = useState<Viaje | 'new' | null>(null);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const invalidDates = !!from && !!until && from > until;

  useEffect(() => {
    let active = true;
    api.vehicles().then(data => { if (active) { setVehicles(data.datos); setVehicleError(null); } })
      .catch(err => { if (active) setVehicleError(err); });
    return () => { active = false; };
  }, [api, revision]);

  useEffect(() => {
    let active = true;
    if (invalidDates) { setLoading(false); return; }
    setLoading(true); setError(null);
    api.trips({ estado: state, desde: from || undefined, hasta: until || undefined, pagina: page, tamano: 12 })
      .then(data => {
        if (!active) return;
        if (page > 1 && page > data.paginacion.totalPaginas) { setPage(Math.max(1, data.paginacion.totalPaginas)); return; }
        setResult(data);
      })
      .catch(err => { if (active) setError(err); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [api, page, state, from, until, revision, invalidDates]);

  function updated(message: string) {
    setForm(null); setDecision(null); setNotice(message);
    setRevision(value => value + 1); onChanged();
  }

  async function confirm() {
    if (!decision || busy) return;
    setBusy(true); setActionError(null);
    try {
      if (decision.kind === 'cancel') await api.cancelTrip(decision.trip.viajeId);
      else await api.finishTrip(decision.trip.viajeId);
      updated(decision.kind === 'cancel' ? 'Tu viaje se ha cancelado.' : 'Tu viaje se ha finalizado.');
    } catch (err) { setActionError(err); }
    finally { setBusy(false); }
  }

  const filteredTrips = (result?.datos ?? []).filter(trip => {
    const vehicle = vehicles.find(item => item.vehiculoId === trip.vehiculoId);
    const text = `${trip.origen.descripcion} ${trip.destino.descripcion} ${trip.viajeId} ${vehicle?.placa ?? ''}`;
    return text.toLocaleLowerCase('es').includes(search.trim().toLocaleLowerCase('es'));
  });

  return <>
    <div className="page-heading">
      <div><p className="eyebrow">CADA TRAYECTO CUENTA</p><h1>Mis viajes</h1><p className="muted">Tus rutas, tus horarios y más maneras de compartir el camino.</p></div>
      <button className="btn primary" onClick={() => { setNotice(''); setForm('new'); }}><Plus size={18} aria-hidden="true" />Publicar viaje</button>
    </div>
    {notice && <div className="notice trip-success" role="status"><CheckCircle2 size={18} aria-hidden="true" />{notice}<button type="button" aria-label="Cerrar aviso" onClick={() => setNotice('')}>×</button></div>}
    <div className="card trip-filters">
      <div className="trip-search"><Search size={18} aria-hidden="true" /><input aria-label="Buscar en esta página por ruta, placa o número" placeholder="Buscar una ruta en esta página…" value={search} onChange={event => setSearch(event.target.value)} /></div>
      <div className="trip-filter-fields">
        <Field label="Estado"><select value={state} onChange={event => { setState(event.target.value); setPage(1); }}><option value="TODOS">Todos los estados</option><option value="ACTIVO">Activos</option><option value="FINALIZADO">Finalizados</option><option value="CANCELADO">Cancelados</option></select></Field>
        <Field label="Desde"><input type="date" value={from} max={until || undefined} onChange={event => { setFrom(event.target.value); setPage(1); }} /></Field>
        <Field label="Hasta"><input type="date" value={until} min={from || undefined} onChange={event => { setUntil(event.target.value); setPage(1); }} /></Field>
        {(from || until || state !== 'TODOS' || search) && <button className="btn secondary small" onClick={() => { setFrom(''); setUntil(''); setState('TODOS'); setSearch(''); setPage(1); }}>Limpiar</button>}
      </div>
    </div>
    {invalidDates ? <ErrorNotice error={new Error('La fecha inicial no puede ser posterior a la fecha final.')} /> : loading ? <Loading /> : error ? <ErrorNotice error={error} retry={() => setRevision(value => value + 1)} /> : <>
      {vehicleError != null && <p className="notice">No pudimos consultar las placas. Puedes identificar cada vehículo por su número.</p>}
      <div className="trip-list-heading"><p className="muted">{result?.paginacion.totalElementos ?? 0} {(result?.paginacion.totalElementos ?? 0) === 1 ? 'viaje en tu historial' : 'viajes en tu historial'}</p><span className="muted">{search ? 'Búsqueda en la página actual' : 'Ordenados por fecha de salida'}</span></div>
      {!filteredTrips.length ? <Empty title={search ? 'No encontramos esa ruta en esta página' : 'Tu próximo viaje empieza aquí'} description={search ? 'Prueba otra búsqueda o cambia de página para consultar más viajes.' : from || until || state !== 'TODOS' ? 'No hay viajes con estos filtros. Prueba otras fechas o estados.' : 'Publica tu primera ruta y comparte el camino a la universidad.'} action={!search && !from && !until && state === 'TODOS' ? <button className="btn primary" onClick={() => setForm('new')}><Plus size={17} aria-hidden="true" />Publicar mi primer viaje</button> : undefined} /> :
        <div className="trip-grid">{filteredTrips.map(trip => {
          const vehicle = vehicles.find(item => item.vehiculoId === trip.vehiculoId);
          return <article className="card trip-card" key={trip.viajeId}>
            <div className="trip-card-top"><span className="trip-id">VIAJE #{trip.viajeId}</span><Status value={trip.estado} /></div>
            <div className="trip-route">
              <div className="trip-route-marker"><span /><i /><MapPin size={16} aria-hidden="true" /></div>
              <div className="trip-route-labels"><div><span>Origen</span><h3>{trip.origen.descripcion}</h3></div><div><span>Destino</span><h3>{trip.destino.descripcion}</h3></div></div>
              <ArrowDown size={19} className="trip-route-arrow" aria-hidden="true" />
            </div>
            <div className="trip-meta"><span><CalendarDays size={16} aria-hidden="true" />{fecha(trip.fechaSalida)}</span><span><Clock3 size={16} aria-hidden="true" />{hora(trip.horaSalida)}</span></div>
            <div className="trip-card-details"><span><CarFront size={17} aria-hidden="true" />{vehicle ? `${vehicle.placa} · ${vehicle.marca}` : `Vehículo #${trip.vehiculoId}`}</span><span><Users size={17} aria-hidden="true" /><strong>{trip.cuposDisponibles}</strong> de {trip.capacidad} cupos libres</span></div>
            <div className="trip-actions"><button className="btn secondary small trip-reservations" onClick={() => onReservations(trip)}>Ver reservas<ArrowRight size={16} aria-hidden="true" /></button>{trip.estado === 'ACTIVO' && <button className="trip-icon-button" aria-label={`Editar viaje ${trip.viajeId}`} title="Editar viaje" onClick={() => setForm(trip)}><Pencil size={17} aria-hidden="true" /></button>}</div>
            {trip.estado === 'ACTIVO' && <div className="trip-state-actions"><button onClick={() => { setActionError(null); setDecision({ kind: 'finish', trip }); }}><CheckCircle2 size={15} aria-hidden="true" />Finalizar</button><button onClick={() => { setActionError(null); setDecision({ kind: 'cancel', trip }); }}><XCircle size={15} aria-hidden="true" />Cancelar viaje</button></div>}
          </article>;
        })}</div>}
      {(result?.paginacion.totalPaginas ?? 0) > 1 && <nav className="trip-pagination" aria-label="Páginas de viajes"><button className="btn secondary small" disabled={page <= 1} onClick={() => setPage(value => value - 1)}><ChevronLeft size={17} aria-hidden="true" />Anterior</button><span>Página {page} de {result!.paginacion.totalPaginas}</span><button className="btn secondary small" disabled={page >= result!.paginacion.totalPaginas} onClick={() => setPage(value => value + 1)}>Siguiente<ChevronRight size={17} aria-hidden="true" /></button></nav>}
    </>}
    {form && <TripForm api={api} existing={form === 'new' ? undefined : form} onClose={() => { setForm(null); setRevision(value => value + 1); }} onSaved={() => updated(form === 'new' ? 'Tu viaje se ha publicado.' : 'Los cambios se han guardado.')} />}
    {decision && <Modal title={decision.kind === 'cancel' ? '¿Cancelar este viaje?' : '¿Finalizar este viaje?'} description={`${decision.trip.origen.descripcion} → ${decision.trip.destino.descripcion}`} onClose={() => { if (!busy) setDecision(null); }}>
      <p>{decision.kind === 'cancel' ? 'El viaje pasará a Cancelado y dejará de aparecer entre tus viajes activos. Esta acción no se puede deshacer desde la aplicación.' : 'Confirma que ya terminaste el recorrido. El viaje pasará a Finalizado y ya no podrás modificarlo.'}</p>
      {actionError != null && <ErrorNotice error={actionError} />}
      <div className="form-actions"><button className="btn secondary" disabled={busy} onClick={() => setDecision(null)}>Volver</button><button className={`btn ${decision.kind === 'cancel' ? 'danger' : 'primary'}`} disabled={busy} onClick={confirm}>{busy ? 'Procesando…' : decision.kind === 'cancel' ? 'Sí, cancelar viaje' : 'Sí, finalizar viaje'}</button></div>
    </Modal>}
  </>;
}
