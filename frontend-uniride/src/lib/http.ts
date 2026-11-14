import { uuid } from './uuid.ts';
export class ApiError extends Error {
  status: number;
  correlationId?: string;
  detalles: { campo: string; problema: string }[];
  constructor(message: string, status = 0, correlationId?: string, detalles: {campo: string; problema: string}[] = []) {
    super(message); this.name = 'ApiError'; this.status = status; this.correlationId = correlationId; this.detalles = detalles;
  }
}
export interface RequestOptions { method?: string; body?: unknown; token?: string; headers?: Record<string, string>; signal?: AbortSignal; timeoutMs?: number }
/** No automatic retries: a timed-out mutation may already have been committed. */
export async function request<T>(base: string, path: string, options: RequestOptions = {}): Promise<T> {
  const controller = new AbortController();
  const correlationId = uuid();
  const abort = () => controller.abort();
  if (options.signal?.aborted) abort();
  options.signal?.addEventListener('abort', abort, { once: true });
  const timeout = setTimeout(abort, options.timeoutMs ?? 25000);
  try {
    const response = await fetch(`${base.replace(/\/$/, '')}${path}`, {
      method: options.method ?? 'GET', signal: controller.signal, cache: 'no-store',
      headers: { Accept: 'application/json', 'X-Correlation-Id': correlationId,
        ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}), ...options.headers },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    const responseId = response.headers.get('X-Correlation-Id') ?? correlationId;
    const text = response.status === 204 ? '' : await response.text();
    let data: Record<string, unknown> | undefined;
    try { data = text ? JSON.parse(text) : undefined; } catch { /* Safe message below for a gateway HTML error. */ }
    if (!response.ok) {
      const message = typeof data?.message === 'string' ? data.message :
        response.status === 401 ? 'Tu sesión terminó. Vuelve a iniciar sesión.' :
        response.status === 409 || response.status === 412 ? 'El registro cambió o entra en conflicto. Actualiza los datos e inténtalo de nuevo.' :
        response.status >= 500 ? 'El servicio no está disponible. Comprueba el Gateway y los microservicios.' : `No se pudo completar la solicitud (${response.status}).`;
      throw new ApiError(message, response.status, typeof data?.correlationId === 'string' ? data.correlationId : responseId,
        Array.isArray(data?.detalles) ? data.detalles.filter((x): x is {campo: string; problema: string} => typeof x?.campo === 'string' && typeof x?.problema === 'string') : []);
    }
    if (response.status !== 204 && !data) throw new ApiError('El servicio devolvió una respuesta inesperada.', response.status, responseId);
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (options.signal?.aborted) throw error;
    throw new ApiError(controller.signal.aborted ? 'La solicitud tardó demasiado. Si estabas guardando, consulta los datos antes de volver a intentarlo.' : 'No fue posible conectar. Comprueba que el Gateway esté iniciado y que la dirección configurada sea correcta.', 0, correlationId);
  } finally { clearTimeout(timeout); options.signal?.removeEventListener('abort', abort); }
}
export function query(values: Record<string, unknown>) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
  return params.size ? `?${params}` : '';
}
