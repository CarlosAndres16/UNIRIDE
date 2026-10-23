"""Autenticacion local del conductor y comprobacion del propietario."""

from dataclasses import dataclass, field
import logging
from typing import Annotated

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from pydantic import SecretStr, ValidationError

from app.config.settings import getJwtSettings
from app.exceptions.exceptions import ErrorInterno, NoAutenticadoError, NoAutorizadoError

logger = logging.getLogger("uniride.security")
bearerScheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    bearerFormat="JWT",
    description="JWT HS256 emitido por Usuarios y Autenticacion.",
)


@dataclass(frozen=True, slots=True)
class ConductorAutenticado:
    """Contexto interno; el token queda oculto en representaciones y logs."""

    conductorId: int
    token: SecretStr = field(repr=False, compare=False)


class JwtService:
    """Verifica tokens; la emision corresponde a Usuarios y Autenticacion."""

    def __init__(self, secret: SecretStr) -> None:
        if not isinstance(secret, SecretStr) or not secret.get_secret_value().strip():
            raise ValueError("El servicio JWT necesita un secreto configurado.")
        self._secret = secret

    def validarToken(self, token: str) -> ConductorAutenticado:
        try:
            claims = jwt.decode(
                token,
                self._secret.get_secret_value(),
                algorithms=["HS256"],
                options={
                    "require": ["sub", "iat", "exp"],
                    # El contrato no define issuer ni audience.
                    "verify_aud": False,
                    "verify_iss": False,
                },
            )
            subject = claims["sub"]
            if not isinstance(subject, str) or not subject.isascii() or not subject.isdecimal():
                raise ValueError("Identificador de conductor invalido.")
            conductorId = int(subject)
            if conductorId <= 0:
                raise ValueError("Identificador de conductor invalido.")

            # PyJWT admite algunas conversiones a int; el contrato usa numeros
            # enteros JSON. Rechazar strings, bool y decimales sin coercion.
            if type(claims["iat"]) is not int or type(claims["exp"]) is not int:
                raise ValueError("Fechas del token invalidas.")
            if claims["exp"] <= claims["iat"]:
                raise ValueError("Periodo del token invalido.")
        except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError):
            # La misma respuesta publica para firma, formato y vigencia invalidos.
            raise NoAutenticadoError() from None

        return ConductorAutenticado(conductorId=conductorId, token=SecretStr(token))


def obtenerBearerToken(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearerScheme)],
) -> str:
    """Exige un unico Authorization Bearer antes de cargar la configuracion."""

    headers = request.headers.getlist("authorization")
    if len(headers) != 1 or credentials is None:
        raise NoAutenticadoError()
    scheme, separator, token = headers[0].partition(" ")
    # Bearer permite uno o mas espacios entre el esquema y el token.
    token = token.lstrip(" ")
    if not separator or scheme.lower() != "bearer" or not token or any(char.isspace() for char in token):
        raise NoAutenticadoError()
    return token


def getJwtService() -> JwtService:
    try:
        return JwtService(getJwtSettings().jwtSecret)
    except (ValidationError, ValueError):
        # No registrar la ValidationError, porque puede contener entradas.
        logger.error("No se pudo cargar la configuracion JWT del servicio.")
        raise ErrorInterno() from None


def getConductorAutenticado(
    token: Annotated[str, Depends(obtenerBearerToken)],
    jwtService: Annotated[JwtService, Depends(getJwtService)],
) -> ConductorAutenticado:
    return jwtService.validarToken(token)


def verificarPropietario(conductorIdRecurso: int, conductor: ConductorAutenticado) -> None:
    """Solo se llama despues de obtener el propietario de una fuente confiable."""

    if type(conductorIdRecurso) is not int or conductorIdRecurso != conductor.conductorId:
        raise NoAutorizadoError()
