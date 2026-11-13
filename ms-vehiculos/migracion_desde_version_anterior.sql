-- Úsalo UNA vez si ya tienes datos creados con la versión anterior
-- (vehiculo_id / usuario_id). Si prefieres empezar limpio: docker compose down -v
BEGIN;
ALTER TABLE vehiculos RENAME COLUMN vehiculo_id TO id;
ALTER TABLE vehiculos RENAME COLUMN usuario_id TO conductor_id;
ALTER INDEX IF EXISTS idx_vehiculos_usuario_id RENAME TO idx_vehiculos_conductor_id;
ALTER TABLE vehiculos
    ADD COLUMN IF NOT EXISTS fecha_creacion      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE vehiculos DROP CONSTRAINT IF EXISTS vehiculos_capacidad_check;
ALTER TABLE vehiculos ADD CONSTRAINT vehiculos_capacidad_check CHECK (capacidad >= 1);
COMMIT;
