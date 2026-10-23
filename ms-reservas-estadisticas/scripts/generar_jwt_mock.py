"""JWT de prueba local; no crea un endpoint de login ni sustituye a Usuarios."""

import argparse
import sys
import time

import jwt
from pydantic import ValidationError

from app.config.settings import getJwtSettings


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera un JWT local para probar los mocks.")
    parser.add_argument("--conductor-id", type=int, default=25)
    argumentos = parser.parse_args()
    if argumentos.conductor_id <= 0:
        parser.error("El identificador del conductor debe ser positivo.")
    try:
        secret = getJwtSettings().jwtSecret
    except ValidationError:
        print("Configura JWT_SECRET en el entorno o en .env antes de generar el token.", file=sys.stderr)
        return 1
    ahora = int(time.time())
    token = jwt.encode(
        {"sub": str(argumentos.conductor_id), "iat": ahora, "exp": ahora + 3600},
        secret.get_secret_value(),
        algorithm="HS256",
    )
    # Salida destinada a una variable de PowerShell, no a los logs del servicio.
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
