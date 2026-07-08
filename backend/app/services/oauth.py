"""Provider JWT verification for Sign in with Apple + Google (native token exchange).

Uses PyJWT's PyJWKClient which handles JWKS fetching, key caching (TTL ~6h),
and kid-based key selection internally.
"""

import logging

import jwt
from jwt import PyJWKClient, PyJWTError

logger = logging.getLogger(__name__)

JWKS_TTL = 6 * 3600  # seconds

# Per-provider JWKS clients (lazy-initialised, cached at module level)
_clients: dict[str, PyJWKClient] = {}


def _client(jwks_url: str) -> PyJWKClient:
    if jwks_url not in _clients:
        _clients[jwks_url] = PyJWKClient(jwks_url, cache_keys=True, lifespan=JWKS_TTL)
    return _clients[jwks_url]


def _verify_token(
    id_token: str,
    jwks_url: str,
    audience: str,
    valid_issuers: set[str],
) -> dict:
    """Verify an RS256 provider JWT and return decoded claims, or raise ValueError."""
    # Log unverified claims for diagnostics (never shown to client)
    try:
        unverified = jwt.decode(id_token, options={"verify_signature": False})
        logger.warning(
            "oauth: token claims (unverified) aud=%r iss=%r | configured audience=%r",
            unverified.get("aud"), unverified.get("iss"), audience,
        )
    except Exception as peek_exc:
        logger.warning("oauth: could not peek token claims: %s", peek_exc)

    client = _client(jwks_url)
    try:
        signing_key = client.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            options={"verify_iss": False},  # checked manually below
        )
    except PyJWTError as exc:
        logger.warning("oauth: PyJWTError — %s: %s", type(exc).__name__, exc)
        raise ValueError(str(exc)) from exc
    except Exception as exc:
        logger.warning("oauth: verification error — %s: %s", type(exc).__name__, exc)
        raise ValueError(f"Token verification error: {exc}") from exc

    if claims.get("iss") not in valid_issuers:
        logger.warning("oauth: invalid issuer %r (expected one of %r)", claims.get("iss"), valid_issuers)
        raise ValueError(f"Invalid issuer: {claims.get('iss')!r}")

    logger.info("oauth: verified %s token for sub=%s", jwks_url.split("/")[2], claims.get("sub"))
    return claims


def verify_google(id_token: str, client_id: str) -> dict:
    return _verify_token(
        id_token,
        "https://www.googleapis.com/oauth2/v3/certs",
        client_id,
        {"https://accounts.google.com", "accounts.google.com"},
    )


def verify_apple(id_token: str, bundle_id: str) -> dict:
    return _verify_token(
        id_token,
        "https://appleid.apple.com/auth/keys",
        bundle_id,
        {"https://appleid.apple.com"},
    )
