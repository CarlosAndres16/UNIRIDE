"""Registro e inicio de sesión sin conocimiento de HTTP ni de SQL directo."""

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.exceptions.exceptions import AppException
from app.repositories.conductor_repository import ConductorRepository, esCorreoDuplicado
from app.schemas.auth_schema import LoginRequest, LoginResponse, RegistrarConductorRequest
from app.schemas.conductor_schema import ConductorResponse
from app.security.jwt_service import JWTService
from app.security.password_service import PasswordService


class AuthService:
    def __init__(
        self,
        repository: ConductorRepository,
        passwordService: PasswordService,
        jwtService: JWTService,
    ) -> None:
        self.repository = repository
        self.passwordService = passwordService
        self.jwtService = jwtService

    @staticmethod
    def _correoYaRegistrado() -> AppException:
        return AppException(
            status=409,
            error="CORREO_YA_REGISTRADO",
            message="El correo ya está registrado.",
        )

    @staticmethod
    def _credencialesInvalidas() -> AppException:
        return AppException(
            status=401,
            error="CREDENCIALES_INVALIDAS",
            message="El correo o la contraseña son incorrectos.",
        )

    def registrar(self, request: RegistrarConductorRequest) -> ConductorResponse:
        correo = str(request.correo).lower()
        if self.repository.buscarPorCorreo(correo) is not None:
            raise self._correoYaRegistrado()
        passwordHash = self.passwordService.hashPassword(request.password.get_secret_value())
        try:
            conductor = self.repository.crear(
                nombre=request.nombre,
                correo=correo,
                passwordHash=passwordHash,
                telefono=request.telefono,
            )
        except IntegrityError as error:
            # El repositorio ya revierte la transacción. La restricción UNIQUE
            # conserva la garantía aunque dos solicitudes superen el precheck.
            if esCorreoDuplicado(error):
                raise self._correoYaRegistrado() from None
            try:
                existeCorreo = self.repository.buscarPorCorreo(correo) is not None
            except SQLAlchemyError:
                raise error
            if existeCorreo:
                raise self._correoYaRegistrado() from None
            raise
        return ConductorResponse.fromConductor(conductor)

    def login(self, request: LoginRequest) -> LoginResponse:
        conductor = self.repository.buscarPorCorreo(str(request.correo).lower())
        password = request.password.get_secret_value()
        if conductor is None:
            self.passwordService.verifyDummyPassword(password)
            raise self._credencialesInvalidas()
        if not self.passwordService.verifyPassword(password, conductor.password_hash):
            raise self._credencialesInvalidas()
        # El contrato no define bloquear el login por activo=False.
        return LoginResponse(
            accessToken=self.jwtService.generarToken(conductor.id),
            tokenType="Bearer",
            expiresIn=self.jwtService.expiresIn,
            conductorId=conductor.id,
        )
