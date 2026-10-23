"""Comprueba la presencia del secreto compartido sin imprimirlo."""

from pydantic import ValidationError

from app.config.settings import getJwtSettings


def main() -> int:
    try:
        getJwtSettings()
    except ValidationError:
        print("Configuracion JWT pendiente: define JWT_SECRET con el valor privado del equipo.")
        return 1
    print("JWT_SECRET configurado. Su valor permanece oculto.")
    print("Esta comprobacion no confirma que coincida con los otros microservicios.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
