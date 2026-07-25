# Docker Deployment — Quick Rules

**Versión**: 1.0
**Última actualización**: 2026-07-24

## ⚡ Quick Rules (Verificables, No Negociables)

1. **Volúmenes nombrados para todo estado persistente**: índice Chroma/FAISS y DB del audit
   trail, nunca en la capa de escritura efímera del contenedor.
   - ✅ OK: `volumes: chroma_data:/data/chroma`
   - ❌ BAD: datos escritos solo dentro del filesystem del contenedor sin volumen
   - 🔍 Verificar: `docker-compose.yml` declara volúmenes nombrados para estos paths.

2. **`.env.example` versionado, `.env` real ignorado por git**: nunca secrets/API keys
   hardcodeados en `docker-compose.yml`.
   - 🔍 Verificar: existe `.env.example` con las mismas claves que usa `.env` (sin valores reales).

3. **Servicios separados por responsabilidad**: al menos `backend` (FastAPI) y `chainlit`
   como servicios distintos (aunque compartan imagen base), no un único proceso monolítico
   sin aislamiento.
   - 🔍 Verificar: `docker-compose.yml` define servicios independientes con sus propios
     healthchecks.

4. **`docker compose down -v` nunca en scripts automatizados**: solo manual y confirmado
   (borra el índice RAG y el audit trail). El guardrail ya lo bloquea a nivel de hook.
   - 🔍 Verificar: ningún script del repo llama `docker compose down -v` sin confirmación humana.

5. **Reproducibilidad**: `docker compose up` desde un checkout limpio (con `.env` provisto)
   levanta el stack completo sin pasos manuales adicionales no documentados.
   - 🔍 Verificar: el README de deployment no requiere pasos manuales fuera de `docker compose up`.

---

## 📚 Guía completa

- Ver spec-009 (entorno Docker reproducible) para el criterio de aceptación completo.
- Este es un prototipo de despliegue **manual y local** — no hay pipeline de CI/CD.
