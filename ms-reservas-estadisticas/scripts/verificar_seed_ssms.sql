-- Abrir en SQL Server Management Studio y ejecutar con F5.
-- Las fechas DATETIME2 se almacenan como UTC.
USE [unirride_reservas];
GO

SELECT
    id,
    viaje_id,
    pasajero_nombre,
    cupos_reservados,
    estado,
    fecha_reserva
FROM dbo.reservas
WHERE viaje_id = 305
ORDER BY id;

SELECT
    COUNT(*) AS totalReservas,
    COUNT(CASE WHEN estado = N'CONFIRMADA' THEN 1 END) AS reservasConfirmadas,
    COUNT(CASE WHEN estado = N'CANCELADA' THEN 1 END) AS reservasCanceladas,
    COALESCE(SUM(CASE
        WHEN estado = N'CONFIRMADA' THEN cupos_reservados
        ELSE 0
    END), 0) AS pasajerosConfirmados
FROM dbo.reservas
WHERE viaje_id = 305;

-- Sin filas cuando no hay duplicados de las claves utilizadas por este seed.
SELECT
    viaje_id,
    pasajero_nombre,
    fecha_reserva,
    COUNT(*) AS coincidencias
FROM dbo.reservas
WHERE viaje_id = 305
GROUP BY viaje_id, pasajero_nombre, fecha_reserva
HAVING COUNT(*) > 1;
