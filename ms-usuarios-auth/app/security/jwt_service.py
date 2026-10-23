"""Emisión y validación local de JWT HS256 sin roles."""

import re
from datetime import UTC, datetime

import jwt
from jwt.exceptions import InvalidTokenError

from app.config.settings import Settings
from app.exceptions.exceptions import AppException


class JWTService:
    def __init__(self, settings: Settings) -> None:
        self._secret = settings.JWT_SECRET.get_secret_value()
        self.expiresIn = settings.JWT_EXPIRES_IN_SECONDS

    def generarToken(self, conductorId: int) -> str:
        if type(conductorId) is not int or not 1 <= conductorId <= 2_147_483_647:
            raise ValueError("conductorId debe ser un entero positivo compatible con SQL INT.")
        issuedAt = int(datetime.now(UTC).timestamp())
        return jwt.encode(
            {"sub": str(conductorId), "iat": issuedAt, "exp": issuedAt + self.expiresIn},
            self._secret,
            algorithm="HS256",
        )

    def validarToken(self, token: str) -> int:
        try:
            if not isinstance(token, str) or not token:
                raise ValueError("Token ausente.")
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                options={"require": ["sub", "iat", "exp"], "verify_iat": False},
            )
            subject = claims["sub"]
            issuedAt = claims["iat"]
            expiresAt = claims["exp"]
            now = int(datetime.now(UTC).timestamp())
            if not isinstance(subject, str) or re.fullmatch(r"[0-9]+", subject) is None:
                raise ValueError("Subject inválido.")
            conductorId = int(subject)
            if not 1 <= conductorId <= 2_147_483_647:
                raise ValueError("Subject fuera del rango permitido.")
            if type(issuedAt) is not int or type(expiresAt) is not int:
                raise ValueError("Los timestamps del token deben ser enteros.")
            if issuedAt > now or expiresAt <= issuedAt:
                raise ValueError("Intervalo de validez inválido.")
            return conductorId
        except (InvalidTokenError, TypeError, ValueError, OverflowError):
            raise AppException(
                status=401,
                error="NO_AUTENTICADO",
                message="Se requiere un token Bearer válido y vigente.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None
