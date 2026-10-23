"""Registra un conductor de desarrollo usando el mismo servicio que la API."""

import argparse
import getpass

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config.database import getEngine
from app.config.settings import getSettings
from app.exceptions.exceptions import AppException
from app.repositories.conductor_repository import ConductorRepository
from app.schemas.auth_schema import RegistrarConductorRequest
from app.security.jwt_service import JWTService
from app.security.password_service import PasswordService
from app.services.auth_service import AuthService


def main() -> None:
    parser = argparse.ArgumentParser(description="Registrar un conductor de desarrollo.")
    parser.add_argument("--nombre", required=True)
    parser.add_argument("--correo", required=True)
    parser.add_argument("--telefono", default=None)
    args = parser.parse_args()

    password = getpass.getpass("Contraseña del conductor (no se mostrará): ")
    confirmation = getpass.getpass("Confirme la contraseña: ")
    if password != confirmation:
        raise SystemExit("Las contraseñas no coinciden.")
    try:
        request = RegistrarConductorRequest(
            nombre=args.nombre,
            correo=args.correo,
            password=password,
            telefono=args.telefono,
        )
        settings = getSettings()
    except ValidationError:
        raise SystemExit(
            "Datos o configuración inválidos. Revise nombre, correo, teléfono, "
            "contraseña de al menos 8 caracteres y variables del archivo .env."
        ) from None
    finally:
        del password, confirmation

    engine = getEngine()
    try:
        with Session(engine, expire_on_commit=False) as session:
            repository = ConductorRepository(session)
            if repository.buscarPorCorreo(str(request.correo)) is not None:
                print("El correo ya está registrado; no se modificaron sus datos.")
                return
            service = AuthService(repository, PasswordService(), JWTService(settings))
            conductor = service.registrar(request)
            print(f"Conductor de desarrollo registrado con id {conductor.conductorId}.")
    except AppException as error:
        if error.error == "CORREO_YA_REGISTRADO":
            print("El correo ya está registrado; no se modificaron sus datos.")
            return
        raise SystemExit(error.message) from None
    except SQLAlchemyError:
        raise SystemExit("No se pudo registrar el conductor. Revise la base y sus migraciones.") from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
