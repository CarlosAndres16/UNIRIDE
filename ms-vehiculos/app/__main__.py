import uvicorn

from app.config.settings import getSettings

if __name__ == "__main__":
    settings = getSettings()  # falla al arrancar si falta una variable
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.SERVER_PORT)
