// ISO-8601 en UTC sin milisegundos: 2026-10-01T14:20:00Z
function aIsoUtc(fecha) {
  return new Date(fecha).toISOString().replace(/\.\d{3}Z$/, 'Z');
}

module.exports = { aIsoUtc };