"""Hash Argon2id con salt generado por argon2-cffi."""

from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type


@lru_cache(maxsize=1)
def _passwordHasher() -> PasswordHasher:
    return PasswordHasher(
        time_cost=3,
        memory_cost=65_536,
        parallelism=4,
        hash_len=32,
        salt_len=16,
        type=Type.ID,
    )


@lru_cache(maxsize=1)
def _dummyPasswordHash() -> str:
    # Se calcula una vez por proceso. No representa una cuenta ni una credencial.
    return _passwordHasher().hash("UniRide-dummy-verification-only")


class PasswordService:
    def __init__(self) -> None:
        self._hasher = _passwordHasher()
        self._dummyHash = _dummyPasswordHash()

    def hashPassword(self, password: str) -> str:
        return self._hasher.hash(password)

    def verifyPassword(self, password: str, passwordHash: str) -> bool:
        try:
            return self._hasher.verify(passwordHash, password)
        except (VerificationError, InvalidHashError):
            return False

    def verifyDummyPassword(self, password: str) -> None:
        """Realiza el trabajo de verificación también cuando el correo no existe."""
        self.verifyPassword(password, self._dummyHash)
