"""Auth and role service (FR-01, FR-18, NFR-11).

Users(user_id, name, email, firebase_uid, fcm_token, role). email and
firebase_uid are UNIQUE; Firestore cannot enforce that, so it is checked here.
"""
from app.adapters.auth import AccountAdmin, TokenClaims
from app.errors import Conflict, Forbidden, Invalid, NotFound
from app.repository import USERS, Repository, new_id
from app.schemas import Role

SELF_REGISTER_ROLES = {Role.farmer, Role.farm_owner, Role.agronomist}


class UserService:
    def __init__(self, repo: Repository, accounts: AccountAdmin,
                 admin_emails: list[str] | None = None) -> None:
        self.repo = repo
        self.accounts = accounts
        self.admin_emails = {e.lower() for e in admin_emails or []}

    # ------------------------------------------------------------ lookup ----
    def by_firebase_uid(self, uid: str) -> dict | None:
        found = self.repo.find(USERS, firebase_uid=uid)
        return found[0] if found else None

    def get(self, user_id: str) -> dict:
        user = self.repo.get(USERS, user_id)
        if user is None:
            raise NotFound("User not found")
        return user

    def _check_unique(self, firebase_uid: str, email: str) -> None:
        if self.repo.find(USERS, firebase_uid=firebase_uid):
            raise Conflict("This account is already registered")
        if self.repo.find(USERS, email=email.lower()):
            raise Conflict("A user with this email already exists")

    def _insert(self, firebase_uid: str, email: str, name: str, role: Role) -> dict:
        self._check_unique(firebase_uid, email)
        user = {
            "user_id": new_id(),
            "name": name,
            "email": email.lower(),
            "firebase_uid": firebase_uid,
            "fcm_token": None,
            "role": role.value,
        }
        return self.repo.create(USERS, user["user_id"], user)

    # ---------------------------------------------------------- self-serve ----
    def register(self, claims: TokenClaims, name: str, role: Role) -> dict:
        if not claims.email:
            raise Invalid("The sign-in account has no email address")
        if claims.email.lower() in self.admin_emails:
            # Configured first admin (AGRISCAN_ADMIN_EMAILS). The address must be
            # verified, or anyone could sign up with it and become admin.
            if not claims.email_verified:
                raise Forbidden("Verify this email address before registering as admin")
            role = Role.admin
        elif role not in SELF_REGISTER_ROLES:
            raise Forbidden("Admin accounts can only be created by an admin")
        return self._insert(claims.uid, claims.email, name, role)

    def set_fcm_token(self, user: dict, token: str) -> dict:
        return self.repo.update(USERS, user["user_id"], {"fcm_token": token})

    # -------------------------------------------------------------- admin ----
    def with_status(self, user: dict) -> dict:
        return {**user, "disabled": self.accounts.is_disabled(user["firebase_uid"])}

    def list_users(self) -> list[dict]:
        users = sorted(self.repo.find(USERS), key=lambda u: u["name"].lower())
        return [self.with_status(u) for u in users]

    def admin_create(self, name: str, email: str, password: str, role: Role) -> dict:
        if self.repo.find(USERS, email=email.lower()):
            raise Conflict("A user with this email already exists")
        uid = self.accounts.create(email, password, name)
        return self.with_status(self._insert(uid, email, name, role))

    def change_role(self, admin: dict, user_id: str, role: Role) -> dict:
        user = self.get(user_id)
        if user["user_id"] == admin["user_id"] and role != Role.admin:
            raise Invalid("Admins cannot remove their own admin role")
        return self.with_status(self.repo.update(USERS, user_id, {"role": role.value}))

    def set_disabled(self, admin: dict, user_id: str, disabled: bool) -> dict:
        user = self.get(user_id)
        if user["user_id"] == admin["user_id"]:
            raise Invalid("Admins cannot disable their own account")
        self.accounts.set_disabled(user["firebase_uid"], disabled)
        return self.with_status(user)

    def delete(self, admin: dict, user_id: str) -> None:
        """Remove the sign-in account and the Users row.

        Scans and diagnoses are kept as history (they are never deleted), so
        their user_id may point to a removed account.
        """
        user = self.get(user_id)
        if user["user_id"] == admin["user_id"]:
            raise Invalid("Admins cannot remove their own account")
        self.accounts.delete(user["firebase_uid"])
        self.repo.delete(USERS, user_id)
