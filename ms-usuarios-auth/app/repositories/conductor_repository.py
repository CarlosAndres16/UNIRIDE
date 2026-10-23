"""Persistencia de conductores; no contiene reglas HTTP ni hashing."""

import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.conductor import Conductor


def esCorreoDuplicado(error: IntegrityError) -> bool:
    """Identifica exclusivamente la restricción única de correo en SQL Server."""
    originalMessage = " ".join(str(value) for value in getattr(error.orig, "args", ()))
    return bool(re.search(r"\b(?:2601|2627)\b", originalMessage)) and (
        "uq_conductores_correo" in originalMessage.lower()
    )


class ConductorRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def buscarPorCorreo(self, correo: str) -> Conductor | None:
        statement = select(Conductor).where(Conductor.correo == correo.strip().lower())
        return self.session.scalar(statement)

    def buscarPorId(self, conductorId: int) -> Conductor | None:
        return self.session.get(Conductor, conductorId)

    def crear(
        self, nombre: str, correo: str, passwordHash: str, telefono: str | None
    ) -> Conductor:
        conductor = Conductor(
            nombre=nombre,
            correo=correo.strip().lower(),
            password_hash=passwordHash,
            telefono=telefono,
        )
        try:
            self.session.add(conductor)
            self.session.commit()
            self.session.refresh(conductor)
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return conductor

    def actualizar(
        self, conductor: Conductor, nombre: str, telefono: str | None
    ) -> Conductor:
        try:
            conductor.nombre = nombre
            conductor.telefono = telefono
            self.session.commit()
            self.session.refresh(conductor)
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return conductor
