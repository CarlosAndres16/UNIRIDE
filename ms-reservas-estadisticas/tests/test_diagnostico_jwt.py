import time
import jwt
import pytest
from pydantic import SecretStr

from app.security import jwt_service
from app.exceptions.exceptions import NoAutenticadoError


@pytest.mark.parametrize('caso,motivo', [
    ('firma','FIRMA_INVALIDA'), ('vencido','TOKEN_VENCIDO'),
    ('futuro','TOKEN_ADELANTADO_REVISAR_RELOJ'), ('faltante','CLAIMS_INCOMPLETOS'),
    ('algoritmo','ALGORITMO_NO_PERMITIDO'), ('formato','TOKEN_MALFORMADO'),
    ('claims','CLAIMS_INVALIDOS'),
])
def test_diagnostico_sin_exponer_token_o_clave(monkeypatch, caso, motivo):
    secret = 'clave-ficticia-de-prueba-diagnostico-1234567890' * 2
    now = int(time.time())
    claims = {'sub':'1','iat':now,'exp':now+300}
    signing = secret
    algorithm = 'HS256'
    if caso == 'firma': signing = 'otra-clave-ficticia-de-prueba-1234567890'
    if caso == 'vencido': claims.update(iat=now-600, exp=now-300)
    if caso == 'futuro': claims.update(iat=now+300, exp=now+600)
    if caso == 'faltante': claims.pop('exp')
    if caso == 'algoritmo': algorithm = 'HS384'
    if caso == 'claims': claims['sub'] = 'abc'
    token = jwt.encode(claims, signing, algorithm=algorithm) if caso != 'formato' else 'token-invalido-de-prueba'
    messages = []
    monkeypatch.setattr(jwt_service.logger, 'warning', lambda message,*args: messages.append(message % args if args else message))
    with pytest.raises(NoAutenticadoError):
        jwt_service.JwtService(SecretStr(secret)).validarToken(token)
    assert messages == ['JWT rechazado motivo=' + motivo]
    assert secret not in messages[0] and token not in messages[0]
