"""Comprueba los arranques Python con archivos sintéticos, sin SQL ni red."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import importlib.util
import os

from dotenv import dotenv_values

repo = Path(__file__).resolve().parents[1]
publicadas = dotenv_values(repo / "config" / "claves-practica.env")
servicios = ("ms-usuarios-auth", "ms-vehiculos", "ms-viajes", "ms-reservas-estadisticas")
for servicio in servicios:
    values = dotenv_values(repo / servicio / ".env.practica")
    assert values["JWT_SECRET"] == publicadas["JWT_SECRET"]
    expected = {"JWT_SECRET"}
    if servicio in ("ms-viajes", "ms-reservas-estadisticas"):
        expected.add("SERVICE_API_KEY")
        assert values["SERVICE_API_KEY"] == publicadas["SERVICE_API_KEY"]
    assert set(values) == expected, "El archivo de práctica solo contiene sus claves compartidas."

old = "clave-antigua-ficticia-de-pruebas-1234567890"
new = "clave-publica-ficticia-de-pruebas-1234567890"
key = "llave-publica-ficticia-de-pruebas-1234567890"
db = {"DB_HOST": "sql-ficticio.invalid", "DB_PORT": "1433", "DB_NAME": "base_ficticia",
      "DB_USER": "usuario_ficticio", "DB_PASSWORD": "conservar-password-ficticio",
      "DB_DRIVER": "ODBC Driver 18 for SQL Server", "SERVER_PORT": "8084"}

for servicio in ("ms-usuarios-auth", "ms-vehiculos", "ms-reservas-estadisticas"):
    with TemporaryDirectory(prefix="uniride-env-") as temporary, patch.dict(os.environ):
        for name in [*db, "JWT_SECRET", "SERVICE_API_KEY", "UNIRIDE_PRACTICA_AUTO"]:
            os.environ.pop(name, None)
        directory = Path(temporary)
        config = directory / "app" / "config" / "settings.py"
        config.parent.mkdir(parents=True)
        config.write_text((repo / servicio / "app/config/settings.py").read_text(encoding="utf-8"), encoding="utf-8")
        (directory / ".env").write_text("".join(f"{k}={v}\n" for k,v in db.items()) +
                                       f"JWT_SECRET={old}\nSERVICE_API_KEY={old}\n", encoding="utf-8")
        (directory / ".env.practica").write_text(f"JWT_SECRET={new}\nSERVICE_API_KEY={key}\n", encoding="utf-8")

        def cargar(suffix):
            spec = importlib.util.spec_from_file_location("settings_" + suffix, config)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

        def secreto(module):
            if servicio == "ms-reservas-estadisticas":
                return module.JwtSettings().jwtSecret.get_secret_value()
            return module.Settings().JWT_SECRET.get_secret_value()

        module = cargar("practica")
        assert secreto(module) == new, "Un .env antiguo no debe cambiar el JWT común."
        settings = module.Settings()
        password = settings.dbPassword if servicio == "ms-reservas-estadisticas" else settings.DB_PASSWORD
        assert password.get_secret_value() == db["DB_PASSWORD"]
        if servicio == "ms-reservas-estadisticas":
            assert module.ServiceAuthSettings().serviceApiKey.get_secret_value() == key
        os.environ["UNIRIDE_PRACTICA_AUTO"] = "0"
        assert secreto(cargar("privado")) == old, "Se conserva la opción privada explícita."
        os.environ.pop("UNIRIDE_PRACTICA_AUTO")
        os.environ["JWT_SECRET"] = old
        assert secreto(cargar("proceso")) == old, "Las variables explícitas del proceso conservan prioridad."

print("OK: cuatro .env.practica consistentes; tres cargadores Python verificados sin scripts, SQL ni red.")
