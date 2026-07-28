# Spec: Entorno Docker Reproducible (spec-009)

## Summary
El stack (backend FastAPI + Chainlit + vector store Chroma/FAISS) debe poder levantarse
desde un checkout limpio con `docker compose up` y un `.env` provisto, sin pasos manuales
adicionales, y sin perder datos entre reinicios.

## Acceptance Criteria

- [ ] `docker compose up` desde un checkout limpio levanta backend + chainlit + persistencia
      sin pasos manuales fuera de proveer `.env`.
- [ ] El índice Chroma/FAISS y la DB del audit trail persisten en un mecanismo de host que
      sobrevive a `docker compose down` (sin `-v`): la DB del audit trail vía volumen nombrado
      (`sqlite_data`); el índice Chroma vía bind mount a `./data/chroma` (no un volumen nombrado
      — decisión deliberada, ver `docs/plans/plan-tool-execution-permission-modes.md` sección 1:
      el borrado del índice debe ser siempre una acción explícita del usuario sobre esa carpeta,
      nunca un efecto secundario de un comando Docker sobre volúmenes).
- [ ] `docker compose down -v` está documentado como destructivo y bloqueado por guardrail
      salvo confirmación explícita del usuario.
- [ ] `.env.example` existe y contiene las mismas claves que `.env` (sin valores reales).
- [ ] Cada servicio define un healthcheck básico.

## Test Cases

- `test_docker_compose_config_defines_named_volumes_for_persistence`
- `test_env_example_keys_match_required_env_keys`
- `test_services_define_healthchecks`

## Implementation Notes

- Affected files: `docker-compose.yml`, `Dockerfile.backend`, `Dockerfile.chainlit`,
  `.env.example`.
- Dependencies: skill `docker-deployment`, guardrail `docker compose down -v` en
  `.ai/guardrails/restricted-ops.json`.
- Quick Rules referenced: `docker-deployment` (todas).

---

## Referencias Cruzadas

### Quick Rules Relacionadas
- [docker-deployment/SKILL.md](../../skills/docker-deployment/SKILL.md)

### Archivo de Test
- `tests/specs/test_spec_009_entorno_docker_reproducible.py`
