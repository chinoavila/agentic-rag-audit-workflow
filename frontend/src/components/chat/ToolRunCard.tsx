import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { resolveToolRun } from "@/lib/backend";
import { ApiError } from "@/lib/api";
import type { ToolRun } from "@/types/domain";

// Tarjeta de un `ToolRun` (spec-015). Nunca renderiza el texto crudo de
// `ToolCatalogEntry.actions[].command` -- solo `toolRun.commandResuelto` (ya resuelto por la
// allowlist de security-compliance, ver `app/services/tool_run_execution.py`).
//
// `manual`: `toolRun.permissionModeSnapshot === "manual"` (congelado al proponerse, spec-015)
// -- solo bloque de código copiable, SIN ningún botón de ejecutar/aprobar. Cualquier otro
// snapshot (`accept_edit`, o `auto` degradado -- mismo criterio que usa el loop del agente en
// `app/agentic_core/loop.py::_pending_approval_text`) ofrece Aprobar/Rechazar, con un aviso
// explícito y distinguible si es el caso degradado -- nunca cambia lo que muestra
// `PermissionModeSelector` (ese sigue reflejando `Chat.permission_mode` actual, no el snapshot
// de esta propuesta puntual).
export function ToolRunCard({ toolRun }: { toolRun: ToolRun }) {
  const queryClient = useQueryClient();
  const [editedCommand, setEditedCommand] = useState(toolRun.commandResuelto);
  const [copied, setCopied] = useState(false);

  const resolveMutation = useMutation({
    mutationFn: (patch: { status: "approved" | "rejected"; commandResuelto?: string }) =>
      resolveToolRun(toolRun.id, patch),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["tool-runs", updated.chatId] });
    },
  });

  const copyCommand = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Portapapeles no disponible (contexto no seguro/permiso denegado) -- el bloque de
      // código sigue siendo seleccionable/copiable a mano, no es un error bloqueante.
    }
  };

  const errorMessage =
    resolveMutation.isError
      ? resolveMutation.error instanceof ApiError
        ? resolveMutation.error.message
        : "No se pudo procesar la acción sobre este ToolRun."
      : null;

  return (
    <div className="max-w-[560px] overflow-hidden rounded border border-border bg-bg-raised">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <span className="text-[12.5px] font-semibold">
          {toolRun.toolKey} / {toolRun.actionId}
        </span>
        <ToolRunStatusPill toolRun={toolRun} />
      </div>

      <div className="px-3 py-2.5">
        {toolRun.status === "proposed" && toolRun.permissionModeSnapshot === "auto" && (
          <div className="mb-2 rounded border border-accent/40 bg-accent-tint px-2.5 py-1.5 text-[11.5px] text-accent">
            Modo Auto, pero esta propuesta puntual requiere tu aprobación (origen no verificado
            como turno humano explícito).
          </div>
        )}

        {toolRun.status === "proposed" && toolRun.permissionModeSnapshot === "manual" ? (
          <>
            <p className="mb-1.5 text-[11.5px] text-text-dim">
              Este chat está en modo <code>manual</code>: el agente nunca ejecuta, solo te
              muestra el comando propuesto.
            </p>
            <CodeBlock text={toolRun.commandResuelto} />
            <button
              onClick={() => copyCommand(toolRun.commandResuelto)}
              className="mt-1.5 text-[11px] font-medium text-accent hover:underline"
            >
              {copied ? "Copiado" : "Copiar comando"}
            </button>
          </>
        ) : toolRun.status === "proposed" ? (
          <>
            <label className="mb-1 block text-[10.5px] font-bold uppercase tracking-wide text-text-faint">
              Comando propuesto (editable antes de aprobar)
            </label>
            <textarea
              value={editedCommand}
              onChange={(e) => setEditedCommand(e.target.value)}
              rows={2}
              className="w-full resize-none rounded border border-border bg-bg-sunken px-2.5 py-1.5 font-mono text-[11.5px] outline-none focus:border-accent"
            />
            <div className="mt-2 flex items-center gap-2">
              <button
                onClick={() =>
                  resolveMutation.mutate({
                    status: "approved",
                    commandResuelto: editedCommand !== toolRun.commandResuelto ? editedCommand : undefined,
                  })
                }
                disabled={resolveMutation.isPending}
                className="rounded-full bg-accent px-3 py-1 text-[11.5px] font-semibold text-[#1c1508] disabled:opacity-50"
              >
                Aprobar
              </button>
              <button
                onClick={() => resolveMutation.mutate({ status: "rejected" })}
                disabled={resolveMutation.isPending}
                className="rounded-full border border-border px-3 py-1 text-[11.5px] font-semibold text-text-dim hover:border-flag hover:text-flag disabled:opacity-50"
              >
                Rechazar
              </button>
            </div>
            {errorMessage && <div className="mt-1.5 text-[11px] text-flag">{errorMessage}</div>}
          </>
        ) : (
          <ToolRunTerminalResult toolRun={toolRun} />
        )}
      </div>
    </div>
  );
}

function ToolRunTerminalResult({ toolRun }: { toolRun: ToolRun }) {
  if (toolRun.status === "rejected") {
    return <p className="text-[11.5px] text-text-dim">Rechazado. No se ejecutó nada.</p>;
  }
  if (toolRun.status === "executed") {
    return (
      <div className="flex flex-col gap-1.5">
        <p className="text-[11.5px] text-text-dim">exit_code={toolRun.exitCode}</p>
        <CodeBlock text={toolRun.stdout ?? ""} />
        {toolRun.stderr && <CodeBlock text={toolRun.stderr} label="stderr" />}
      </div>
    );
  }
  if (toolRun.status === "failed") {
    return (
      <div className="flex flex-col gap-1">
        <p className="text-[11.5px] font-semibold text-flag">código: {toolRun.errorCode}</p>
        <p className="text-[11.5px] text-text-dim">{toolRun.errorDetail ?? "Sin detalle adicional."}</p>
      </div>
    );
  }
  return null;
}

function CodeBlock({ text, label }: { text: string; label?: string }) {
  return (
    <div>
      {label && <div className="mb-1 text-[10px] font-bold uppercase tracking-wide text-text-faint">{label}</div>}
      <pre className="scrollbar-thin max-h-40 overflow-auto rounded bg-bg-sunken px-2.5 py-1.5 font-mono text-[11px] text-text-dim">
        {text}
      </pre>
    </div>
  );
}

const STATUS_META: Record<ToolRun["status"], { label: string; className: string }> = {
  proposed: { label: "Pendiente de aprobación", className: "bg-pending-tint text-pending" },
  approved: { label: "Aprobado", className: "bg-pending-tint text-pending" },
  executed: { label: "Ejecutado", className: "bg-verdigris-tint text-verdigris" },
  failed: { label: "Falló", className: "bg-flag-tint text-flag" },
  rejected: { label: "Rechazado", className: "bg-flag-tint text-flag" },
};

function ToolRunStatusPill({ toolRun }: { toolRun: ToolRun }) {
  const meta = STATUS_META[toolRun.status];
  return (
    <span
      className={`ml-auto inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${meta.className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {meta.label}
    </span>
  );
}
