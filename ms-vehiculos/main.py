
import os

import psycopg
from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation, OperationalError
from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field


app = FastAPI(
    title="UniRide - Microservicio de Vehículos",
    description="API REST para administrar los vehículos de UniRide.",
    version="1.0.0",
)


def conectar():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "uniride_vehiculos"),
        user=os.getenv("DB_USER", "uniride"),
        password=os.getenv("DB_PASSWORD", "uniride_local_dev"),
        row_factory=dict_row,
        connect_timeout=3,
    )


class VehiculoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario_id: int = Field(gt=0)
    placa: str = Field(min_length=1, max_length=10)
    marca: str = Field(min_length=1, max_length=50)
    modelo: str = Field(min_length=1, max_length=50)
    color: str = Field(min_length=1, max_length=30)
    tipo: str = Field(min_length=1, max_length=30)
    capacidad: int = Field(gt=0)
    estado: str = "ACTIVO"

    def normalizar(self):
        datos = self.model_dump()

        for campo in ("placa", "marca", "modelo", "color", "tipo"):
            datos[campo] = datos[campo].strip()

        datos["placa"] = datos["placa"].upper()
        datos["estado"] = datos["estado"].upper().strip()

        if any(
            not datos[campo]
            for campo in ("placa", "marca", "modelo", "color", "tipo")
        ):
            raise HTTPException(
                status_code=400,
                detail="Los campos de texto no pueden estar vacíos.",
            )

        if datos["estado"] not in ("ACTIVO", "INACTIVO"):
            raise HTTPException(
                status_code=400,
                detail="El estado debe ser ACTIVO o INACTIVO.",
            )

        return datos


def ejecutar(operacion):
    try:
        return operacion()
    except HTTPException:
        raise
    except UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="Ya existe un vehículo registrado con esa placa.",
        )
    except OperationalError:
        raise HTTPException(
            status_code=503,
            detail="El servicio de base de datos no está disponible.",
        )


@app.get("/health")
def health():
    return {"status": "ok", "servicio": "vehiculos"}


@app.post(
    "/api/v1/vehiculos",
    status_code=status.HTTP_201_CREATED,
)
def registrar_vehiculo(vehiculo: VehiculoEntrada):
    datos = vehiculo.normalizar()

    def operacion():
        with conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO vehiculos
                    (usuario_id, placa, marca, modelo, color, tipo,
                     capacidad, estado)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        datos["usuario_id"], datos["placa"],
                        datos["marca"], datos["modelo"], datos["color"],
                        datos["tipo"], datos["capacidad"], datos["estado"],
                    ),
                )
                return cur.fetchone()

    return ejecutar(operacion)


@app.get("/api/v1/vehiculos")
def listar_vehiculos():
    def operacion():
        with conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM vehiculos ORDER BY vehiculo_id"
                )
                return {"vehiculos": cur.fetchall()}

    return ejecutar(operacion)


@app.get("/api/v1/vehiculos/{vehiculo_id}")
def consultar_vehiculo(vehiculo_id: int):
    def operacion():
        with conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM vehiculos WHERE vehiculo_id = %s",
                    (vehiculo_id,),
                )
                vehiculo = cur.fetchone()

                if vehiculo is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Vehículo no encontrado.",
                    )

                return vehiculo

    return ejecutar(operacion)


@app.put("/api/v1/vehiculos/{vehiculo_id}")
def actualizar_vehiculo(
    vehiculo_id: int,
    vehiculo: VehiculoEntrada,
):
    datos = vehiculo.normalizar()

    def operacion():
        with conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE vehiculos
                    SET usuario_id = %s, placa = %s, marca = %s,
                        modelo = %s, color = %s, tipo = %s,
                        capacidad = %s, estado = %s
                    WHERE vehiculo_id = %s
                    RETURNING *
                    """,
                    (
                        datos["usuario_id"], datos["placa"],
                        datos["marca"], datos["modelo"], datos["color"],
                        datos["tipo"], datos["capacidad"], datos["estado"],
                        vehiculo_id,
                    ),
                )
                actualizado = cur.fetchone()

                if actualizado is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Vehículo no encontrado.",
                    )

                return actualizado

    return ejecutar(operacion)


@app.delete(
    "/api/v1/vehiculos/{vehiculo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def eliminar_vehiculo(vehiculo_id: int):
    def operacion():
        with conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM vehiculos WHERE vehiculo_id = %s",
                    (vehiculo_id,),
                )

                if cur.rowcount == 0:
                    raise HTTPException(
                        status_code=404,
                        detail="Vehículo no encontrado.",
                    )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return ejecutar(operacion)
