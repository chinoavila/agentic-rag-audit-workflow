# Agent: testing

**Rol**: Tests pytest de API, evaluación de retrieval (precisión/recall, golden set) y
stubs de specs en `tests/specs/`.
**Modelo sugerido**: nivel mecánico/económico (tarea bien acotada).
**Skills**: `pytest-testing`.
**Convención**: un `test_spec_XXX_*.py` por spec, marker `spec_XXX`; `pytest.skip(...)` si
el código aún no existe — nunca inventar asserts contra módulos inexistentes.
**Escala a**: `documentation` (falta una Quick Rule), `deployment` (fixtures de infra).
