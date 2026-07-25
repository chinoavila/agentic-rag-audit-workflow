# Spec: Contrato de Error Uniforme de API (spec-010)

## Summary
Todos los endpoints FastAPI devuelven errores con la misma forma y usan los códigos HTTP
estándar (200, 201, 400, 401, 403, 404, 422, 500) — nunca un 200 con un error disfrazado en
el body.

## Acceptance Criteria

- [ ] Todo error se levanta con `HTTPException` (o su equivalente), nunca retornado como
      `200 OK` con `{"error": true}` en el body.
- [ ] El body de error sigue el shape `{"detail": str, "code": str}` en toda la API.
- [ ] Los códigos usados están restringidos al set documentado (200, 201, 400, 401, 403,
      404, 422, 500).
- [ ] Errores de validación de Pydantic (422) no se capturan y re-envuelven perdiendo el
      detalle original.
- [ ] Existe un test que recorre cada endpoint y verifica el shape de error en al menos un
      caso de falla.

## Test Cases

- `test_errors_use_http_exception_not_200_with_error_flag`
- `test_error_body_matches_uniform_shape`
- `test_only_documented_status_codes_are_used`
- `test_pydantic_validation_errors_preserve_detail`

## Implementation Notes

- Affected files: `backend-api` (routers, exception handlers en `app/main.py`).
- Dependencies: skill `fastapi` (regla 5).
- Quick Rules referenced: `fastapi` (regla 5).

---

## Referencias Cruzadas

### Quick Rules Relacionadas
- [fastapi/SKILL.md](../../skills/fastapi/SKILL.md)

### Archivo de Test
- `tests/specs/test_spec_010_contrato_error_api.py`
