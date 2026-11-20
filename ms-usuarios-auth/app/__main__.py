"""python -m app: interfaz y puerto configurables, logs sin query strings."""

import uvicorn

from app.config.settings import getSettings


def main() -> None:
    settings = getSettings()
    uvicorn.run(
        "app.main:app", host=settings.SERVER_HOST, port=settings.SERVER_PORT, access_log=False
    )


if __name__ == "__main__":
    main()
