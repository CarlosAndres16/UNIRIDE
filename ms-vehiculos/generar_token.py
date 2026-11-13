import sys
import time

import jwt

from app.config.settings import getSettings

conductorId = sys.argv[1] if len(sys.argv) > 1 else "1"
ahora = int(time.time())
secreto = getSettings().JWT_SECRET.get_secret_value()
print(jwt.encode({"sub": conductorId, "iat": ahora, "exp": ahora + 3600}, secreto, algorithm="HS256"))