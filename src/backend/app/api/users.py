"""Login/register support and account management (FR-01, FR-18)."""
from fastapi import APIRouter, Depends, Response, status

from app.adapters.auth import TokenClaims
from app.container import Container
from app.schemas import (AccuracyOut, AdminCreateUserIn, FcmTokenIn, RegisterIn, RoleIn,
                         UserOut)
from app.security import admin_only, get_claims, get_container, get_current_user

router = APIRouter(tags=["users"])


@router.post("/users/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, claims: TokenClaims = Depends(get_claims),
             c: Container = Depends(get_container)):
    """Create the Users row after the app has signed up with Firebase Authentication."""
    return c.users.register(claims, body.name, body.role)


@router.get("/users/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return user


@router.put("/users/me/fcm-token", response_model=UserOut)
def set_fcm_token(body: FcmTokenIn, user: dict = Depends(get_current_user),
                  c: Container = Depends(get_container)):
    return c.users.set_fcm_token(user, body.fcm_token)


# ------------------------------------------------------------------ admin ----
@router.get("/admin/users", response_model=list[UserOut])
def list_users(_: dict = Depends(admin_only), c: Container = Depends(get_container)):
    return c.users.list_users()


@router.post("/admin/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: AdminCreateUserIn, _: dict = Depends(admin_only),
                c: Container = Depends(get_container)):
    return c.users.admin_create(body.name, body.email, body.password, body.role)


@router.patch("/admin/users/{user_id}/role", response_model=UserOut)
def change_role(user_id: str, body: RoleIn, admin: dict = Depends(admin_only),
                c: Container = Depends(get_container)):
    return c.users.change_role(admin, user_id, body.role)


@router.post("/admin/users/{user_id}/disable", response_model=UserOut)
def disable(user_id: str, admin: dict = Depends(admin_only), c: Container = Depends(get_container)):
    return c.users.set_disabled(admin, user_id, True)


@router.post("/admin/users/{user_id}/enable", response_model=UserOut)
def enable(user_id: str, admin: dict = Depends(admin_only), c: Container = Depends(get_container)):
    return c.users.set_disabled(admin, user_id, False)


@router.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(user_id: str, admin: dict = Depends(admin_only), c: Container = Depends(get_container)):
    c.users.delete(admin, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/model-accuracy", response_model=AccuracyOut)
def model_accuracy(_: dict = Depends(admin_only), c: Container = Depends(get_container)):
    """FR-18 monitoring: accuracy trend from farmer feedback."""
    return c.dashboard.model_accuracy()
