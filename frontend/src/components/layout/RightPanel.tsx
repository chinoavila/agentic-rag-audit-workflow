import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getReport, setReportStatus } from "@/lib/backend";
import { StatusPill } from "@/components/StatusPill";
import { useRightPanel } from "@/context/RightPanelContext";

// Panel lateral derecho estilo "Artifact" (ver mockup): persiste montado independientemente de
// qué ruta esté activa (controlado por RightPanelContext, no por la URL), igual que el panel de
// artifacts de Claude.
export function RightPanel() {
  const { open, reportId, close } = useRightPanel();
  const queryClient = useQueryClient();

  const reportQuery = useQuery({
    queryKey: ["reports", reportId],
    queryFn: () => getReport(reportId as string),
    enabled: open && !!reportId,
  });

  const statusMutation = useMutation({
    mutationFn: (status: "published" | "rejected") => setReportStatus(reportId as string, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reports"] });
    },
  });

  const report = reportQuery.data;

  // Descarga real (spec-020, tarea 4a): GET /api/reports/{id}/export?format= devuelve el
  // archivo con Content-Disposition: attachment -- alcanza con navegar a la URL, el backend ya
  // le pone el nombre de archivo correcto, no hace falta armar un Blob a mano en el cliente.
  const download = (format: "docx" | "pdf") => {
    if (!report) return;
    const a = document.createElement("a");
    a.href = `/api/reports/${report.id}/export?format=${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
    <aside
      className={`flex-shrink-0 overflow-hidden border-l border-border bg-bg transition-[width] duration-200 ${
        open ? "w-[min(480px,42vw)]" : "w-0"
      }`}
    >
      {open && report && (
        <div className="flex h-full w-[min(480px,42vw)] flex-col">
          <div className="flex flex-shrink-0 items-start gap-2.5 border-b border-border px-4 py-3.5">
            <div className="min-w-0 flex-1">
              <div className="text-balance text-sm font-semibold">{report.title}</div>
              <div className="mt-1.5 flex items-center gap-2">
                <StatusPill status={report.status} />
                <span className="text-[11.5px] text-text-faint">
                  Actualizado {new Date(report.updatedAt).toLocaleDateString()}
                </span>
              </div>
            </div>
            <button
              className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-sm text-text-dim hover:bg-bg-sunken hover:text-text"
              onClick={close}
              aria-label="Cerrar"
            >
              ✕
            </button>
          </div>

          <div className="scrollbar-thin flex-1 overflow-y-auto p-5.5">
            <div className="rounded border border-border bg-bg-raised p-8 shadow-lg">
              <div className="mb-3.5 text-[10.5px] font-bold uppercase tracking-wider text-accent">
                Informe de auditoría
              </div>
              <h2 className="text-balance text-base font-bold">{report.title}</h2>
              {report.sections.map((section) => (
                <div key={section.heading} className="mt-5 first:mt-0">
                  <h3 className="mb-2 text-[12.5px] font-bold uppercase tracking-wide text-text-dim">
                    {section.heading}
                  </h3>
                  <p className="text-[13.2px] leading-relaxed">{section.body}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-shrink-0 flex-col gap-2.5 border-t border-border p-3">
            {report.status === "pending_review" && (
              <div className="flex gap-2">
                <button
                  className="flex flex-1 items-center justify-center gap-1.5 rounded border border-accent bg-accent px-2.5 py-1.5 text-xs font-semibold text-[#1c1508]"
                  onClick={() => statusMutation.mutate("published")}
                >
                  Aprobar
                </button>
                <button
                  className="flex flex-1 items-center justify-center gap-1.5 rounded border border-transparent px-2.5 py-1.5 text-xs font-semibold text-flag hover:border-flag hover:bg-flag-tint"
                  onClick={() => statusMutation.mutate("rejected")}
                >
                  Rechazar
                </button>
              </div>
            )}
            <div className="flex gap-2">
              <button
                className="flex-1 rounded border border-border px-2.5 py-1.5 text-xs font-semibold hover:border-accent"
                onClick={() => download("docx")}
              >
                Descargar .docx
              </button>
              <button
                className="flex-1 rounded border border-border px-2.5 py-1.5 text-xs font-semibold hover:border-accent"
                onClick={() => download("pdf")}
              >
                Descargar .pdf
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
