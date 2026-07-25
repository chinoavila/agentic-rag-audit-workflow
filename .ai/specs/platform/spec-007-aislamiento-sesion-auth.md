# Spec: Aislamiento de Sesión y Auth en Chainlit (spec-007)

## Summary
Cada usuario autenticado en el chat solo puede ver/modificar sus propios casos de
auditoría. El estado de sesión de Chainlit y la autorización del backend deben estar
correlacionados de forma consistente.

## Acceptance Criteria

- [ ] El estado de conversación/caso activo vive en `cl.user_session`, nunca en una
      variable global de módulo compartida entre usuarios.
- [ ] Toda llamada del backend disparada desde el chat incluye la identidad del usuario
      autenticado (vía `Depends(get_current_user)` del lado de `backend-api`).
- [ ] Un usuario no puede leer ni modificar un caso de auditoría que no le pertenece (ni por
      API directa ni por acción del chat), verificado con un test cross-user.
- [ ] Reiniciar el proceso de Chainlit no filtra estado de una sesión de usuario a otra.

## Test Cases

- `test_user_session_state_isolated_between_sessions`
- `test_chat_action_includes_authenticated_user_identity`
- `test_user_cannot_access_other_users_audit_case`
- `test_no_global_mutable_state_shared_across_sessions`

## Implementation Notes

- Affected files: `chainlit-ui` (manejo de sesión), `backend-api` (auth/autorización por
  recurso).
- Dependencies: skill `chainlit` (regla 3), skill `fastapi` (regla 4).
- Quick Rules referenced: `chainlit` (regla 3), `fastapi` (regla 4).

---

## Referencias Cruzadas

### Quick Rules Relacionadas
- [chainlit/SKILL.md](../../skills/chainlit/SKILL.md)
- [fastapi/SKILL.md](../../skills/fastapi/SKILL.md)

### Archivo de Test
- `tests/specs/test_spec_007_aislamiento_sesion_auth.py`
