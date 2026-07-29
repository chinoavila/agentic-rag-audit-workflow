import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getProjectTools,
  getToolCatalog,
  removeProjectTool,
  setProjectToolAllowedActions,
  setToolEligibility,
} from "@/lib/backend";
import { Switch } from "@/components/Switch";
import type { CaseTool } from "@/types/domain";

// Panel de herramientas del proyecto (spec-013, Task 16/19; ver mockup). El backend devuelve
// TODAS las `ToolCatalogEntry.installed=true` del catálogo global -- default-on -- así que ya
// no hay dos columnas "catálogo disponible" / "activas en el proyecto": una única lista con
// el estado `eligible` de cada tool. La ausencia de override (`projectTool === null`) significa
// "elegible por default, sin personalización", NUNCA "no disponible". El control de "agregar"
// pasa a ser un toggle de inclusión/exclusión.
export function ToolsPanel({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient();
  const [expandedKey, setExpandedKey] = useState<string | null>(null);

  // Se sigue consultando el catálogo global solo para resolver `label`/`command` de las
  // acciones de cada tool -- `GET .../audit-cases/{id}/tools` no las incluye (ver
  // `CaseToolOut` en `app/schemas/project_tool.py`).
  const catalogQuery = useQuery({ queryKey: ["tools"], queryFn: getToolCatalog });
  const toolsQuery = useQuery({
    queryKey: ["project-tools", caseId],
    queryFn: () => getProjectTools(caseId),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["project-tools", caseId] });

  const eligibilityMutation = useMutation({
    mutationFn: ({ tool, enabled }: { tool: CaseTool; enabled: boolean }) =>
      setToolEligibility(caseId, tool, enabled),
    onSuccess: invalidate,
  });
  const resetMutation = useMutation({
    mutationFn: (key: string) => removeProjectTool(caseId, key),
    onSuccess: invalidate,
  });
  const actionsMutation = useMutation({
    mutationFn: ({ tool, allowedActionIds }: { tool: CaseTool; allowedActionIds: string[] }) =>
      setProjectToolAllowedActions(caseId, tool, allowedActionIds),
    onSuccess: invalidate,
  });

  const tools = toolsQuery.data ?? [];
  const catalog = catalogQuery.data ?? [];
  const actionsFor = (toolKey: string) => catalog.find((t) => t.key === toolKey)?.actions ?? [];

  const toggleAction = (tool: CaseTool, actionId: string) => {
    const allActionIds = actionsFor(tool.toolKey).map((a) => a.id);
    const current = new Set(tool.projectTool?.allowedActionIds ?? allActionIds);
    if (current.has(actionId)) current.delete(actionId);
    else current.add(actionId);
    actionsMutation.mutate({ tool, allowedActionIds: Array.from(current) });
  };

  return (
    <div>
      <div className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-text-faint">
        Herramientas instaladas globalmente
      </div>
      {tools.length === 0 ? (
        <EmptyNote text="No hay herramientas instaladas en el catálogo global todavía. Instalá alguna desde el catálogo de herramientas." />
      ) : (
        <div className="flex flex-col gap-2.5">
          {tools.map((tool) => {
            const expanded = expandedKey === tool.toolKey;
            const hasOverride = tool.projectTool !== null;
            const actions = actionsFor(tool.toolKey);
            const allowedActionIds = tool.projectTool?.allowedActionIds ?? actions.map((a) => a.id);
            return (
              <div key={tool.toolKey} className="rounded border border-border bg-bg-raised p-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[12.8px] font-semibold">{tool.label}</span>
                      <span
                        className={`rounded px-1.5 py-0.5 text-[9.5px] font-semibold uppercase tracking-wide ${
                          hasOverride ? "bg-accent-tint-strong text-accent" : "text-text-faint"
                        }`}
                        title={
                          hasOverride
                            ? "Tiene un override puntual para este proyecto"
                            : "Elegible por default del catálogo global, sin override"
                        }
                      >
                        {hasOverride ? "override" : "default"}
                      </span>
                    </div>
                    <p className="mt-1 text-[11.5px] leading-relaxed text-text-faint">{tool.description}</p>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      className="flex h-7 w-7 items-center justify-center rounded text-text-dim hover:bg-bg-sunken"
                      title="Configurar acciones permitidas"
                      onClick={() => setExpandedKey(expanded ? null : tool.toolKey)}
                    >
                      ⚙
                    </button>
                    {hasOverride && (
                      <button
                        className="flex h-7 w-7 items-center justify-center rounded text-text-dim hover:bg-bg-sunken"
                        title="Quitar override -- vuelve al default del catálogo global"
                        onClick={() => resetMutation.mutate(tool.toolKey)}
                      >
                        ↺
                      </button>
                    )}
                    <Switch
                      on={tool.eligible}
                      onClick={() => eligibilityMutation.mutate({ tool, enabled: !tool.eligible })}
                    />
                  </div>
                </div>

                {expanded && (
                  <div className="mt-2.5 flex flex-col gap-2.5 border-t border-border pt-2.5">
                    <FieldRow label="Habilitada en este proyecto">
                      <Switch
                        on={tool.eligible}
                        onClick={() => eligibilityMutation.mutate({ tool, enabled: !tool.eligible })}
                      />
                    </FieldRow>
                    {actions.length > 0 && (
                      <>
                        <div className="mt-1 text-[10.5px] font-bold uppercase tracking-wide text-text-faint">
                          Acciones permitidas
                        </div>
                        {actions.map((action) => (
                          <div key={action.id} className="flex flex-col gap-1">
                            <FieldRow label={action.label}>
                              <Switch
                                on={allowedActionIds.includes(action.id)}
                                onClick={() => toggleAction(tool, action.id)}
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
