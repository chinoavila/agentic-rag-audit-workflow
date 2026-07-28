import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getToolCatalog, setToolInstalled } from "@/lib/backend";
import { Switch } from "@/components/Switch";
import { ToolModal } from "@/components/tools/ToolModal";
import type { ToolCatalogEntry } from "@/types/domain";

// Catálogo global: instalar una herramienta la hace disponible para agregar a cualquier
// proyecto (ver ToolsPanel); desinstalarla no la quita de los proyectos que ya la tengan
// agregada. "Instalar herramienta" / el ícono de engranaje abren el mismo ToolModal
// (alta/edición) que ya define nombre + acciones + comando por acción.
export function ToolsCatalogRoute() {
  const queryClient = useQueryClient();
  const toolsQuery = useQuery({ queryKey: ["tools"], queryFn: getToolCatalog });
  const [modalTool, setModalTool] = useState<ToolCatalogEntry | null | "new">(null);

  const installMutation = useMutation({
    mutationFn: ({ key, installed }: { key: string; installed: boolean }) => setToolInstalled(key, installed),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tools"] }),
  });

  return (
    <div className="scrollbar-thin flex-1 overflow-y-auto p-7">
      <div className="flex h-13 items-center justify-between border-b border-border pb-3.5">
        <div className="text-[14.5px] font-semibold">Catálogo de herramientas</div>
        <button
          className="rounded border border-accent bg-accent px-3 py-1.5 text-xs font-semibold text-[#1c1508]"
          onClick={() => setModalTool("new")}
        >
          + Instalar herramienta
        </button>
      </div>
      <p className="mt-3.5 max-w-[64ch] text-[13px] text-text-dim">
        Instalar una herramienta la hace disponible para agregar a cualquier proyecto (pestaña
        "Herramientas" del proyecto). Desinstalarla no la quita de los proyectos que ya la tengan
        agregada.
      </p>
      <div className="mt-4.5 grid grid-cols-[repeat(auto-fill,minmax(230px,1fr))] gap-3">
        {toolsQuery.data?.map((tool) => {
          return (
            <div key={tool.key} className="flex flex-col gap-2.5 rounded border border-border bg-bg-raised p-3.5">
              <div className="flex items-start gap-2.5">
                <div className="flex-1">
                  <div className="text-[13.5px] font-semibold">{tool.label}</div>
                  <div className="font-mono text-[10.5px] text-text-faint">{tool.key}</div>
                </div>
                <button
                  className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded text-text-dim hover:bg-bg-sunken"
                  title="Editar acciones"
                  onClick={() => setModalTool(tool)}
                >
                  ⚙
                </button>
              </div>
              <p className="flex-1 text-xs leading-relaxed text-text-dim">{tool.description}</p>
              <div className="text-[11px] text-text-faint">
                {tool.actions.length} acción{tool.actions.length === 1 ? "" : "es"} definida
                {tool.actions.length === 1 ? "" : "s"}
              </div>
              <div className="flex items-center justify-end">
                <label className="flex items-center gap-2 text-xs text-text-dim">
                  {tool.installed ? "Instalada" : "No instalada"}
                  <Switch
                    on={tool.installed}
                    onClick={() => installMutation.mutate({ key: tool.key, installed: !tool.installed })}
                  />
                </label>
              </div>
            </div>
          );
        })}
      </div>

      {modalTool !== null && (
        <ToolModal existing={modalTool === "new" ? null : modalTool} onClose={() => setModalTool(null)} />
      )}
    </div>
  );
}
