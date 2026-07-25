"""Shared FastAPI dependencies: auth stub and DB session re-export.

`get_current_user` es un placeholder explícito de desarrollo (ver
`.ai/skills/fastapi/SKILL.md` regla 4): siempre resuelve al mismo usuario fijo, sin leer
ni validar ningún header/token todavía. Es el punto de extensión que `security-compliance`
reemplazará por autenticación real (JWT/session) más adelante — los endpoints ya declaran
la dependencia vía `Depends(get_current_user)`, así que ese reemplazo no debería requerir
tocar los routers, solo esta función.

IMPORTANTE para `chainlit-ui`/spec-007: cuando se implemente auth real, este stub es el
lugar donde se debe derivar la identidad del usuario autenticado a partir del request (p.
ej. header `Authorization` parseado por una lib de JWT, nunca a mano dentro del endpoint),
para poder filtrar casos/hallazgos por usuario.
"""

from pydantic import BaseModel


class CurrentUser(BaseModel):
    """Identidad de usuario autenticado resuelta por la dependencia de auth."""

    id: str
    email: str
    is_authenticated: bool = True


# Usuario fijo de desarrollo. Reemplazar por resolución real de token en security-compliance.
_DEV_USER = CurrentUser(id="dev-user-0", email="dev@local.test")


def get_current_user() -> CurrentUser:
    """Stub de autenticación: devuelve siempre el mismo usuario de desarrollo.

    Placeholder explícito — no implementa JWT ni ninguna validación real todavía.
    """
    return _DEV_USER
