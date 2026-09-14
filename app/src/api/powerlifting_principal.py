import os
import time

import jwt


def principal_token(person: str, athlete: str, operation: str, issuer: str = 'if-native', **extra: object) -> str:
    secret = os.getenv('PL_PRINCIPAL_SECRET', '')
    if len(secret) < 32:
        raise RuntimeError('Powerlifting principal signing is not configured')
    now = int(time.time())
    return jwt.encode({'sub': person, 'athlete': athlete, 'operation': operation, 'iss': issuer, 'aud': 'powerlifting-services', 'iat': now, 'exp': now + 300, **extra}, secret, algorithm='HS256')


def verify_principal(token: str, operation: str | None = None, person: str = '', athlete: str = '') -> dict:
    secret = os.getenv('PL_PRINCIPAL_SECRET', '')
    if len(secret) < 32:
        raise ValueError('Powerlifting principal verification is not configured')
    try:
        claims = jwt.decode(token, secret, algorithms=['HS256'], audience='powerlifting-services', issuer=['powerlifting-gateway', 'if-native'], options={'require': ['sub', 'iss', 'aud', 'iat', 'exp', 'athlete', 'operation']})
    except jwt.InvalidTokenError as exc:
        raise ValueError('Invalid Powerlifting principal') from exc
    if operation and claims.get('operation') != operation:
        raise ValueError('Principal operation mismatch')
    if not isinstance(claims.get('sub'), str) or not isinstance(claims.get('athlete'), str):
        raise ValueError('Principal scope is invalid')
    if (person and person != claims['sub']) or (athlete and athlete != claims['athlete']):
        raise ValueError('Principal scope mismatch')
    if claims['exp'] - claims['iat'] > 300:
        raise ValueError('Principal lifetime exceeds five minutes')
    return claims
