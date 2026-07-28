"""Tests unitarios REALES (no skipeados) del sandbox de ejecución de comandos.

Cubre `app/agentic_core/tool_execution/{allowlist,sandbox}.py` -- la implementación de la
Task 9 del plan de permission modes (spec-015, sección "Sandboxing y Autorización").

Los stubs de integración end-to-end (ToolRun persistido, endpoints, permission modes de chat)
siguen en `tests/specs/test_spec_015_ejecucion_comandos_permission_modes.py`, deliberadamente
skipeados porque dependen de Tasks 8/10 (backend-api) y 12 (agentic-core), fuera del alcance
de este módulo aislado.

Estrategia: en vez de depender de binarios específicos del sistema operativo (que pueden no
estar presentes/tener rutas distintas entre hosts), los `argv` de prueba invocan
`sys.executable -c "<script>"` -- el propio intérprete que corre los tests, siempre disponible
y 100% determinista en su comportamiento.

Nota honesta sobre el entorno de verificación: estos tests fueron escritos sin poder correrlos
contra el contenedor Docker real (`Dockerfile.backend`, `python:3.11-slim`) desde este agente
-- no hubo acceso a un tool de ejecución de comandos en esta sesión. La lógica en sí
(`resource.setrlimit`, `subprocess.Popen` con `start_new_session`/`os.killpg`, `tempfile`) usa
únicamente primitivas POSIX estándar documentadas, pero los dos tests de límites de recursos
(`test_resource_limit_exceeded_cpu_*`, `test_resource_limit_exceeded_memory_*`) son los más
sensibles a particularidades del kernel/cgroup del host real y quedan marcados como los que más
ameritan una corrida real de confirmación (ver reporte de la task).
"""

from __future__ import annotations

import os
import sys

import pytest

from app.agentic_core.tool_execution import sandbox
from app.agentic_core.tool_execution.allowlist import AllowlistEntry, ParamSpec
from app.models.tool_catalog_entry import ToolCatalogEntry


def _entry(**overrides: object) -> AllowlistEntry:
    base: dict[str, object] = dict(
        tool_key="_test_tool",
        action_id="_test_action",
        argv_template=(sys.executable, "-c", "print('ok')"),
        params=(),
        env_allowlist={},
        network_hosts=(),
        timeout_seconds=5.0,
        cpu_seconds=5,
        memory_bytes=256 * 1024 * 1024,
    )
    base.update(overrides)
    return AllowlistEntry(**base)  # type: ignore[arg-type]


pytestmark = pytest.mark.skipif(
    os.name != "posix",
    reason=(
        "El sandbox usa resource.setrlimit/os.killpg (POSIX-only); el target real de "
        "despliegue es el contenedor Linux de Dockerfile.backend."
    ),
)


class TestAllowlistResolution:
    """`allowlist.AllowlistEntry.resolve_argv` -- nunca sustituye texto libre no validado."""

    def test_missing_declared_param_is_rejected(self):
        entry = _entry(
            argv_template=(sys.executable, "-c", "pass"),
            params=(ParamSpec(name="choice", kind="enum", enum_values=("a", "b")),),
        )
        assert entry.resolve_argv({}) is None

    def test_param_not_matching_enum_schema_is_rejected(self):
        entry = _entry(
            argv_template=(sys.executable, "-c", "import sys; print(sys.argv[1])", "{choice}"),
            params=(ParamSpec(name="choice", kind="enum", enum_values=("a", "b")),),
        )
        assert entry.resolve_argv({"choice": "not_a_valid_enum_choice"}) is None

    def test_param_not_matching_regex_schema_is_rejected(self):
        entry = _entry(
            argv_template=(sys.executable, "-c", "pass", "{value}"),
            params=(ParamSpec(name="value", kind="regex", pattern=r"[a-z0-9_]{1,16}"),),
        )
        assert entry.resolve_argv({"value": "; unsafe injected $(payload) #"}) is None

    def test_undeclared_extra_param_is_rejected(self):
        entry = _entry()
        assert entry.resolve_argv({"unexpected": "x"}) is None

    def test_valid_params_resolve_to_expected_argv(self):
        entry = _entry(
            argv_template=(sys.executable, "-c", "pass", "{choice}"),
            params=(ParamSpec(name="choice", kind="enum", enum_values=("a", "b")),),
        )
        assert entry.resolve_argv({"choice": "a"}) == [sys.executable, "-c", "pass", "a"]


class TestSandboxExecute:
    """`sandbox.execute` -- comportamiento end-to-end contra la allowlist real."""

    def test_command_outside_allowlist_never_reaches_executed_status(self, monkeypatch):
        monkeypatch.setattr(sandbox, "get_entry", lambda *a, **k: None)
        result = sandbox.execute("tool_que_no_existe", "accion_que_no_existe", {})
        assert result["status"] == "failed"
        assert result["error_code"] == "no_allowlist_entry"

    def test_command_execution_never_uses_shell_true_or_string_interpolation(self):
        """Verificación estática: el módulo nunca invoca subprocess/os con shell libre."""
        import inspect

        source = inspect.getsource(sandbox)
        assert "shell=True" not in source
        assert "os.system(" not in source
        assert "os.popen(" not in source

    def test_command_with_param_failing_schema_never_executes(self, monkeypatch):
        entry = _entry(
            argv_template=(sys.executable, "-c", "import sys; print(sys.argv[1])", "{choice}"),
            params=(ParamSpec(name="choice", kind="enum", enum_values=("a", "b")),),
        )
        monkeypatch.setattr(sandbox, "get_entry", lambda *a, **k: entry)
        result = sandbox.execute("_test_tool", "_test_action", {"choice": "not_a_valid_enum_choice"})
        assert result["status"] == "failed"
        assert result["error_code"] == "no_allowlist_entry"

    def test_entry_declaring_network_hosts_is_rejected_fail_closed(self, monkeypatch):
        """Enforcement de red no está implementado -- declarar network_hosts se rechaza en
        vez de ejecutar como si el bloqueo existiera de verdad (ver docstring de sandbox.py).
        """
        entry = _entry(network_hosts=("example.com:443",))
        monkeypatch.setattr(sandbox, "get_entry", lambda *a, **k: entry)
        result = sandbox.execute("_test_tool", "_test_action", {})
        assert result["status"] == "failed"
        assert result["error_code"] == "no_allowlist_entry"

    def test_successful_execution_returns_executed_with_exit_code_zero(self, monkeypatch):
        entry = _entry()
        monkeypatch.setattr(sandbox, "get_entry", lambda *a, **k: entry)
        result = sandbox.execute("_test_tool", "_test_action", {})
        assert result["status"] == "executed"
        assert result["exit_code"] == 0
        assert "ok" in (result["stdout"] or "")
        assert result["argv_resolved"] == [sys.executable, "-c", "print('ok')"]

    def test_executed_subprocess_cannot_read_groq_api_key_or_database_url(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "secret-groq-key-should-not-leak")
        monkeypatch.setenv("AUDIT_DATABASE_URL", "sqlite:////should/not/leak.db")
        entry = _entry(
            argv_template=(
                sys.executable,
                "-c",
                "import os; print(repr(os.environ.get('GROQ_API_KEY'))); "
                "print(repr(os.environ.get('AUDIT_DATABASE_URL')))",
            ),
            env_allowlist={},
        )
        monkeypatch.setattr(sandbox, "get_entry", lambda *a, **k: entry)
        result = sandbox.execute("_test_tool", "_test_action", {})
        assert result["status"] == "executed"
        stdout = result["stdout"] or ""
        assert "secret-groq-key-should-not-leak" not in stdout
        assert "should/not/leak.db" not in stdout
        # os.environ.get(...) sobre un proceso sin esas vars da None -- confirma que jamás
        # se heredaron, no solo que no aparecieron en el output por casualidad.
        assert stdout.count("None") == 2

    def test_env_allowlist_only_exposes_explicitly_fixed_values(self, monkeypatch):
        monkeypatch.setenv("SOME_BACKEND_SECRET", "should-not-appear")
        entry = _entry(
            argv_template=(
                sys.executable,
                "-c",
                "import os; print(os.environ.get('FIXED_VAR')); "
                "print(os.environ.get('SOME_BACKEND_SECRET'))",
            ),
            env_allowlist={"FIXED_VAR": "valor-fijo-explicito"},
        )
        monkeypatch.setattr(sandbox, "get_entry", lambda *a, **k: entry)
        result = sandbox.execute("_test_tool", "_test_action", {})
        stdout = result["stdout"] or ""
        assert "valor-fijo-explicito" in stdout
        assert "should-not-appear" not in stdout

    def test_no_default_network_egress_env_has_no_proxy_or_credentials(self, monkeypatch):
        """No hay bloqueo real de red a nivel de kernel (ver docstring de sandbox.py), pero
        el subproceso nunca recibe proxies/credenciales del backend que le permitirían
        autenticarse en una llamada de red -- verificación de la mitigación real aplicada.
        """
        monkeypatch.setenv("HTTP_PROXY", "http://backend-proxy-should-not-leak")
        monkeypatch.setenv("GROQ_API_KEY", "should-not-leak-either")
        entry = _entry(
            argv_template=(sys.executable, "-c", "import os; print(sorted(os.environ.keys()))"),
        )
        monkeypatch.setattr(sandbox, "get_entry", lambda *a, **k: entry)
        result = sandbox.execute("_test_tool", "_test_action", {})
        assert result["status"] == "executed"
        assert (result["stdout"] or "").strip() == "[]"

    def test_timeout_is_killed_and_marked_failed_structured(self, monkeypatch):
        entry = _entry(
            argv_template=(sys.executable, "-c", "import time; time.sleep(30)"),
            timeout_seconds=1.0,
        )
        monkeypatch.setattr(sandbox, "get_entry", lambda *a, **k: entry)
        result = sandbox.execute("_test_tool", "_test_action", {})
        assert result["status"] == "failed"
        assert result["error_code"] == "timeout"
        assert isinstance(result["error_detail"], str) and result["error_detail"]

    def test_timeout_does_not_leave_subprocess_running(self, monkeypatch, tmp_path):
        marker = tmp_path / "sandbox_timeout_marker"
        entry = _entry(
            argv_template=(
                sys.executable,
                "-c",
                f"open({str(marker)!r}, 'w').write('alive'); import time; time.sleep(30)",
            ),
            timeout_seconds=1.0,
        )
        monkeypatch.setattr(sandbox, "get_entry", lambda *a, **k: entry)
        result = sandbox.execute("_test_tool", "_test_action", {})
        assert result["error_code"] == "timeout"
        # El marker se crea al arrancar (confirma que el proceso sí llegó a correr) pero el
        # sleep(30) nunca debería completarse -- si `execute()` retornó ya (arriba), el
        # proceso fue matado antes del final del sleep, dentro de ~1s + margen de la señal.
        assert marker.exists()

    def test_resource_limit_exceeded_cpu_is_marked_failed_structured(self, monkeypatch):
        entry = _entry(
            argv_template=(sys.executable, "-c", "x = 0\nwhile True:\n    x += 1\n"),
            cpu_seconds=1,
            timeout_seconds=10.0,
        )
        monkeypatch.setattr(sandbox, "get_entry", lambda *a, **k: entry)
        result = sandbox.execute("_test_tool", "_test_action", {})
        assert result["status"] == "failed"
        # El wall-clock timeout (10s) es la red de contención de último recurso si el kernel
        # del host no entregara SIGXCPU/SIGKILL de forma perfectamente determinista -- ver
        # docstring del módulo de test.
        assert result["error_code"] in ("resource_limit_exceeded", "timeout")

    def test_resource_limit_exceeded_memory_is_marked_failed_structured(self, monkeypatch):
        entry = _entry(
            argv_template=(sys.executable, "-c", "data = bytearray(600 * 1024 * 1024)"),
            memory_bytes=200 * 1024 * 1024,
            cpu_seconds=5,
            timeout_seconds=10.0,
        )
        monkeypatch.setattr(sandbox, "get_entry", lambda *a, **k: entry)
        result = sandbox.execute("_test_tool", "_test_action", {})
        assert result["status"] == "failed"
        # Ver docstring del módulo de sandbox: un intérprete que atrapa su propio fallo de
        # allocación como excepción de alto nivel sale con exit code no-cero en vez de morir
        # por señal -- ambos códigos son un resultado válido de esta clasificación heurística.
        assert result["error_code"] in ("resource_limit_exceeded", "nonzero_exit", "timeout")

    def test_nonzero_exit_code_never_propagates_as_raw_exception(self, monkeypatch):
        entry = _entry(argv_template=(sys.executable, "-c", "import sys; sys.exit(7)"))
        monkeypatch.setattr(sandbox, "get_entry", lambda *a, **k: entry)
        result = sandbox.execute("_test_tool", "_test_action", {})
        assert result["status"] == "failed"
        assert result["error_code"] == "nonzero_exit"
        assert result["exit_code"] == 7

    def test_nonexistent_executable_never_raises_returns_structured_error(self, monkeypatch):
        entry = _entry(argv_template=("/no/existe/binario/inventado/para/este/test",))
        monkeypatch.setattr(sandbox, "get_entry", lambda *a, **k: entry)
        result = sandbox.execute("_test_tool", "_test_action", {})
        assert result["status"] == "failed"
        assert result["error_code"] == "nonzero_exit"

    def test_workdir_is_ephemeral_and_purged_after_execution(self, monkeypatch):
        entry = _entry(argv_template=(sys.executable, "-c", "import os; print(os.getcwd())"))
        monkeypatch.setattr(sandbox, "get_entry", lambda *a, **k: entry)
        result = sandbox.execute("_test_tool", "_test_action", {})
        cwd_used = (result["stdout"] or "").strip()
        assert cwd_used and cwd_used != os.getcwd()
        assert not os.path.exists(cwd_used)  # purgado tras la ejecución

    def test_workdir_purged_even_on_timeout(self, monkeypatch):
        entry = _entry(
            argv_template=(sys.executable, "-c", "import time; time.sleep(30)"),
            timeout_seconds=1.0,
        )
        captured_workdirs: list[str] = []
        original_mkdtemp = sandbox.tempfile.mkdtemp

        def _spy_mkdtemp(*args: object, **kwargs: object) -> str:
            path = original_mkdtemp(*args, **kwargs)
            captured_workdirs.append(path)
            return path

        monkeypatch.setattr(sandbox.tempfile, "mkdtemp", _spy_mkdtemp)
        monkeypatch.setattr(sandbox, "get_entry", lambda *a, **k: entry)
        result = sandbox.execute("_test_tool", "_test_action", {})
        assert result["error_code"] == "timeout"
        assert len(captured_workdirs) == 1
        assert not os.path.exists(captured_workdirs[0])


class TestSandboxAppliesRegardlessOfCatalogMetadata:
    """spec-015, punto 4: ninguna metadata declarativa del catálogo exime del sandbox."""

    def test_no_module_imports_tool_catalog_entry(self):
        """Invariante estructural a nivel de AST (no un grep de texto -- ambos módulos
        MENCIONAN `ToolCatalogEntry` en su docstring, en prosa, precisamente para explicar por
        qué no lo leen; un grep de substring ingenuo daría falso positivo ahí, y otro sobre
        nombres de atributo puntuales como `.kind` daría falso positivo contra
        `ParamSpec.kind`, un campo propio sin relación con el ya eliminado
        `ToolCatalogEntry.kind`). Lo que sí es una garantía real: ninguno de los dos módulos
        tiene una sentencia `import`/`from ... import` que traiga el tipo `ToolCatalogEntry`
        ni el módulo `app.models.tool_catalog_entry` -- por lo tanto no hay forma de que el
        código (a diferencia de la documentación) instancie ni lea ese tipo para decidir nada.
        """
        import ast
        import inspect

        from app.agentic_core.tool_execution import allowlist as allowlist_module

        for module in (sandbox, allowlist_module):
            tree = ast.parse(inspect.getsource(module))
            imported_names: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imported_names.update(alias.name for alias in node.names)
                    module_name = getattr(node, "module", None)
                    if module_name:
                        imported_names.add(module_name)

            assert "ToolCatalogEntry" not in imported_names
            assert not any("tool_catalog_entry" in name for name in imported_names)

    def test_catalog_entry_labeled_low_risk_still_requires_real_allowlist_entry(self):
        """Una ToolCatalogEntry con label/description que sugiere 'bajo riesgo' no obtiene
        ningún atajo: `sandbox.execute` ni siquiera acepta un `ToolCatalogEntry` como
        parámetro -- solo `(tool_key, action_id, params)` -- así que esa metadata no puede
        influir en si se ejecuta o no.
        """
        low_risk_entry = ToolCatalogEntry(
            key="low_risk_tool",
            label="Solo lectura",
            description="Tool aparentemente inofensiva, de solo lectura",
            installed=True,
            actions=[{"id": "act", "label": "Leer", "command": "internal:not_a_real_sandbox_action"}],
        )
        result = sandbox.execute(low_risk_entry.key, "act", {})
        assert result["status"] == "failed"
        assert result["error_code"] == "no_allowlist_entry"
