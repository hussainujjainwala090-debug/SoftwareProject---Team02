"""Firebase Authentication adapters.

The app signs in with Firebase Authentication and sends the ID token with every
request. The backend verifies it here (firebase mode) or accepts development
tokens of the form ``dev:<uid>:<email>`` (memory mode and tests only).
Passwords are never seen or stored by the backend's data layer.
"""
from dataclasses import dataclass
from typing import Protocol


class InvalidTokenError(Exception):
    pass


class AccountDisabledError(Exception):
    pass


@dataclass(frozen=True)
class TokenClaims:
    uid: str
    email: str | None


class TokenVerifier(Protocol):
    def verify(self, token: str) -> TokenClaims: ...


class AccountAdmin(Protocol):
    """Account actions the admin can take (FR-18)."""

    def create(self, email: str, password: str, name: str) -> str: ...

    def set_disabled(self, uid: str, disabled: bool) -> None: ...

    def is_disabled(self, uid: str) -> bool: ...

    def delete(self, uid: str) -> None: ...


# ---------------------------------------------------------------- fakes ----
class FakeAccountAdmin:
    def __init__(self) -> None:
        self.accounts: dict[str, dict] = {}

    def create(self, email: str, password: str, name: str) -> str:
        uid = f"dev-{len(self.accounts) + 1}-{email.split('@')[0]}"
        self.accounts[uid] = {"email": email, "name": name, "disabled": False}
        return uid

    def set_disabled(self, uid: str, disabled: bool) -> None:
        self.accounts.setdefault(uid, {"disabled": False})["disabled"] = disabled

    def is_disabled(self, uid: str) -> bool:
        return self.accounts.get(uid, {}).get("disabled", False)

    def delete(self, uid: str) -> None:
        self.accounts.pop(uid, None)


class DevTokenVerifier:
    """Accepts ``dev:<uid>:<email>``. Never used in firebase mode."""

    def __init__(self, accounts: FakeAccountAdmin) -> None:
        self._accounts = accounts

    def verify(self, token: str) -> TokenClaims:
        parts = token.split(":", 2)
        if len(parts) != 3 or parts[0] != "dev" or not parts[1]:
            raise InvalidTokenError("Invalid development token")
        uid, email = parts[1], parts[2] or None
        if self._accounts.is_disabled(uid):
            raise AccountDisabledError(uid)
        return TokenClaims(uid=uid, email=email)


# ------------------------------------------------------------- firebase ----
class FirebaseTokenVerifier:
    def __init__(self, firebase_app) -> None:
        self._app = firebase_app

    def verify(self, token: str) -> TokenClaims:
        from firebase_admin import auth

        try:
            decoded = auth.verify_id_token(token, app=self._app, check_revoked=True)
        except auth.UserDisabledError as exc:
            raise AccountDisabledError(str(exc)) from exc
        except (ValueError, auth.InvalidIdTokenError, auth.ExpiredIdTokenError,
                auth.RevokedIdTokenError, auth.CertificateFetchError) as exc:
            raise InvalidTokenError(str(exc)) from exc
        return TokenClaims(uid=decoded["uid"], email=decoded.get("email"))


class FirebaseAccountAdmin:
    def __init__(self, firebase_app) -> None:
        self._app = firebase_app

    def create(self, email: str, password: str, name: str) -> str:
        from firebase_admin import auth

        return auth.create_user(email=email, password=password, display_name=name, app=self._app).uid

    def set_disabled(self, uid: str, disabled: bool) -> None:
        from firebase_admin import auth

        auth.update_user(uid, disabled=disabled, app=self._app)
        if disabled:
            auth.revoke_refresh_tokens(uid, app=self._app)

    def is_disabled(self, uid: str) -> bool:
        from firebase_admin import auth

        try:
            return auth.get_user(uid, app=self._app).disabled
        except auth.UserNotFoundError:
            return True

    def delete(self, uid: str) -> None:
        from firebase_admin import auth

        try:
            auth.delete_user(uid, app=self._app)
        except auth.UserNotFoundError:
            pass
