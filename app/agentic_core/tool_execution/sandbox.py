"""Ejecutor sandboxed de comandos reales resueltos desde `allowlist.py` (spec-015, puntos 2-3).

`execute(tool_key, action_id, params)` es el ÚNICO punto de entrada de este módulo y, por
diseño (spec-015, punto 4), de todo el backend para correr un comando real. Nunca acepta ni
lee `ToolCatalogEntry` (ni su `label`/`description`/`kind`) -- el único insumo es el trío
`(tool_key, action_id, params)`. Nunca deja escapar una excepción cruda: todo camino de salida
es un dict con exactamente el shape de `SandboxResult.as_dict()` (mismo criterio que spec-003
regla 2 para tools regulares).

## Qué garantiza este módulo con primitivas puras de Python/POSIX (verificado para el target
real de despliegue: contenedor `python:3.11-slim` sobre Debian bookworm, `Dockerfile.backend`,
sin `--privileged`, sin `cap_add`, ver `docker-compose.yml`)

1. **Nunca shell**: `subprocess.Popen(argv, shell=False, ...)` con `argv` ya resuelto por
   `allowlist.AllowlistEntry.resolve_argv` -- jamás una cadena, jamás `os.system`.
2. **`env` explícito, nunca heredado**: se construye desde `AllowlistEntry.env_allowlist`
   exclusivamente. `Popen(env=...)` con un dict explícito (incluso `{}`) REEMPLAZA por
   completo el entorno del hijo -- no hay ninguna ruta por la que `GROQ_API_KEY`,
   `AUDIT_DATABASE_URL` u otro secreto del proceso backend lleguen al subproceso.
3. **Directorio de trabajo efímero**: `tempfile.mkdtemp()` dedicado por invocación, usado como
   `cwd` del subproceso, purgado (`shutil.rmtree`) en un `finally` -- se ejecuta siempre, haya
   éxito, timeout o error.
4. **Timeout duro por wall-clock**: `Popen.communicate(timeout=...)`. Al vencer, se mata el
   GRUPO de procesos completo (`start_new_session=True` + `os.killpg(..., SIGKILL)`), no solo
   el proceso top-level -- evita huérfanos si el comando allowlisted hubiera hecho fork.
5. **Límites de CPU y memoria**: `resource.setrlimit(RLIMIT_CPU, ...)` /
   `setrlimit(RLIMIT_AS, ...)` aplicados en el propio proceso hijo vía `preexec_fn`, ejecutado
   después del `fork()` y antes del `exec()`. Esto NO requiere ningún privilegio adicional: un
   proceso siempre puede bajar (nunca subir sin privilegio) sus propios rlimits -- disponible
   en un contenedor no-privilegiado sin `CAP_SYS_RESOURCE`.

## Limitaciones REALES de aislamiento en este entorno -- documentadas explícitamente, no
ocultas (ver instrucción explícita de la task: reportar con honestidad lo que no se puede
cerrar del todo)

- **Aislamiento de red saliente: NO implementado a nivel de kernel.** Verificación hecha antes
  de diseñar esto: `docker-compose.yml` no declara `cap_add: [NET_ADMIN, SYS_ADMIN]` ni
  `privileged: true` para el servicio `backend`; sin esas capabilities, crear un network
  namespace propio (`CLONE_NEWNET`, vía `unshare --net` o `os.unshare` de Python) no está
  garantizado -- típicamente requiere `CAP_SYS_ADMIN` (o namespaces de usuario sin privilegios
  habilitados en el kernel del HOST, algo que este código no controla ni puede verificar en
  build-time). Además, `python:3.11-slim` corre Python 3.11, que no expone `os.unshare` en
  absoluto (se agregó recién en CPython 3.12). Por estas dos razones, NO se intentó ningún
  mecanismo de namespaces de red: hacerlo sin poder probarlo en el contenedor real habría sido
  asumir una capability no verificada, exactamente lo que la task pidió evitar.

  Mitigación real aplicada en su lugar (fail-closed, no fail-open): `execute()` rechaza de
  entrada (con `error_code="no_allowlist_entry"`) cualquier `AllowlistEntry` que declare
  `network_hosts` no vacío, porque este módulo no puede hoy garantizar que solo esos hosts
  sean alcanzables. El único entry poblado en `allowlist.py` tiene `network_hosts=()`, así que
  hoy esto no bloquea nada real -- pero si en el futuro una tool necesitara red saliente, ESTE
  gap debe cerrarse primero (imagen base con `gVisor`/`firejail` instalado y probado, o un
  contenedor sidecar de ejecución con sus propias reglas de red) antes de habilitar
  `network_hosts` en una entrada real. Como consecuencia de este diseño, hoy el subproceso SÍ
  puede alcanzar la red si el binario que ejecuta lo intenta y el proceso backend puede
  resolver DNS/rutas -- no hay firewall de proceso. Lo único garantizado es que el subproceso
  NUNCA recibe las credenciales del backend (punto 2 de arriba) para autenticarse en cualquier
  request de red que intentara hacer.

- **`preexec_fn` + multithreading**: la documentación oficial de `subprocess` advierte que
  `preexec_fn` no es seguro en presencia de threads en el proceso padre (riesgo de deadlock
  entre el `fork()` y el `exec()` si otro thread tiene tomado un lock que el hijo necesita,
  p. ej. el allocator de memoria). El backend es un proceso FastAPI que puede correr
  request handlers en threads del threadpool. Se aceptó este riesgo conocido (ventana muy
  acotada: el único trabajo hecho en `preexec_fn` acá son dos llamadas a `setrlimit`, sin
  I/O ni imports adicionales) porque no hay, en este entorno sin dependencias nuevas
  aprobadas, una alternativa POSIX-pura que aplique rlimits per-child antes del `exec` sin
  `preexec_fn` (`posix_spawn` de Python no expone `setrlimit` como spawn attribute). Se deja
  documentado para que quien integre la Task 10 decida si vale la pena aislar esta llamada en
  un proceso dedicado (p. ej. un worker pool separado) para reducir aún más la ventana.

- **Clasificación de `resource_limit_exceeded` es heurística, no perfecta**: se infiere a
  partir de la señal con la que terminó el proceso (`SIGKILL`/`SIGXCPU`/`SIGSEGV`/`SIGABRT`).
  Un programa que atrapa su propio fallo de allocación (p. ej. un intérprete que convierte un
  `malloc` fallido en una excepción de alto nivel y sale limpio con `exit(1)`) se reporta como
  `nonzero_exit`, no `resource_limit_exceeded`, aunque la causa raíz haya sido el límite. Este
  matiz se documenta acá y se cubre explícitamente en el test
  `test_resource_limit_exceeded_memory_is_marked_failed_structured`
  (`tests/unit/test_tool_execution_sandbox.py`), que acepta ambos códigos como resultado
  válido en vez de asumir uno solo.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Literal

from app.agentic_core.tool_execution.allowlist import AllowlistEntry, get_entry

try:
    import resource  # POSIX-only. Disponible en el target real (Linux, python:3.11-slim).
except ImportError:  # pragma: no cover - solo en hosts no-POSIX (p. ej. desarrollo en Windows)
    resource = None  # type: ignore[assignment]


ErrorCode = Literal["no_allowlist_entry", "timeout", "resource_limit_exceeded", "nonzero_exit"]

# Señales cuyo default disposition es terminar el proceso y que, en el contexto de este
# sandbox, correlacionan con haber excedido un límite de recursos que este módulo mismo
# configuró (RLIMIT_CPU -> SIGXCPU y eventualmente SIGKILL si soft==hard; RLIMIT_AS -> a
# menudo SIGSEGV/SIGABRT si el binario no maneja el fallo de allocación en userspace). SIGKILL
# también es la señal que usa `sandbox` para el timeout, pero ese caso se resuelve ANTES en
# `TimeoutExpired` (nunca llega a esta clasificación) -- si `communicate()` retorna con
# exit_code negativo SIN pasar por `TimeoutExpired`, el proceso murió por otra causa (rlimit
# propio, o un límite externo al proceso como un OOM-killer de cgroup del contenedor).
_RESOURCE_LIMIT_SIGNALS = frozenset(
    {signal.SIGKILL, signal.SIGXCPU, signal.SIGSEGV, signal.SIGABRT}
)

_STDOUT_STDERR_TRUNCATE_CHARS = 4000  # sanitizado/truncado (spec-015, punto 3)


@dataclass(frozen=True)
class SandboxResult:
    """Resultado estructurado de una ejecución -- nunca una excepción cruda (spec-003)."""

    status: Literal["executed", "failed"]
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    error_code: ErrorCode | None = None
    error_detail: str | None = None
    argv_resolved: list[str] | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error_code": self.error_code,
            "error_detail": self.error_detail,
            "argv_resolved": self.argv_resolved,
        }


def _truncate(text: str | None) -> str | None:
    if text is None:
        return None
    if len(text) <= _STDOUT_STDERR_TRUNCATE_CHARS:
        return text
    return text[:_STDOUT_STDERR_TRUNCATE_CHARS] + "...[truncado]"


def _build_env(entry: AllowlistEntry) -> dict[str, str]:
    """Nunca hereda `os.environ` del backend -- exactamente `entry.env_allowlist` (puede ser
    `{}`, lo que deja al subproceso sin NINGUNA variable de entorno).
    """
    return dict(entry.env_allowlist)


def _make_resource_limiter(entry: AllowlistEntry):
    """`preexec_fn`: corre en el proceso HIJO, después del `fork()` y antes del `exec()`, para
    bajar sus propios rlimits. No requiere privilegios (ver docstring del módulo).
    """
    if resource is None:
        return None

    cpu_seconds = entry.cpu_seconds
    memory_bytes = entry.memory_bytes

    def _limit() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))  # no core dumps del subproceso

    return _limit


def _looks_like_resource_limit_kill(exit_code: int) -> bool:
    return exit_code < 0 and -exit_code in _RESOURCE_LIMIT_SIGNALS


def _kill_process_group(proc: "subprocess.Popen[bytes]") -> None:
    """Mata el GRUPO de procesos completo (no solo el top-level) para no dejar huérfanos tras
    un timeout. Requiere que el proceso se haya lanzado con `start_new_session=True`.
    """
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        # El proceso ya terminó por su cuenta entre el timeout y este punto, o el sistema no
        # permite señalizar el grupo -- fallback al kill directo del top-level.
        try:
            proc.kill()
        except Exception:  # noqa: BLE001 - best-effort de limpieza, nunca debe propagar
            pass


def _run_in_sandbox(entry: AllowlistEntry, argv: list[str]) -> dict[str, object]:
    """Ejecuta `argv` (ya resuelto y validado) dentro de las restricciones de `entry`. Nunca
    deja escapar una excepción -- ver el `try/except` final de `execute()` como red de
    seguridad adicional, aunque cada paso de acá ya está cubierto explícitamente.
    """
    workdir = tempfile.mkdtemp(prefix="toolrun_sandbox_")
    env = _build_env(entry)
    preexec = _make_resource_limiter(entry)

    try:
        try:
            proc = subprocess.Popen(  # noqa: S603 - argv es una list[str] ya validada contra allowlist
                argv,
                shell=False,
                cwd=workdir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,  # process group propio -> permite killpg en timeout
                preexec_fn=preexec,  # noqa: PLW1509 - ver docstring del módulo (caveat documentado)
            )
        except OSError as exc:
            # Ejecutable inexistente/no permitido/etc -- nunca una excepción cruda.
            return SandboxResult(
                status="failed",
                error_code="nonzero_exit",
                error_detail=f"No se pudo lanzar el comando: {exc}",
                argv_resolved=argv,
            ).as_dict()

        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=entry.timeout_seconds)
        except subprocess.TimeoutExpired:
            _kill_process_group(proc)
            try:
                # Drena los pipes / reapea el proceso ya matado; no debe volver a timeoutear.
                proc.communicate(timeout=5)
            except Exception:  # noqa: BLE001 - best-effort de limpieza tras el kill
                pass
            return SandboxResult(
                status="failed",
                error_code="timeout",
                error_detail=(
                    f"Comando excedió el timeout de {entry.timeout_seconds}s y fue terminado "
                    "(SIGKILL a todo el grupo de procesos)."
                ),
                argv_resolved=argv,
            ).as_dict()

        exit_code = proc.returncode
        stdout = _truncate(stdout_bytes.decode("utf-8", errors="replace"))
        stderr = _truncate(stderr_bytes.decode("utf-8", errors="replace"))

        if _looks_like_resource_limit_kill(exit_code):
            return SandboxResult(
                status="failed",
                error_code="resource_limit_exceeded",
                error_detail=(
                    f"Proceso terminado por límite de recursos (CPU={entry.cpu_seconds}s, "
                    f"memoria={entry.memory_bytes} bytes); señal recibida: {-exit_code} "
                    f"({signal.Signals(-exit_code).name})."
                ),
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                argv_resolved=argv,
            ).as_dict()

        if exit_code != 0:
            return SandboxResult(
                status="failed",
                error_code="nonzero_exit",
                error_detail="El comando terminó con exit code distinto de cero.",
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                argv_resolved=argv,
            ).as_dict()

        return SandboxResult(
            status="executed",
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            argv_resolved=argv,
        ).as_dict()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def execute(tool_key: str, action_id: str, params: dict[str, object] | None = None) -> dict[str, object]:
    """Punto de entrada ÚNICO del sandbox (spec-015, punto 2).

    Nunca recibe ni lee un `ToolCatalogEntry` -- el único insumo es
    `(tool_key, action_id, params)`, ya que ninguna metadata declarativa del catálogo puede
    eximir a una tool del sandbox (spec-015, punto 4). Nunca deja escapar una excepción: todo
    camino de error vuelve como `{"status": "failed", "error_code": ..., "error_detail": ...}`
    con el set cerrado de `error_code` que define spec-015: `no_allowlist_entry | timeout |
    resource_limit_exceeded | nonzero_exit` (mismo criterio que spec-003 regla 2).
    """
    try:
        entry = get_entry(tool_key, action_id)
        if entry is None:
            return SandboxResult(
                status="failed",
                error_code="no_allowlist_entry",
                error_detail=f"No hay entrada de allowlist para ({tool_key!r}, {action_id!r}).",
            ).as_dict()

        if entry.network_hosts:
            # Fail-closed: este módulo no implementa enforcement real de red saliente (ver
            # docstring). Declarar network_hosts sin poder garantizarlo se rechaza en vez de
            # ejecutar como si la restricción existiera de verdad.
            return SandboxResult(
                status="failed",
                error_code="no_allowlist_entry",
                error_detail=(
                    f"La entrada ({tool_key!r}, {action_id!r}) declara network_hosts "
                    f"{entry.network_hosts!r} pero este sandbox no implementa bloqueo/"
                    "allowlist de red real todavía (ver limitación documentada en "
                    "sandbox.py) -- rechazado por seguridad (fail-closed)."
                ),
            ).as_dict()

        argv = entry.resolve_argv(params)
        if argv is None:
            return SandboxResult(
                status="failed",
                error_code="no_allowlist_entry",
                error_detail=(
                    f"Parámetros inválidos para ({tool_key!r}, {action_id!r}): no matchean "
                    "el schema declarado en la allowlist (o incluyen una clave no declarada)."
                ),
            ).as_dict()

        return _run_in_sandbox(entry, argv)
    except Exception as exc:  # noqa: BLE001 - red de seguridad final (spec-003 regla 2)
        # No debería alcanzarse en la práctica (cada paso de arriba ya tiene su propio manejo
        # de error específico) -- existe como última línea de defensa. Se mapea a
        # `nonzero_exit` (con `exit_code=None`) para mantenerse dentro del set cerrado de
        # `error_code` que define spec-015 en vez de inventar un quinto código.
        return SandboxResult(
            status="failed",
            error_code="nonzero_exit",
            error_detail=f"Error inesperado no capturado por el manejo específico: {exc}",
        ).as_dict()


__all__ = ["execute", "SandboxResult", "ErrorCode"]
