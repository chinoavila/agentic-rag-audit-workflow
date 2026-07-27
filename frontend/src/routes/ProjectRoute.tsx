import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createChat, getChats, getProject, getReports } from "@/data/mock";
import { SourcesPanel } from "@/components/sources/SourcesPanel";
import { StatusPill } from "@/components/StatusPill";
import { ToolsPanel } from "@/components/tools/ToolsPanel";
import { useRightPanel } from "@/context/RightPanelContext";

type Tab = "chats" | "sources" | "tools" | "reports";

// Vista de proyecto (tarea 3c del plan): por ahora implementa Chats + Informes contra datos
// mock -- Fuentes/Herramientas quedan como placeholder explícito hasta que exista `CaseFile`
// (tarea 3a-3b) y el catálogo dinámico (tarea 2a) en el backend real.
export function ProjectRoute() {
  const { projectId } = useParams<{ projectId: string }>();
  const [tab, setTab] = useState<Tab>("chats");
  const [newChatDraft, setNewChatDraft] = useState("");
  const { openReport } = useRightPanel();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const newChatMutation = useMutation({
    mutationFn: () => createChat(projectId as string),
    onSuccess: (chat) => {
      queryClient.invalidateQueries({ queryKey: ["chats"] });
      navigate(`/projects/${projectId}/chats/${chat.id}`);
    },
  });

  const projectQuery = useQuery({
    queryKey: ["projects", projectId],
    queryFn: () => getProject(projectId as string),
  });
  const chatsQuery = useQuery({
    queryKey: ["chats", { caseId: projectId }],
    queryFn: () => getChats({ caseId: projectId }),
  });
  const reportsQuery = useQuery({
    queryKey: ["reports", { caseId: projectId }],
    queryFn: () => getReports(projectId as string),
  });

  const project = projectQuery.data;
  if (!project) return null;

  return (
    <div className="flex h-full flex-col">
      <div className="flex-shrink-0 px-7 pt-5.5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-accent-tint text-accent">
            📁
          </div>
          <div className="text-balance text-[21px] font-bold">{project.name}</div>
        </div>

        <div className="mt-4 flex items-center gap-2.5 rounded-lg border border-border bg-bg-raised px-4 py-2.5">
          <span className="text-accent">+</span>
          <input
            value={newChatDraft}
            onChange={(e) => setNewChatDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && newChatDraft.trim()) newChatMutation.mutate();
            }}
            placeholder={`Nuevo chat en ${project.name}…`}
            className="flex-1 bg-transparent text-[13.8px] outline-none placeholder:text-text-faint"
          />
        </div>

        <div className="mt-4.5 flex gap-5.5 border-b border-border">
          {(
            [
              ["chats", "Chats"],
              ["sources", "Fuentes"],
              ["tools", "Herramientas"],
              ["reports", "Informes"],
            ] as [Tab, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`border-b-2 pb-2.5 pt-2 text-[13px] font-medium ${
                tab === key ? "border-accent text-text" : "border-transparent text-text-faint hover:text-text"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="scrollbar-thin flex-1 overflow-y-auto px-7 py-4.5">
        {tab === "chats" &&
          (chatsQuery.data?.length ? (
            chatsQuery.data.map((chat) => (
              <Link
                key={chat.id}
                to={`/projects/${project.id}/chats/${chat.id}`}
                className="flex items-center gap-3 rounded px-2.5 py-2.5 hover:bg-bg-raised"
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[13.5px] font-medium">{chat.title ?? "Nuevo chat"}</div>
                </div>
                <div className="flex-shrink-0 text-[11.5px] text-text-faint">
                  {new Date(chat.updatedAt).toLocaleDateString()}
                </div>
              </Link>
            ))
          ) : (
            <EmptyTab text="Todavía no hay chats en este proyecto." />
          ))}

        {tab === "reports" &&
          (reportsQuery.data?.length ? (
            reportsQuery.data.map((report) => (
              <button
                key={report.id}
                onClick={() => openReport(report.id)}
                className="flex w-full items-center gap-3 rounded px-2.5 py-2.5 text-left hover:bg-bg-raised"
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[13.5px] font-medium">{report.title}</div>
                  <div className="text-[11.5px] text-text-faint">{report.sections.length} secciones</div>
                </div>
                <StatusPill status={report.status} />
              </button>
            ))
          ) : (
            <EmptyTab text="Todavía no se generó ningún informe en este proyecto." />
          ))}

        {tab === "sources" && <SourcesPanel caseId={project.id} />}
        {tab === "tools" && <ToolsPanel caseId={project.id} />}
      </div>
    </div>
  );
}

function EmptyTab({ text }: { text: string }) {
  return <div className="p-7 text-center text-[13px] text-text-faint">{text}</div>;
}
