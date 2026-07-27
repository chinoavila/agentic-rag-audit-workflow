import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { addProjectSources, getProjectSources } from "@/lib/backend";

// Fuentes adjuntas a un proyecto: dropzone con drag&drop + selector nativo, lista con tamaño.
// Real contra `POST/GET /api/audit-cases/{id}/files`: cada archivo se ingesta en Chroma
// taggeado con el `case_id` real -- buscable junto con la normativa general desde
// `search_evidence`, sin tool nueva. Sin botón de "quitar" a propósito: `CaseFile` es
// append-only en el backend real (mismo criterio que Finding/Report), no hay DELETE.
export function SourcesPanel({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient();
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const sourcesQuery = useQuery({
    queryKey: ["project-sources", caseId],
    queryFn: () => getProjectSources(caseId),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["project-sources", caseId] });

  const addMutation = useMutation({
    mutationFn: (files: File[]) => addProjectSources(caseId, files),
    onSuccess: invalidate,
  });

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    addMutation.mutate(Array.from(fileList));
  };

  const sources = sourcesQuery.data ?? [];

  return (
    <div>
      <div
        onClick={() => fileInputRef.current?.click()}
        onDragEnter={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragOver={(e) => e.preventDefault()}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={`mb-3.5 cursor-pointer rounded border-[1.5px] border-dashed p-6.5 text-center text-xs transition-colors ${
          dragOver ? "border-accent bg-accent-tint text-text" : "border-border text-text-faint"
        }`}
      >
        Arrastrá archivos aquí o{" "}
        <span className="font-semibold text-accent underline">elegí desde tu equipo</span>
        <br />
        PDF, DOCX, XLSX, MD — buscables junto con la normativa general.
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      {sources.length === 0 ? (
        <div className="p-6.5 text-center text-xs text-text-faint">Sin fuentes adjuntas todavía.</div>
      ) : (
        <div className="flex flex-col">
          {sources.map((file) => (
            <div key={file.id} className="flex items-center gap-3 rounded px-2.5 py-2.5 hover:bg-bg-raised">
              <span className="text-text-faint">📄</span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13.5px] font-medium">{file.name}</div>
                <div className="text-[11.5px] text-text-faint">{file.sizeLabel}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
