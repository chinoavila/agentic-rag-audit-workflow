import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { archiveChat, archiveProject, getChats, getProjects, getToolCatalog } from "@/lib/backend";
import { Modal } from "@/components/Modal";
import { NewProjectModal } from "@/components/projects/NewProjectModal";

type ArchiveTarget = { kind: "project" | "chat"; id: string; name: string; path: string };

// Primer corte de la Sidebar (tarea 1d/2b del plan): estructura + navegación real contra los
// datos mock. El diseño visual (paleta, tipografía, spacing) está portado 1:1 del mockup vía
// los tokens de tailwind.config.js.
export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [showNewProject, setShowNewProject] = useState(false);
  const [archiveTarget, setArchiveTarget] = useState<ArchiveTarget | null>(null);
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: getProjects });
  const toolsQuery = useQuery({ queryKey: ["tools"], queryFn: getToolCatalog });
  const standaloneChatsQuery = useQuery({
    queryKey: ["chats", { standalone: true }],
    queryFn: () => getChats({ standalone: true }),
  });

  // Soft-hide (archivar), nunca un DELETE real -- ver app/routers/audit_cases.py y
  // app/routers/chats.py. Si el proyecto/chat archivado es el que está abierto ahora mismo,
  // navega a "/" porque va a desaparecer de las listas que lo mantenían visible.
  const archiveMutation = useMutation({
    mutationFn: (target: ArchiveTarget) =>
      target.kind === "project" ? archiveProject(target.id) : archiveChat(target.id),
    onSuccess: (_, target) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["chats"] });
      if (location.pathname === target.path || location.pathname.startsWith(`${target.path}/`)) {
        navigate("/");
      }
      setArchiveTarget(null);
    },
  });

  return (
    <>
    <aside
      className={`flex flex-shrink-0 flex-col overflow-hidden border-r border-sidebar-border bg-sidebar-bg transition-[width] duration-200 ${
        collapsed ? "w-[60px]" : "w-[276px]"
      }`}
    >
      <div className="flex flex-shrink-0 items-center gap-2 px-2.5 py-3.5">
        <button
          className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-sm text-text-dim hover:bg-bg-sunken hover:text-text"
          aria-label="Contraer/expandir sidebar"
          onClick={() => setCollapsed((c) => !c)}
        >
          <MenuIcon />
        </button>
        {!collapsed && (
          <div className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden">
            <div className="flex h-6.5 w-6.5 flex-shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-accent to-verdigris text-[13px] font-extrabold text-[#14110a]">
              A
            </div>
            <div className="truncate text-[14.5px] font-semibold">Agentic Audit RAG Workflow</div>
          </div>
        )}
      </div>

      <div className="flex-shrink-0 px-2.5 pb-2.5">
        <Link
          to="/"
          className={`flex w-full items-center gap-2.5 rounded border border-border bg-bg-raised px-2.5 py-2 text-[13px] font-medium hover:border-accent hover:bg-accent-tint ${
            collapsed ? "justify-center px-0" : ""
          }`}
        >
          <EditIcon />
          {!collapsed && <span className="whitespace-nowrap">Nuevo chat</span>}
        </Link>
      </div>

      <nav className="scrollbar-thin flex flex-1 flex-col gap-4.5 overflow-y-auto px-2 pb-2">
        <div>
          {!collapsed && (
            <div className="flex items-center justify-between px-1.5 pb-1.5">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-text-faint">
                Proyectos
              </span>
              <button
                className="flex h-5 w-5 items-center justify-center rounded text-text-faint hover:bg-bg-sunken hover:text-accent"
                title="Nuevo proyecto"
                onClick={() => setShowNewProject(true)}
              >
                <PlusIcon />
              </button>
            </div>
          )}
          {!collapsed &&
            projectsQuery.data?.map((project) => {
              const active = location.pathname.startsWith(`/projects/${project.id}`);
              return (
                <div key={project.id} className="group/row flex items-center">
                  <Link
                    to={`/projects/${project.id}`}
                    className={`flex min-w-0 flex-1 items-center gap-2 truncate rounded-sm border-l-2 px-2 py-1.5 text-[13px] ${
                      active
                        ? "border-accent bg-accent-tint text-text"
                        : "border-transparent text-text-dim hover:bg-bg-sunken hover:text-text"
                    }`}
                    title={project.name}
                  >
                    <FolderIcon className={active ? "text-accent" : "text-text-faint"} />
                    <span className="truncate">{project.name}</span>
                  </Link>
                  <button
                    className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded text-text-faint opacity-0 hover:bg-bg-sunken hover:text-flag group-hover/row:opacity-100"
                    title="Borrar proyecto"
                    aria-label={`Borrar proyecto ${project.name}`}
                    onClick={(e) => {
                      e.preventDefault();
                      setArchiveTarget({
                        kind: "project",
                        id: project.id,
                        name: project.name,
                        path: `/projects/${project.id}`,
                      });
                    }}
                  >
                    <TrashIcon />
                  </button>
                </div>
              );
            })}
        </div>

        {!collapsed && (
          <div>
            <div className="px-1.5 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-faint">
              Herramientas
            </div>
            <Link
              to="/tools"
              className={`flex items-center gap-2 rounded-sm border-l-2 px-2 py-1.5 text-[13px] ${
                location.pathname === "/tools"
                  ? "border-accent bg-accent-tint text-text"
                  : "border-transparent text-text-dim hover:bg-bg-sunken hover:text-text"
              }`}
            >
              <SlidersIcon />
              <span>
                Catálogo de herramientas
                {toolsQuery.data ? ` (${toolsQuery.data.filter((t) => t.installed).length})` : ""}
              </span>
            </Link>
          </div>
        )}

        {!collapsed && !!standaloneChatsQuery.data?.length && (
          <div>
            <div className="px-1.5 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-faint">
              Recientes
            </div>
            {standaloneChatsQuery.data.map((chat) => (
              <div key={chat.id} className="group/row flex items-center">
                <Link
                  to={`/chats/${chat.id}`}
                  className={`flex min-w-0 flex-1 items-center gap-2 truncate rounded-sm border-l-2 px-2 py-1.5 text-[13px] ${
                    location.pathname === `/chats/${chat.id}`
                      ? "border-accent bg-accent-tint text-text"
                      : "border-transparent text-text-dim hover:bg-bg-sunken hover:text-text"
                  }`}
                >
                  <ChatIcon className="text-text-faint" />
                  <span className="truncate">{chat.title ?? "Nuevo chat"}</span>
                </Link>
                <button
                  className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded text-text-faint opacity-0 hover:bg-bg-sunken hover:text-flag group-hover/row:opacity-100"
                  title="Borrar conversación"
                  aria-label={`Borrar conversación ${chat.title ?? "Nuevo chat"}`}
                  onClick={(e) => {
                    e.preventDefault();
                    setArchiveTarget({
                      kind: "chat",
                      id: chat.id,
                      name: chat.title ?? "Nuevo chat",
                      path: `/chats/${chat.id}`,
                    });
                  }}
                >
                  <TrashIcon />
                </button>
              </div>
            ))}
          </div>
        )}
      </nav>

      <div className="flex flex-shrink-0 items-center gap-2.5 border-t border-sidebar-border p-2.5">
        <div className="flex h-6.5 w-6.5 flex-shrink-0 items-center justify-center rounded-full bg-verdigris text-[11.5px] font-bold text-[#eafff9]">
          AA
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <div className="truncate text-[12.5px] font-semibold">Alejandro Ávila</div>
            <div className="truncate text-[11px] text-text-faint">Auditor · dev-user-0</div>
          </div>
        )}
      </div>
    </aside>
    {showNewProject && <NewProjectModal onClose={() => setShowNewProject(false)} />}
    {archiveTarget && (
      <Modal
        title={archiveTarget.kind === "project" ? "Borrar proyecto" : "Borrar conversación"}
        onClose={() => setArchiveTarget(null)}
        footer={
          <>
            <button
              className="rounded px-3.5 py-2 text-[13px] font-medium hover:bg-bg-sunken"
              onClick={() => setArchiveTarget(null)}
            >
              Cancelar
            </button>
            <button
              className="rounded border border-flag bg-flag px-3.5 py-2 text-[13px] font-semibold text-white disabled:opacity-40"
              disabled={archiveMutation.isPending}
              onClick={() => archiveMutation.mutate(archiveTarget)}
            >
              Borrar
            </button>
          </>
        }
      >
        <p className="text-[13px] text-text-dim">
          {archiveTarget.kind === "project" ? (
            <>
              Se va a ocultar el proyecto <strong className="text-text">{archiveTarget.name}</strong> del
              sidebar. Los chats, hallazgos e informes del proyecto no se borran -- siguen
              existiendo en la base de datos.
            </>
          ) : (
            <>
              Se va a ocultar la conversación <strong className="text-text">{archiveTarget.name}</strong>{" "}
              del sidebar. Los mensajes no se borran -- siguen existiendo en la base de datos.
            </>
          )}
        </p>
      </Modal>
    )}
    </>
  );
}

function MenuIcon() {
  return (
    <svg className="h-[17px] w-[17px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
      <path d="M3 6h18M3 12h18M3 18h18" />
    </svg>
  );
}
function EditIcon() {
  return (
    <svg className="h-[17px] w-[17px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}
function PlusIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}
function FolderIcon({ className = "" }: { className?: string }) {
  return (
    <svg className={`h-[17px] w-[17px] flex-shrink-0 ${className}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z" />
    </svg>
  );
}
function SlidersIcon() {
  return (
    <svg className="h-[17px] w-[17px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
      <path d="M5 21V10M5 6V3M12 21v-7M12 10V3M19 21v-4M19 13V3" />
      <circle cx="5" cy="8" r="2" />
      <circle cx="12" cy="12" r="2" />
      <circle cx="19" cy="15" r="2" />
    </svg>
  );
}
function ChatIcon({ className = "" }: { className?: string }) {
  return (
    <svg className={`h-[17px] w-[17px] flex-shrink-0 ${className}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 11.5a8.5 8.5 0 1 1-3.8-7.1L21 3l-1 4.3a8.4 8.4 0 0 1 1 4.2Z" />
    </svg>
  );
}
function TrashIcon() {
  return (
    <svg className="h-[14px] w-[14px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 7h16" />
      <path d="M9 7V4.5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1V7" />
      <path d="M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13" />
      <path d="M10 11v6M14 11v6" />
    </svg>
  );
}
