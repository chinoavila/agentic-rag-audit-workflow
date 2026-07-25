# Chainlit — Quick Rules

**Versión**: 1.0
**Última actualización**: 2026-07-24

## ⚡ Quick Rules (Verificables, No Negociables)

1. **Streaming de tokens**: usar `cl.Message().stream_token(...)`, nunca esperar la
   respuesta completa antes de mostrar nada.
   - ✅ OK: `async for chunk in llm.stream(...): await msg.stream_token(chunk)`
   - ❌ BAD: `response = await llm.complete(...); await cl.Message(content=response).send()`
   - 🔍 Verificar: presencia de `stream_token` en el handler de mensajes.

2. **Visibilidad del razonamiento**: cada tool call / paso de retrieval se muestra con
   `cl.Step` (name = nombre de la tool), no se oculta como texto plano mezclado.
   - ✅ OK: `async with cl.Step(name="retrieval") as step: step.output = citas`
   - ❌ BAD: imprimir "Buscando..." como parte del mensaje del asistente
   - 🔍 Verificar: cada tool call relevante tiene su propio `cl.Step`.

3. **Aislamiento de sesión** (spec-007): el estado (caso de auditoría activo, historial) vive
   en `cl.user_session`, nunca en una variable global de módulo.
   - ✅ OK: `cl.user_session.set("case_id", case_id)`
   - ❌ BAD: `CURRENT_CASE_ID = case_id` a nivel de módulo
   - 🔍 Verificar: no hay variables globales mutables compartidas entre sesiones.

4. **Actions tipadas para acciones de auditoría**: aprobar/rechazar un hallazgo es un
   `cl.Action` explícito, no texto libre parseado.
   - ✅ OK: `cl.Action(name="approve_finding", payload={"finding_id": id})`
   - ❌ BAD: interpretar "sí, apruébalo" como texto libre para mutar estado
   - 🔍 Verificar: mutaciones de estado de auditoría pasan por `cl.Action`, no por parsing de texto.

5. **Chat profiles** para separar modos (ej. "Auditor", "Solo consulta") si aplica, definidos
   con `@cl.set_chat_profiles`.
   - 🔍 Verificar: si hay más de un modo de operación, existe un chat profile por modo.

---

## 📚 Guía completa

- `@cl.on_chat_start`: inicializa sesión, credenciales, caso de auditoría por defecto.
- `@cl.on_message`: delega en `agentic-core` (el loop del agente), nunca contiene lógica de
  negocio de auditoría directamente.
- Autenticación: `@cl.password_auth_callback` o el mecanismo de auth definido por
  `backend-api`; nunca hardcodear usuarios de prueba en producción.
