"""Request authentication and role checks (AuthController.checkRole; NFR-11).

Every API request must carry "Authorization: Bearer <Firebase ID token>".
Missing or invalid tokens get 401; disabled accounts, unregistered accounts and
wrong roles get 403.
"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.adapters.auth import AccountDisabledError, InvalidTokenError, TokenClaims
from app.container import Container
from app.schemas import Role

_bearer = HTTPBearer(auto_error=False)


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_claims(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    c: Container = Depends(get_container),
) -> TokenClaims:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        return c.verifier.verify(creds.credentials)
    except InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"}) from None
    except AccountDisabledError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled") from None


def get_current_user(
    claims: TokenClaims = Depends(get_claims), c: Container = Depends(get_container),
) -> dict:
    user = c.users.by_firebase_uid(claims.uid)
    if user is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account not registered; call POST /api/v1/users/register")
    return user


def require_roles(*roles: Role):
    allowed = {r.value for r in roles}

    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot use this feature")
        return user

    return checker


admin_only = require_roles(Role.admin)
grower = require_roles(Role.farmer, Role.farm_owner, Role.admin)
agronomist_only = require_roles(Role.agronomist, Role.admin)
