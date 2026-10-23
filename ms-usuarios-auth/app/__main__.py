"""python -m app: puerto leído de SERVER_PORT y logs sin query strings."""

import uvicorn

from app.config.settings import getSettings


def main() -> None:
    settings = getSettings()
    uvicorn.run("app.main:app", port=settings.SERVER_PORT, access_log=False)


if __name__ == "__main__":
    main()
