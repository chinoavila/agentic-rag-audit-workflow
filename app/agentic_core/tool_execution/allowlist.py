"""Allowlist versionada de comandos reales ejecutables por el sandbox (spec-015, punto 1).

## Por qué existe este módulo

`ToolCatalogEntry.actions[].command` (`app/models/tool_catalog_entry.py`) es, por diseño y
sin excepción, texto descriptivo para humanos -- nunca algo que el backend ejecute
directamente. Este módulo es la ÚNICA fuente de verdad de qué `(tool_key, action_id)` tiene
un `argv` real asociado y qué parámetros variables acepta. Reglas no-negociables (spec-015,
punto 1):

1. Ningún comando se arma interpolando texto libre en un string (`f"cmd {user_input}"`,
   `shell=True`, `os.system`). El único artefacto que produce este módulo es una `list[str]`
   (`argv`) con cada posición resuelta contra un schema estricto.
2. `(tool_key, action_id)` ausente de `_ALLOWLIST` (o presente pero con parámetros que no
   validan contra su schema) nunca resuelve a un `argv` -- `resolve_argv` devuelve `None` en
   ambos casos, indistinguiblemente. Ver `sandbox.py` para cómo ambos casos colapsan al mismo
   `error_code="no_allowlist_entry"` en el resultado estructurado (el set de `error_code` de
   `ToolRun` -- spec-015, bloque 1 -- es cerrado y no reserva un código separado para "params
   inválidos"; conceptualmente "no hay un argv resoluble para esta propuesta exacta" es el
   mismo caso que "no hay entrada en la allowlist").
3. Esta allowlist está versionada en el repo (mismo patrón que
   `.ai/guardrails/restricted-ops.json`), no es editable desde `POST/PATCH /api/tools` (ese
   endpoint solo escribe `ToolCatalogEntry`, metadata pura -- ver `app/routers/tools.py`).
   Agregar/modificar una entrada acá es, deliberadamente, un cambio de código con su propio
   review, no una operación de UI/runtime.
4. Este módulo ni siquiera importa el tipo `ToolCatalogEntry` -- no tiene forma de leer sus
   campos declarativos (`label`, `description`, el ya eliminado `kind`) para decidir nada. El
   único insumo de `resolve_argv` es `(tool_key, action_id, params)`. No existe la categoría
   "tool de bajo riesgo" (spec-015, punto 4).

## Estado de este slice (Task 9)

Se puebla con un único caso de ejemplo, explícitamente ilustrativo (`tool_key="_sandbox_example"`,
prefijo `_` para que no pueda confundirse con una key real del catálogo de negocio) -- ninguna
de las tres tools reales seedeadas hoy (`search_evidence`, `create_finding`, `generate_report`,
ver `app/main.py::_SEED_TOOL_CATALOG`) tiene un `command` real: las tres se resuelven vía
`TOOL_DISPATCH` (`app/agentic_core/tools_registry.py`), no vía este sandbox, y por diseño
(spec-015, "Loop Agéntico") la rama de `permission_mode`/`ToolRun` solo aplica a tool-calls que
resuelven a una tool CON `command` real. Agregar una allowlist para una tool de negocio real
(p. ej. un futuro `run_diagnostic_script`) es una decisión de producto explícita, fuera del
alcance de esta task -- acá solo se deja la estructura lista, probada, y con el caso negativo
("no hay entrada -> nunca ejecuta") cubierto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

ParamKind = Literal["enum", "regex"]


@dataclass(frozen=True)
class ParamSpec:
    """Schema estricto para UN parámetro variable de un comando allowlisted.

    Cada parámetro variable de un `argv_template` debe declarar un `ParamSpec` -- nunca se
    sustituye texto libre no validado en una posición del `argv` (spec-015, punto 1).
    """

    name: str
    kind: ParamKind
    enum_values: tuple[str, ...] = ()
    pattern: str = ""

    def __post_init__(self) -> None:
        if self.kind == "enum" and not self.enum_values:
            raise ValueError(f"ParamSpec {self.name!r} kind=enum requiere enum_values no vacío")
        if self.kind == "regex":
            if not self.pattern:
                raise ValueError(f"ParamSpec {self.name!r} kind=regex requiere pattern no vacío")
            re.compile(self.pattern)  # valida en definición, no en cada request

    def is_valid(self, value: object) -> bool:
        """True si `value` matchea el schema declarado. `value` que no sea `str` es inválido
        siempre (evita que un número/dict/lista del LLM se cuele a una posición de `argv`).
        """
        if not isinstance(value, str):
            return False
        if self.kind == "enum":
            return value in self.enum_values
        return re.fullmatch(self.pattern, value) is not None


@dataclass(frozen=True)
class AllowlistEntry:
    """Resuelve UN `(tool_key, action_id)` a un `argv` fijo + los parámetros variables que
    admite, ya validados. También transporta la configuración de sandbox de ESA entrada
    específica (env fijo, límites de recursos, hosts de red) -- spec-015, puntos 1-3.
    """

    tool_key: str
    action_id: str

    # Cada elemento es un literal fijo o un placeholder `"{param_name}"` (`str.format`) que
    # se resuelve exclusivamente con valores ya validados contra su `ParamSpec` -- nunca con
    # el dict crudo de params.
    argv_template: tuple[str, ...]
    params: tuple[ParamSpec, ...] = ()

    # Entorno explícito para el subproceso: SOLO estos pares se exponen -- el sandbox nunca
    # hereda `os.environ` del backend (spec-015, punto 2). Vacío por defecto.
    env_allowlist: dict[str, str] = field(default_factory=dict)

    # Hosts/puertos de red saliente permitidos para esta entrada. Vacío = deny-all (default,
    # ver docstring de `sandbox.py` para el estado REAL -- hoy no implementado -- de
    # enforcement de red). Declarar hosts acá sin que exista enforcement real es, a propósito,
    # rechazado en runtime por `sandbox.execute` (fail-closed) -- ver `sandbox.py`.
    network_hosts: tuple[str, ...] = ()

    timeout_seconds: float = 30.0
    cpu_seconds: int = 10
    memory_bytes: int = 256 * 1024 * 1024

    def _param_names(self) -> frozenset[str]:
        return frozenset(p.name for p in self.params)

    def resolve_argv(self, params: dict[str, object] | None) -> list[str] | None:
        """Devuelve el `argv` resuelto (`list[str]`) o `None` si la propuesta no es
        ejecutable: parámetros no declarados presentes, parámetro declarado ausente, o
        parámetro presente que no matchea su `ParamSpec`. Nunca lanza excepción.
        """
        provided = dict(params or {})
        declared = self._param_names()

        # Cualquier clave no declarada explícitamente se rechaza -- no se ignora en silencio
        # (ignorarla podría esconder al humano/reviewer que el LLM intentó colar un parámetro
        # extra que la allowlist nunca aprobó).
        if set(provided) - declared:
            return None

        resolved: dict[str, str] = {}
        for spec in self.params:
            if spec.name not in provided:
                return None  # todo parámetro declarado es requerido en este slice mínimo
            value = provided[spec.name]
            if not spec.is_valid(value):
                return None
            resolved[spec.name] = value  # type: ignore[assignment] -- ya validado como str

        try:
            return [segment.format(**resolved) for segment in self.argv_template]
        except (KeyError, IndexError, ValueError):
            # Placeholder en argv_template que no matchea ningún ParamSpec declarado -- error
            # de definición de la entrada, no algo que el LLM pueda disparar; igual nunca
            # deja escapar la excepción.
            return None


# ---------------------------------------------------------------------------
# La allowlist real -- versionada, revisada en código, no editable en runtime.
# ---------------------------------------------------------------------------

_ALLOWLIST: dict[tuple[str, str], AllowlistEntry] = {
    # Caso de ejemplo mínimo y explícitamente ilustrativo (ver docstring del módulo, sección
    # "Estado de este slice"). No corresponde a ninguna tool de negocio real del catálogo.
    # Demuestra: argv fijo con un único parámetro variable validado por enum, sin red, con
    # límites de recursos conservadores.
    ("_sandbox_example", "echo_message"): AllowlistEntry(
        tool_key="_sandbox_example",
        action_id="echo_message",
        argv_template=("/bin/echo", "{message}"),
        params=(ParamSpec(name="message", kind="enum", enum_values=("ok", "ping", "pong")),),
        env_allowlist={},
        network_hosts=(),
        timeout_seconds=5.0,
        cpu_seconds=2,
        memory_bytes=64 * 1024 * 1024,
    ),
}


def get_entry(tool_key: str, action_id: str) -> AllowlistEntry | None:
    """Único punto de lectura de la allowlist -- `sandbox.py` nunca accede a `_ALLOWLIST`
    directo, siempre pasa por acá (permite monkeypatchear esta función en tests sin mutar el
    diccionario global versionado).
    """
    return _ALLOWLIST.get((tool_key, action_id))


__all__ = ["ParamSpec", "AllowlistEntry", "get_entry"]
