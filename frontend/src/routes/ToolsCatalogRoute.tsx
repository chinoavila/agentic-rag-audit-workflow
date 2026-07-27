import { useQuery } from "@tanstack/react-query";

import { getToolCatalog } from "@/data/mock";

const KIND_META = {
  ro: { label: "solo lectura", className: "bg-verdigris-tint text-verdigris" },
  write: { label: "escribe", className: "bg-flag-tint text-flag" },
};

// Catálogo global (tarea 2a del plan: pasa a leer GET /api/tools real, respaldado por
// ToolCatalogEntry). Instalar/desinstalar y el flujo de alta con acciones+comando (ver el
// mockup) quedan para cuando ese endpoint exista -- por ahora es de solo lectura.
export function ToolsCatalogRoute() {
  const toolsQuery = useQuery({ queryKey: ["tools"], queryFn: getToolCatalog });

  return (
    <div className="scrollbar-thin flex-1 overflow-y-auto p-7">
      <div className="flex h-13 items-center border-b border-border pb-3.5 text-[14.5px] font-semibold">
        Catálogo de herramientas
      </div>
      <p className="mt-3.5 max-w-[64ch] text-[13px] text-text-dim">
        Instalar una herramienta la hace disponible para agregar a cualquier proyecto. Vista de
        solo lectura por ahora (tarea 2a del plan agrega instalar/desinstalar + alta de tools
        nuevas contra el backend real).
      </p>
      <div className="mt-4.5 grid grid-cols-[repeat(auto-fill,minmax(230px,1fr))] gap-3">
        {toolsQuery.data?.map((tool) => {
          const kind = KIND_META[tool.kind];
          return (
            <div key={tool.key} className="flex flex-col gap-2.5 rounded border border-border bg-bg-raised p-3.5">
              <div className="flex items-start gap-2.5">
                <div>
                  <div className="text-[13.5px] font-semibold">{tool.label}</div>
                  <div className="font-mono text-[10.5px] text-text-faint">{tool.key}</div>
                </div>
              </div>
              <p className="flex-1 text-xs leading-relaxed text-text-dim">{tool.description}</p>
              <div className="text-[11px] text-text-faint">
                {tool.actions.length} acción{tool.actions.length === 1 ? "" : "es"} definida
                {tool.actions.length === 1 ? "" : "s"}
              </div>
              <div className="flex items-center justify-between">
                <span className={`rounded px-1.5 py-0.5 text-[9.5px] font-bold uppercase tracking-wide ${kind.className}`}>
                  {kind.label}
                </span>
                <span className="text-xs text-text-dim">{tool.installed ? "Instalada" : "No instalada"}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
