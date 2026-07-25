"""Uniform error contract for the API (spec-010, `.ai/skills/fastapi/SKILL.md` regla 5).

Todo error responde con el shape `{"detail": ..., "code": str}` y se restringe a los
códigos documentados: 200, 201, 400, 401, 403, 404, 422, 500.

Uso normal en un endpoint: seguir usando `HTTPException` directamente, tal como indica la
Quick Rule (`raise HTTPException(404, detail="Case not found")`). Los handlers globales
registrados en `app/main.py` se encargan de normalizar la forma de la respuesta:

- Si ya se pasó `detail={"detail": ..., "code": ...}` (vía `api_error`), se respeta tal cual.
- Si se pasó un `detail` string simple, se envuelve con un `code` derivado del status.
- Errores de validación de Pydantic (422) preservan la lista completa de errores original
  bajo `detail` (no se pierde información), con `code="validation_error"`.
- Cualquier excepción no controlada se normaliza a 500 sin filtrar detalles internos.
"""

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# Códigos por defecto para status HTTP sin `code` explícito.
_DEFAULT_CODE_BY_STATUS: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "unprocessable_entity",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_error",
}


def api_error_detail(status_code: int, detail: str, code: str | None = None) -> dict:
    """Construye el body `{"detail": ..., "code": ...}` para pasar a `HTTPException(detail=...)`.

    Ejemplo: `raise HTTPException(404, detail=api_error_detail(404, "Case not found", "case_not_found"))`.
    """
    return {"detail": detail, "code": code or _DEFAULT_CODE_BY_STATUS.get(status_code, "http_error")}


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Normaliza cualquier `HTTPException` al shape uniforme `{"detail", "code"}`."""
    if isinstance(exc.detail, dict) and "detail" in exc.detail and "code" in exc.detail:
        body = exc.detail
    else:
        body = api_error_detail(exc.status_code, str(exc.detail))
    return JSONResponse(status_code=exc.status_code, content=body, headers=getattr(exc, "headers", None))


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Normaliza errores 422 de Pydantic preservando el detalle original (spec-010)."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "code": "validation_error"},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Red de seguridad para excepciones no controladas: siempre 500 con shape uniforme."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "code": "internal_error"},
    )
