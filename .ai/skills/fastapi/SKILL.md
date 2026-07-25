# FastAPI — Quick Rules

**Versión**: 1.0
**Última actualización**: 2026-07-24

## ⚡ Quick Rules (Verificables, No Negociables)

1. **Prefijo de recurso**: endpoints bajo `/api/{resource}`.
   - ✅ OK: `POST /api/audit-cases`
   - ❌ BAD: `POST /createCase`
   - 🔍 Verificar: el router registra el prefijo `/api/...`.

2. **Paginación obligatoria en listados**: `?skip=0&limit=100`.
   - ✅ OK: `def list_cases(skip: int = 0, limit: int = 100)`
   - ❌ BAD: `def list_cases()` que retorna todo sin límite
   - 🔍 Verificar: la firma del endpoint GET-list tiene `skip`/`limit`.

3. **Schemas Pydantic para request/response**: nunca dicts sueltos.
   - ✅ OK: `def create_case(payload: AuditCaseCreate) -> AuditCaseOut`
   - ❌ BAD: `def create_case(payload: dict)`
   - 🔍 Verificar: el endpoint tipa `payload` y el return con clases Pydantic.

4. **Auth vía `Depends`**: nunca leer el token manualmente en el body del endpoint.
   - ✅ OK: `def get_case(user: User = Depends(get_current_user))`
   - ❌ BAD: parsear el header `Authorization` a mano dentro del endpoint
   - 🔍 Verificar: presencia de `Depends(get_current_user)` en endpoints protegidos.

5. **Contrato de error uniforme** (spec-010): códigos 200, 201, 400, 401, 403, 404, 422, 500
   con body `{"detail": str, "code": str}`.
   - ✅ OK: `raise HTTPException(404, detail="Case not found")`
   - ❌ BAD: retornar 200 con `{"error": true}` en el body
   - 🔍 Verificar: errores usan `HTTPException`, no status 200 disfrazado.

6. **Nunca `DELETE` físico sobre hallazgos/audit trail** (spec-004).
   - ✅ OK: `PATCH /api/findings/{uuid}` con `{"superseded_by": <id>}`
   - ❌ BAD: `db.delete(finding)`
   - 🔍 Verificar: no existe ningún `db.delete(...)` sobre modelos de auditoría.

---

## 📚 Guía completa

- Routers organizados por recurso en `app/routers/{resource}.py`, incluidos en `app/main.py`.
- Sesión de DB inyectada vía `Depends(get_db)`; nunca abrir sesión manual dentro del endpoint.
- Todo endpoint que devuelve datos de un caso de auditoría debe filtrar por el usuario/rol
  autenticado (ver `security-compliance` y spec-007).
