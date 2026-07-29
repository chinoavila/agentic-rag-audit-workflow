import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createChat,
  getChat,
  getMessages,
  getProject,
  getToolRuns,
  postMessage,
  updateChatPermissionMode,
} from "@/lib/backend";
import { ApiError } from "@/lib/api";
import { StatusPill } from "@/components/StatusPill";
import { PermissionModeSelector } from "@/components/chat/PermissionModeSelector";
import { ToolRunCard } from "@/components/chat/ToolRunCard";
import { useRightPanel } from "@/context/RightPanelContext";
import type { ChatMessage, ChatSummary, PermissionMode } from "@/types/domain";

// Chat view: usa /api/chats/{id}/messages real vía src/lib/backend.ts::postMessage.
// Sin streaming real (decisión del plan): revela `final_text` palabra por palabra, igual que
// hacía `chainlit_ui/chat.py::_stream_chunks`.
export function ChatRoute() {
  const { chatId, projectId } = useParams<{ chatId?: string; projectId?: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const threadRef = useRef<HTMLDivElement>(null);

  // Selector de `permission_mode` (spec-015): mientras el chat todavía no existe (borrador de
  // chat nuevo), no hay `Chat` real donde persistir el valor -- se guarda acá y se aplica con
  // un `PATCH` recién después de `createChat` (ver `sendMutation` abajo). Se resetea a "manual"
  // (default del backend) cada vez que cambia de chat/ruta.
  const [draftPermissionMode, setDraftPermissionMode] = useState<PermissionMode>("manual");
  // `ToolRun` puntual que dejó pausado el último turno (spec-015) -- ver `pendingToolRunId` de
  // `postMessage`. Se resetea al cambiar de chat; se recupera también al recargar la página
  // (ver el `useEffect` que barre `toolRunsQuery.data` más abajo) para no perder un turno
  // pausado si el usuario refresca antes de aprobar/rechazar.
  const [pendingToolRunId, setPendingToolRunId] = useState<string | null>(null);

  useEffect(() => {
    setDraftPermissionMode("manual");
    setPendingToolRunId(null);
  }, [chatId]);

  const chatQuery = useQuery({
    queryKey: ["chats", chatId],
    queryFn: () => getChat(chatId as string),
    enabled: !!chatId,
  });
  const projectQuery = useQuery({
    queryKey: ["projects", projectId],
    queryFn: () => getProject(projectId as string),
    enabled: !!projectId,
  });
  const messagesQuery = useQuery({
    queryKey: ["messages", chatId],
    queryFn: () => getMessages(chatId as string),
    enabled: !!chatId,
  });
  // Sin filtro de status: conserva en la lista los ToolRun ya resueltos de este turno (para
  // poder mostrar su estado terminal -- executed/failed/rejected) además de los `proposed`
  // pendientes. Acotado por diseño al alcance de un chat individual (prototipo).
  const toolRunsQuery = useQuery({
    queryKey: ["tool-runs", chatId],
    queryFn: () => getToolRuns(chatId as string),
    enabled: !!chatId,
  });

  // Recupera un turno pausado tras un refresh de página: si no hay ningún `pendingToolRunId`
  // en memoria pero el chat tiene un `ToolRun` en `status=proposed`, lo adopta.
  useEffect(() => {
    if (pendingToolRunId || !toolRunsQuery.data) return;
    const proposed = toolRunsQuery.data.find((t) => t.status === "proposed");
    if (proposed) setPendingToolRunId(proposed.id);
  }, [toolRunsQuery.data, pendingToolRunId]);

  const permissionModeMutation = useMutation({
    mutationFn: ({ id, mode }: { id: string; mode: PermissionMode }) => updateChatPermissionMode(id, mode),
    onMutate: async ({ id, mode }) => {
      await queryClient.cancelQueries({ queryKey: ["chats", id] });
      const previous = queryClient.getQueryData<ChatSummary>(["chats", id]);
      queryClient.setQueryData<ChatSummary | undefined>(["chats", id], (old) =>
        old ? { ...old, permissionMode: mode } : old,
      );
      return { previous };
    },
    onError: (_err, { id }, context) => {
      // Revierte al valor anterior si el PATCH falla (spec-015: "revertir si falla").
      if (context?.previous) queryClient.setQueryData(["chats", id], context.previous);
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(["chats", updated.id], updated);
    },
  });

  const handlePermissionModeChange = (mode: PermissionMode) => {
    if (!chatId) {
      // Todavía no hay un `Chat` real -- se aplica recién cuando se crea (ver sendMutation).
      setDraftPermissionMode(mode);
      return;
    }
    permissionModeMutation.mutate({ id: chatId, mode });
  };

  const sendMutation = useMutation({
    mutationFn: async (content: string) => {
      let id = chatId;
      if (!id) {
        const chat = await createChat(projectId ?? null);
        id = chat.id;
        if (draftPermissionMode !== "manual") {
          await updateChatPermissionMode(id, draftPermissionMode);
        }
      }
      const result = await postMessage(id, content);
      return { id, result };
    },
    onSuccess: ({ id, result }) => {
      queryClient.invalidateQueries({ queryKey: ["messages", id] });
      queryClient.invalidateQueries({ queryKey: ["chats"] });
      queryClient.invalidateQueries({ queryKey: ["tool-runs", id] });
      setPendingToolRunId(result.pendingToolRunId);
      if (!chatId) {
        navigate(projectId ? `/projects/${projectId}/chats/${id}` : `/chats/${id}`);
      }
    },
  });

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight });
  }, [messagesQuery.data, sendMutation.isPending]);

  const handleSend = () => {
    const content = draft.trim();
    if (!content) return;
    setDraft("");
    sendMutation.mutate(content);
  };

  const messages = messagesQuery.data ?? [];
  const project = projectQuery.data;
  const chat = chatQuery.data;
  const permissionMode = chat?.permissionMode ?? (chatId ? "manual" : draftPermissionMode);
  const activeToolRun = pendingToolRunId
    ? toolRunsQuery.data?.find((t) => t.id === pendingToolRunId)
    : undefined;
  const pendingContent = sendMutation.isPending ? sendMutation.variables : undefined;
  const errorMessage =
    sendMutation.isError
      ? sendMutation.error instanceof ApiError
        ? sendMutation.error.message
        : "No se pudo enviar el mensaje. Probá de nuevo."
      : null;
  const showThread = messages.length > 0 || pendingContent !== undefined;

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-13 flex-shrink-0 items-center gap-2.5 border-b border-border px-4.5">
        {project && (
          <Link
            to={`/projects/${project.id}`}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg-sunken px-2.5 py-1 text-xs font-medium text-text-dim hover:border-accent hover:text-text"
          >
            {project.name}
          </Link>
        )}
        <div className="text-[14.5px] font-semibold">{chat?.title ?? "Nuevo chat"}</div>
        <PermissionModeSelector
          value={permissionMode}
          onChange={handlePermissionModeChange}
          disabled={permissionModeMutation.isPending}
        />
      </div>

      {showThread ? (
        <div ref={threadRef} className="scrollbar-thin flex-1 overflow-y-auto py-6">
          <div className="mx-auto flex w-full max-w-[720px] flex-col gap-4.5 px-6">
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
            {pendingContent !== undefined && (
              <>
                <MessageBubble
                  message={{
                    id: "pending-user",
                    chatId: chatId ?? "",
                    role: "user",
                    content: pendingContent,
                    toolName: null,
                    toolInput: null,
                    toolOutput: null,
                    reportId: null,
                    createdAt: "",
                  }}
                />
                <ThinkingBubble />
              </>
            )}
            {activeToolRun && <ToolRunCard toolRun={activeToolRun} />}
          </div>
        </div>
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center gap-1.5 p-6 text-center">
          <h1 className="text-balance text-xl font-semibold">
            {project ? `Nuevo chat en ${project.name}` : "¿Qué necesitás revisar hoy?"}
          </h1>
          <p className="max-w-[46ch] text-[13.5px] text-text-dim">
            Pedime que busque evidencia, registre un hallazgo o genere un informe.
          </p>
        </div>
      )}

      <div className="flex-shrink-0 px-6 pb-5 pt-3.5">
        {errorMessage && (
          <div className="mx-auto mb-2.5 max-w-[720px] rounded-lg border border-flag/30 bg-flag-tint px-3.5 py-2 text-[12.8px] text-flag">
            {errorMessage}
          </div>
        )}
        <div className="mx-auto flex max-w-[720px] items-end gap-2 rounded-lg border border-border bg-bg-raised p-2 pl-4 shadow-lg">
          <textarea
            rows={1}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={project ? `Escribir en ${project.name}…` : "Escribí tu mensaje…"}
            className="max-h-40 flex-1 resize-none bg-transparent py-2 text-[13.8px] outline-none placeholder:text-text-faint"
          />
          <button
            className="flex h-8.5 w-8.5 flex-shrink-0 items-center justify-center rounded-full bg-accent text-[#1c1508] disabled:opacity-40"
            onClick={handleSend}
            disabled={!draft.trim() || sendMutation.isPending}
            aria-label="Enviar"
          >
            ➤
          </button>
        </div>
        <div className="mt-2 text-center text-[11px] text-text-faint">
          Sin streaming real todavía (ver plan spec-020) — la respuesta se revela de una vez.
        </div>
      </div>
    </div>
  );
}

function ThinkingBubble() {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 text-xs font-semibold text-text-dim">
        <span className="h-1.5 w-1.5 rounded-full bg-verdigris" /> Asistente
      </div>
      <div className="flex items-center gap-1 text-[13.6px] text-text-faint">
        <span className="animate-bounce [animation-delay:0ms]">●</span>
        <span className="animate-bounce [animation-delay:150ms]">●</span>
        <span className="animate-bounce [animation-delay:300ms]">●</span>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const { openReport } = useRightPanel();

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[78%] rounded-lg border border-accent-tint-strong bg-accent-tint-strong px-3.5 py-2.5 text-[13.6px] leading-relaxed">
          {message.content}
        </div>
      </div>
    );
  }

  if (message.role === "tool") {
    return (
      <ToolStep name={message.toolName ?? "tool"} input={message.toolInput} output={message.toolOutput} reportId={message.reportId} onOpenReport={openReport} />
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 text-xs font-semibold text-text-dim">
        <span className="h-1.5 w-1.5 rounded-full bg-verdigris" /> Asistente
      </div>
      {message.reportId && (
        <ReportReferenceCard reportId={message.reportId} onOpen={openReport} />
      )}
      <div className="text-[13.6px] leading-relaxed">{message.content}</div>
    </div>
  );
}

function ToolStep({
  name,
  input,
  output,
}: {
  name: string;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  reportId: string | null;
  onOpenReport: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="max-w-[520px] overflow-hidden rounded border border-border bg-bg-raised">
      <button
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="text-[12.5px] font-semibold">{name}</span>
        <span className="rounded bg-verdigris-tint px-1.5 py-0.5 text-[10px] font-bold uppercase text-verdigris">
          tool
        </span>
        <span className={`ml-auto text-text-faint transition-transform ${open ? "rotate-90" : ""}`}>›</span>
      </button>
      {open && (
        <div className="border-t border-border px-3 py-2.5 font-mono text-[11.5px] text-text-dim">
          <div>input: {JSON.stringify(input)}</div>
          <div className="mt-1.5">output: {JSON.stringify(output)}</div>
        </div>
      )}
    </div>
  );
}

function ReportReferenceCard({ reportId, onOpen }: { reportId: string; onOpen: (id: string) => void }) {
  // La forma de status real viene de la query de reports en RightPanel; acá solo hace falta
  // saber el id para abrir el panel, por eso no se resuelve un status pill acá (evita otra
  // request duplicada) -- ver RightPanel para el detalle completo.
  return (
    <button
      onClick={() => onOpen(reportId)}
      className="flex max-w-[420px] items-center gap-2.5 rounded border border-border bg-bg-raised px-3 py-2.5 text-left hover:border-accent"
    >
      <div className="flex h-7.5 w-7.5 flex-shrink-0 items-center justify-center rounded-md bg-accent-tint text-accent">
        📄
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[12.8px] font-semibold">Informe generado</div>
        <div className="text-[11px] text-text-faint">Click para previsualizar</div>
      </div>
    </button>
  );
}
