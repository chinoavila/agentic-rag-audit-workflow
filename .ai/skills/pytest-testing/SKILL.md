# Pytest Testing — Quick Rules

**Versión**: 1.0
**Última actualización**: 2026-07-24

## ⚡ Quick Rules (Verificables, No Negociables)

1. **Un test file por spec**: `tests/specs/test_spec_XXX_<slug>.py`, marcado
   `@pytest.mark.spec_XXX` (marker registrado en `pytest.ini`).
   - 🔍 Verificar: el nombre del archivo y el marker coinciden con el id de la spec.

2. **Stub explícito si el código no existe aún**: `pytest.skip("pending implementation: <spec>")`
   en vez de un test que falla por `ImportError` o un assert inventado.
   - ✅ OK: `def test_x(): pytest.skip("pending implementation: spec-003")`
   - ❌ BAD: `def test_x(): assert True  # TODO`
   - 🔍 Verificar: los stubs usan `pytest.skip` con el id de la spec, no un `assert True`.

3. **DB de test aislada**: `sqlite:///:memory:` o un contenedor de test dedicado, nunca
   contra el volumen de datos real/desarrollo.
   - 🔍 Verificar: la fixture de DB de test no apunta a la ruta de persistencia real.

4. **Eval de retrieval con golden set**: un pequeño set de pares (query, chunk esperado)
   versionado en el repo, usado para medir precisión/recall del retrieval antes de cambiar
   `top_k`/umbral/modelo de embeddings.
   - 🔍 Verificar: existe un golden set y un test que lo recorre.

5. **Nombre de test describe el Acceptance Criterion**, no la implementación interna.
   - ✅ OK: `test_finding_without_evidence_is_rejected`
   - ❌ BAD: `test_function_1`
   - 🔍 Verificar: el nombre del test es legible como una afirmación de negocio.

---

## 📚 Guía completa

- `pytest.ini` registra un marker `spec_XXX` por cada spec en `.ai/specs/**`.
- Correr solo los tests de una spec: `pytest -m spec_004`.
