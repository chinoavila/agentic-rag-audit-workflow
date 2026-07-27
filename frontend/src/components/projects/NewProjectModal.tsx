import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { createProject } from "@/data/mock";
import { Modal } from "@/components/Modal";

// Reemplaza el `window.prompt()` placeholder (diálogo nativo del navegador, sin estilo ni
// lugar para más campos) por un componente real de la app -- mismo `Modal` genérico que ya usa
// `ToolModal`. Solo nombre + contexto por ahora: adjuntar fuentes/herramientas al crear queda
// para cuando este modal sume tabs (ver mockup), se pueden agregar después desde las pestañas
// del proyecto ya creado.
export function NewProjectModal({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [context, setContext] = useState("");

  const mutation = useMutation({
    mutationFn: () => createProject(name.trim(), context.trim() || null),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/projects/${project.id}`);
      onClose();
    },
  });

  return (
    <Modal
      title="Nuevo proyecto"
      onClose={onClose}
      footer={
        <>
          <button className="rounded px-3.5 py-2 text-[13px] font-medium hover:bg-bg-sunken" onClick={onClose}>
            Cancelar
          </button>
          <button
            className="rounded border border-accent bg-accent px-3.5 py-2 text-[13px] font-semibold text-[#1c1508] disabled:opacity-40"
            disabled={!name.trim() || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            Crear proyecto
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-text-dim">Nombre del proyecto</label>
          <input
            autoFocus
            className="w-full rounded-sm border border-border bg-bg-sunken px-2.5 py-2 text-sm outline-none focus:border-accent"
            placeholder="p. ej. Auditoría TI — Cliente X"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && name.trim()) mutation.mutate();
            }}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-text-dim">Contexto / instrucciones (opcional)</label>
          <textarea
            className="min-h-24 w-full rounded-sm border border-border bg-bg-sunken px-2.5 py-2 text-sm outline-none focus:border-accent"
            placeholder='p. ej. "Citá siempre fuente y página. Nunca afirmes un hallazgo sin evidencia."'
            value={context}
            onChange={(e) => setContext(e.target.value)}
          />
          <div className="text-[11.5px] text-text-faint">
            Contexto que el asistente respeta para todos los chats de este proyecto.
          </div>
        </div>
      </div>
    </Modal>
  );
}
