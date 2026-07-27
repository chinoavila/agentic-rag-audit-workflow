import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { addProjectTool, getProjectTools, getToolCatalog, removeProjectTool, updateProjectTool } from "@/lib/backend";
import { Switch } from "@/components/Switch";
import type { ToolCatalogEntry, ToolInstance } from "@/types/domain";

const KIND_META: Record<string, { label: string; className: string }> = {
  ro: { label: "solo lectura", className: "bg-verdigris-tint text-verdigris" },
  write: { label: "escribe", className: "bg-flag-tint text-flag" },
};

// Panel n8n-style (ver mockup): catálogo instalado a la izquierda (lo que no está agregado
// todavía a ESTE proyecto), herramientas activas a la derecha, cada una expandible para
// habilitar/deshabilitar, exigir confirmación, y restringir qué acciones puede ejecutar --
// mismo modelo que `ToolInstance.allowedActionIds` (src/types/domain.ts).
export function ToolsPanel({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient();
  const [expandedKey, setExpandedKey] = useState<string | null>(null);

  const catalogQuery = useQuery({ queryKey: ["tools"], queryFn: getToolCatalog });
  const instancesQuery = useQuery({
    queryKey: ["project-tools", caseId],
    queryFn: () => getProjectTools(caseId),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["project-tools", caseId] });

  const addMutation = useMutation({
    mutationFn: (key: string) => addProjectTool(caseId, key),
    onSuccess: invalidate,
  });
  const removeMutation = useMutation({
    mutationFn: (key: string) => removeProjectTool(caseId, key),
    onSuccess: invalidate,
  });
  const patchMutation = useMutation({
    mutationFn: ({ key, patch }: { key: string; patch: Partial<ToolInstance> }) =>
      updateProjectTool(caseId, key, patch),
    onSuccess: invalidate,
  });

  const catalog = catalogQuery.data ?? [];
  const instances = instancesQuery.data ?? [];
  const activeKeys = new Set(instances.map((ti) => ti.key));
  const available = catalog.filter((t) => t.installed && !activeKeys.has(t.key));
  const byKey = (key: string): ToolCatalogEntry | undefined => catalog.find((t) => t.key === key);

  const toggleAction = (ti: ToolInstance, actionId: string) => {
    const set = new Set(ti.allowedActionIds);
    if (set.has(actionId)) set.delete(actionId);
    else set.add(actionId);
    patchMutation.mutate({ key: ti.key, patch: { allowedActionIds: Array.from(set) } });
  };

  return (
    <div className="grid gap-5.5 lg:grid-cols-[1.1fr_1fr]">
      <div>
        <div className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-text-faint">
          Catálogo instalado
        </div>
        {available.length === 0 ? (
          <EmptyNote text="Ya agregaste todas las herramientas instaladas. Instalá más desde el catálogo global." />
        ) : (
          <div className="flex flex-col gap-2.5">
            {available.map((tool) => {
              const kind = KIND_META[tool.kind];
              return (
                <div key={tool.key} className="rounded border border-border bg-bg-raised p-3.5">
                  <div className="text-[13px] font-semibold">{tool.label}</div>
                  <p className="mt-1 text-[11.5px] leading-relaxed text-text-faint">{tool.description}</p>
                  <div className="mt-2 flex items-center justify-between">
                    <span className={`rounded px-1.5 py-0.5 text-[9.5px] font-bold uppercase tracking-wide ${kind.className}`}>
                      {kind.label}
                    </span>
                    <button
                      className="rounded border border-border px-2.5 py-1 text-xs font-semibold hover:border-accent"
                      onClick={() => addMutation.mutate(tool.key)}
                    >
                      + Agregar
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div>
        <div className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-text-faint">
          Herramientas activas en este proyecto
        </div>
        {instances.length === 0 ? (
          <EmptyNote text='Arrastrá ninguna todavía -- usá "+ Agregar" del catálogo a la izquierda.' />
        ) : (
          <div className="flex flex-col gap-2.5">
            {instances.map((ti) => {
              const def = byKey(ti.key);
              if (!def) return null;
              const kind = KIND_META[def.kind];
              const expanded = expandedKey === ti.key;
              return (
                <div key={ti.key} className="rounded border border-border bg-bg-raised p-3">
                  <div className="flex items-center gap-2">
                    <span className="text-[12.8px] font-semibold">{def.label}</span>
                    <span className={`rounded px-1.5 py-0.5 text-[9.5px] font-bold uppercase tracking-wide ${kind.className}`}>
                      {kind.label}
                    </span>
                    <div className="ml-auto flex gap-1">
                      <button
                        className="flex h-7 w-7 items-center justify-center rounded text-text-dim hover:bg-bg-sunken"
                        title="Configurar"
                        onClick={() => setExpandedKey(expanded ? null : ti.key)}
                      >
                        ⚙
                      </button>
                      <button
                        className="flex h-7 w-7 items-center justify-center rounded text-text-dim hover:bg-bg-sunken hover:text-flag"
                        title="Quitar"
                        onClick={() => removeMutation.mutate(ti.key)}
                      >
                        🗑
                      </button>
                    </div>
                  </div>

                  {expanded && (
                    <div className="mt-2.5 flex flex-col gap-2.5 border-t border-border pt-2.5">
                      <FieldRow label="Habilitada en este proyecto">
                        <Switch on={ti.enabled} onClick={() => patchMutation.mutate({ key: ti.key, patch: { enabled: !ti.enabled } })} />
                      </FieldRow>
                      <FieldRow label="Confirmar antes de ejecutar">
                        <Switch on={ti.confirm} onClick={() => patchMutation.mutate({ key: ti.key, patch: { confirm: !ti.confirm } })} />
                      </FieldRow>
                      {def.actions.length > 0 && (
                        <>
                          <div className="mt-1 text-[10.5px] font-bold uppercase tracking-wide text-text-faint">
                            Acciones permitidas
                          </div>
                          {def.actions.map((action) => (
                            <div key={action.id} className="flex flex-col gap-1">
                              <FieldRow label={action.label}>
                                <Switch
                                  on={ti.allowedActionIds.includes(action.id)}
                                  onClick={() => toggleAction(ti, action.id)}
                                />
                              </FieldRow>
                              <div className="self-start rounded bg-bg-sunken px-1.5 py-0.5 font-mono text-[10.5px] text-text-faint">
                                {action.command}
                              </div>
                            </div>
                          ))}
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function FieldRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2.5">
      <span className="text-xs text-text-dim">{label}</span>
      {children}
    </div>
  );
}

function EmptyNote({ text }: { text: string }) {
  return <div className="rounded border border-dashed border-border p-5.5 text-center text-xs text-text-faint">{text}</div>;
}
