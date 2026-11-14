import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { MapPin, Navigation, Save } from 'lucide-react';
import type { Api } from '../lib/api';
import { hoy } from '../lib/format';
import { ApiError } from '../lib/http';
import { uuid } from '../lib/uuid';
import type { Vehiculo, Viaje, ViajeInput } from '../types';
import { Modal, ErrorNotice, Empty, Loading, Field } from './UI';

interface Props { api: Api; existing?: Viaje; onClose: () => void; onSaved: () => void }

const formValues = (trip?: Viaje) => ({
  vehiculoId: trip ? String(trip.vehiculoId) : '',
  origen: trip?.origen.descripcion ?? '',
  origenLat: trip ? String(trip.origen.latitud) : '',
  origenLon: trip ? String(trip.origen.longitud) : '',
  destino: trip?.destino.descripcion ?? '',
  destinoLat: trip ? String(trip.destino.latitud) : '',
  destinoLon: trip ? String(trip.destino.longitud) : '',
  fechaSalida: trip?.fechaSalida.slice(0, 10) ?? hoy(),
  horaSalida: trip?.horaSalida.slice(0, 5) ?? '',
  capacidad: String(trip?.capacidad ?? 4),
});

export function TripForm({ api, existing, onClose, onSaved }: Props) {
  const [vehicles, setVehicles] = useState<Vehiculo[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [snapshot, setSnapshot] = useState(existing);
  const [form, setForm] = useState(() => formValues(existing));
  const [conflicted, setConflicted] = useState(false);
  const [refreshed, setRefreshed] = useState(false);
  const operation = useRef<{ body: string; key: string } | null>(null);
  const saving = useRef(false);

  useEffect(() => {
    let active = true;
    setLoading(true); setLoadError(null);
    api.vehicles().then(data => { if (active) setVehicles(data.datos); })
      .catch(err => { if (active) setLoadError(err); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [api, attempt]);

  const change = (field: keyof typeof form, value: string) => { setForm(previous => ({ ...previous, [field]: value })); setRefreshed(false); };
  const activeVehicles = vehicles.filter(vehicle => vehicle.estado === 'ACTIVO');
  const currentVehicle = vehicles.find(vehicle => vehicle.vehiculoId === Number(form.vehiculoId));
  const maxCapacity = Math.min(8, currentVehicle?.capacidad ?? 8);
  const missingCurrent = !!snapshot && !activeVehicles.some(vehicle => vehicle.vehiculoId === snapshot.vehiculoId);
  const editable = !snapshot || snapshot.estado === 'ACTIVO';

  async function refreshTrip() {
    if (!snapshot || saving.current) return;
    saving.current = true; setBusy(true);
    try {
      const current = await api.trip(snapshot.viajeId);
      setSnapshot(current); setForm(formValues(current)); setError(null);
      setConflicted(false); setRefreshed(true);
    } catch (err) { setError(err); }
    finally { saving.current = false; setBusy(false); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving.current) return;
    if (!editable) { setError(new Error('Este viaje ya no está activo y no se puede editar.')); return; }
    setError(null);
    const body: ViajeInput = {
      vehiculoId: Number(form.vehiculoId),
      origen: { descripcion: form.origen.trim(), latitud: Number(form.origenLat), longitud: Number(form.origenLon) },
      destino: { descripcion: form.destino.trim(), latitud: Number(form.destinoLat), longitud: Number(form.destinoLon) },
      fechaSalida: form.fechaSalida,
      horaSalida: form.horaSalida,
      capacidad: Number(form.capacidad),
    };
    if (!Number.isInteger(body.vehiculoId) || body.vehiculoId < 1 || !body.origen.descripcion || !body.destino.descripcion) {
      setError(new Error('Completa el vehículo, el origen y el destino del viaje.')); return;
    }
    if (!Number.isInteger(body.capacidad) || body.capacidad < 1 || body.capacidad > maxCapacity) {
      setError(new Error(`La capacidad debe estar entre 1 y ${maxCapacity} cupos.`)); return;
    }
    for (const point of [body.origen, body.destino]) {
      if (!Number.isFinite(point.latitud) || !Number.isFinite(point.longitud) || Math.abs(point.latitud) > 90 || Math.abs(point.longitud) > 180) {
        setError(new Error('Revisa las coordenadas: latitud entre −90 y 90; longitud entre −180 y 180.')); return;
      }
    }
    const serialized = JSON.stringify(body);
    if (operation.current?.body !== serialized) operation.current = { body: serialized, key: uuid() };
    saving.current = true; setBusy(true);
    try {
      await api.saveTrip(body, operation.current!.key, snapshot);
      onSaved();
    } catch (err) { setError(err); setConflicted(!!snapshot && err instanceof ApiError && (err.status === 409 || err.status === 412)); }
    finally { saving.current = false; setBusy(false); }
  }

  return <Modal title={existing ? 'Editar viaje' : 'Publicar un viaje'} description="Comparte tu ruta y ayuda a alguien más a llegar." onClose={() => { if (!busy) onClose(); }} wide>
    {loading ? <Loading /> : loadError ? <ErrorNotice error={loadError} retry={() => setAttempt(value => value + 1)} /> : !activeVehicles.length && !existing ?
      <Empty title="Primero, registra tu vehículo" description="Necesitas un vehículo activo para publicar tu primer viaje. Puedes añadirlo desde Mis vehículos." action={<button className="btn secondary" onClick={onClose}>Entendido</button>} /> :
      <form onSubmit={submit} className="stack">
        {!editable && <p className="notice" role="status">Este viaje ya no está activo. Puedes consultar sus datos, pero no modificarlos.</p>}
        {refreshed && editable && <p className="success-notice" role="status">Se cargó la versión actual. Revisa los datos y vuelve a aplicar los cambios que necesites.</p>}
        <fieldset disabled={busy || !editable} className="trip-form-fields">
          <div className="form-grid two">
            <Field label="Vehículo">
              <select required value={form.vehiculoId} onChange={event => change('vehiculoId', event.target.value)}>
                <option value="">Selecciona un vehículo</option>
                {missingCurrent && <option value={snapshot!.vehiculoId}>Vehículo #{snapshot!.vehiculoId} · actual</option>}
                {activeVehicles.map(vehicle => <option key={vehicle.vehiculoId} value={vehicle.vehiculoId}>{vehicle.placa} · {vehicle.marca} {vehicle.modelo}</option>)}
              </select>
            </Field>
            <Field label="Cupos ofrecidos" hint={`Entre 1 y ${maxCapacity}, según tu vehículo.`}>
              <input type="number" required min={1} max={maxCapacity} step={1} value={form.capacidad} onChange={event => change('capacidad', event.target.value)} />
            </Field>
          </div>
          <div className="trip-form-point">
            <h3><MapPin size={18} aria-hidden="true" /> Punto de salida</h3>
            <Field label="Descripción del origen"><input required value={form.origen} onChange={event => change('origen', event.target.value)} placeholder="Ej. Entrada principal de la universidad" /></Field>
            <div className="form-grid two">
              <Field label="Latitud del origen"><input type="number" required min={-90} max={90} step="any" value={form.origenLat} onChange={event => change('origenLat', event.target.value)} placeholder="Ej. 4.6097" /></Field>
              <Field label="Longitud del origen"><input type="number" required min={-180} max={180} step="any" value={form.origenLon} onChange={event => change('origenLon', event.target.value)} placeholder="Ej. -74.0817" /></Field>
            </div>
          </div>
          <div className="trip-form-point">
            <h3><Navigation size={18} aria-hidden="true" /> Punto de llegada</h3>
            <Field label="Descripción del destino"><input required value={form.destino} onChange={event => change('destino', event.target.value)} placeholder="Ej. Biblioteca central" /></Field>
            <div className="form-grid two">
              <Field label="Latitud del destino"><input type="number" required min={-90} max={90} step="any" value={form.destinoLat} onChange={event => change('destinoLat', event.target.value)} placeholder="Ej. 4.6120" /></Field>
              <Field label="Longitud del destino"><input type="number" required min={-180} max={180} step="any" value={form.destinoLon} onChange={event => change('destinoLon', event.target.value)} placeholder="Ej. -74.0900" /></Field>
            </div>
          </div>
          <p className="muted trip-coordinate-help">Puedes copiar las coordenadas desde tu aplicación de mapas. El primer número es la latitud y el segundo, la longitud.</p>
          <div className="form-grid two">
            <Field label="Fecha de salida"><input type="date" required value={form.fechaSalida} onChange={event => change('fechaSalida', event.target.value)} /></Field>
            <Field label="Hora de salida"><input type="time" required value={form.horaSalida} onChange={event => change('horaSalida', event.target.value)} /></Field>
          </div>
        </fieldset>
        {error != null && <ErrorNotice error={error} />}
        {conflicted && <div className="notice"><p>Consulta la versión actual antes de reintentar. Esto reemplazará los datos del formulario y descartará tus cambios sin guardar.</p><button type="button" className="btn secondary small" disabled={busy} onClick={refreshTrip}>{busy ? 'Actualizando…' : 'Actualizar datos del viaje'}</button></div>}
        <div className="form-actions"><button type="button" className="btn secondary" disabled={busy} onClick={onClose}>{editable ? 'Cancelar' : 'Cerrar'}</button>{editable && <button type="submit" className="btn primary" disabled={busy}><Save size={17} aria-hidden="true" />{busy ? 'Guardando…' : existing ? 'Guardar cambios' : 'Publicar viaje'}</button>}</div>
      </form>}
  </Modal>;
}
