"""Informe idempotente de la ocupacion detectada durante una consulta valida."""

import logging

from app.clients.viajes_client import ViajesClient
from app.exceptions.exceptions import ExcepcionAplicacion
from app.schemas.integracion_schema import EstadoViaje, ViajeExterno

logger = logging.getLogger("uniride.services.ocupacion")


async def sincronizarOcupacion(
    viaje: ViajeExterno,
    pasajerosConfirmados: int,
    viajesClient: ViajesClient,
    correlationId: str,
) -> None:
    """Un fallo de este informe nunca invalida la lectura del conductor.

    La version 1 solo lee reservas: los cambios hechos fuera de la API se
    detectan en la siguiente consulta. Se compara con la disponibilidad recien
    obtenida de Viajes, sin cache que sobreviva a un reinicio de sus mocks.
    """

    if viaje.estado != EstadoViaje.ACTIVO:
        return
    if type(pasajerosConfirmados) is not int or pasajerosConfirmados < 0:
        logger.error(
            "No se pudo informar la ocupacion a Viajes: total interno invalido.",
            extra={"correlationId": correlationId},
        )
        return

    # Evita escrituras si Viajes ya representa el mismo total. Si las reservas
    # exceden la capacidad, se envia el total real: nunca se oculta el exceso
    # reduciendo cuposOcupados para que el proveedor acepte la operacion.
    if (
        pasajerosConfirmados <= viaje.capacidad
        and viaje.cuposDisponibles == viaje.capacidad - pasajerosConfirmados
    ):
        return

    try:
        # El cliente aplica el unico reintento permitido y usa X-Service-Key,
        # sin reenviar el JWT del conductor a esta operacion interna.
        await viajesClient.actualizarOcupacion(
            viaje.viajeId, pasajerosConfirmados, correlationId
        )
        logger.info(
            "Ocupacion informada a Viajes para viajeId=%s.",
            viaje.viajeId,
            extra={"correlationId": correlationId},
        )
    except ExcepcionAplicacion as error:
        logger.warning(
            "No se pudo informar la ocupacion a Viajes para viajeId=%s: "
            "status=%s codigo=%s. Se volvera a intentar en una consulta posterior.",
            viaje.viajeId,
            error.status,
            error.error.value,
            extra={"correlationId": correlationId},
        )
    except Exception:
        # No registrar el objeto excepcion, que podria contener credenciales
        # o datos de solicitudes. CancelledError no deriva de Exception.
        logger.error(
            "Fallo interno al informar la ocupacion a Viajes para viajeId=%s. "
            "Se volvera a intentar en una consulta posterior.",
            viaje.viajeId,
            extra={"correlationId": correlationId},
        )
