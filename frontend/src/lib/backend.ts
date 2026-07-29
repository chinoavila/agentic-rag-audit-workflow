// Cliente real contra el backend FastAPI, vía src/lib/api.ts::apiFetch. Cada función devuelve
// la forma de src/types/domain.ts para que los componentes la consuman con useQuery/useMutation
// sin lógica adicional.

import { apiFetch } from "@/lib/api";
import type {
  CaseFile,
  CaseTool,
  ChatMessage,
  ChatSummary,
  PermissionMode,
  Project,
  ProjectTool,
  Report,
  ToolAction,
  ToolCatalogEntry,
  ToolCatalogEntryDraft,
  ToolRun,
  ToolRunErrorCode,
  ToolRunStatus,
} from "@/types/domain";

// ---------------------------------------------------------------------------
// Proyectos (AuditCase)
// ---------------------------------------------------------------------------

interface AuditCaseApi {
  id: string;
  name: string;
  status: string;
  context: string | null;
  created_at: string;
}

function toProject(c: AuditCaseApi): Project {
  return { id: c.id, name: c.name, status: c.status, context: c.context, updatedAt: c.created_at };
}

export async function getProjects(): Promise<Project[]> {
  const cases = await apiFetch<AuditCaseApi[]>("/audit-cases");
  return cases.map(toProject);
}

export async function getProject(id: string): Promise<Project | undefined> {
  try {
    return toProject(await apiFetch<AuditCaseApi>(`/audit-cases/${id}`));
  } catch {
    return undefined;
  }
}

export async function createProject(name: string, context: string | null = null): Promise<Project> {
  const created = await apiFetch<AuditCaseApi>("/audit-cases", {
    method: "POST",
    body: JSON.stringify({ name, context }),
  });
  return toProject(created);
}

// Soft-hide: nunca hay un DELETE real sobre AuditCase (append-only, ver app/schemas/audit_case.py).
export async function archiveProject(id: string): Promise<Project> {
  const updated = await apiFetch<AuditCaseApi>(`/audit-cases/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status: "archived" }),
  });
  return toProject(updated);
}

// ---------------------------------------------------------------------------
// Chats y mensajes
// ---------------------------------------------------------------------------

interface ChatApi {
  id: string;
  case_id: string | null;
  title: string | null;
  archived: boolean;
  permission_mode: PermissionMode;
  updated_at: string;
}

function toChatSummary(c: ChatApi): ChatSummary {
  return {
    id: c.id,
    caseId: c.case_id,
    title: c.title,
    archived: c.archived,
    permissionMode: c.permission_mode,
    updatedAt: c.updated_at,
  };
}

interface MessageApi {
  id: string;
  chat_id: string;
  role: "user" | "assistant" | "tool";
  content: string | null;
  tool_name: string | null;
  tool_input: Record<string, unknown> | null;
  tool_output: Record<string, unknown> | null;
  report_id: string | null;
  created_at: string;
}

function toChatMessage(m: MessageApi): ChatMessage {
  return {
    id: m.id,
    chatId: m.chat_id,
    role: m.role,
    content: m.content,
    toolName: m.tool_name,
    toolInput: m.tool_input,
    toolOutput: m.tool_output,
    reportId: m.report_id,
    createdAt: m.created_at,
  };
}

export async function getChats(params: { caseId?: string | null; standalone?: boolean } = {}): Promise<ChatSummary[]> {
  const qs = new URLSearchParams();
  if (params.caseId) qs.set("case_id", params.caseId);
  else if (params.standalone) qs.set("standalone", "true");
  const chats = await apiFetch<ChatApi[]>(`/chats?${qs.toString()}`);
  return chats.map(toChatSummary);
}

export async function getChat(id: string): Promise<ChatSummary | undefined> {
  try {
    return toChatSummary(await apiFetch<ChatApi>(`/chats/${id}`));
  } catch {
    return undefined;
  }
}

export async function createChat(caseId: string | null): Promise<ChatSummary> {
  const created = await apiFetch<ChatApi>("/chats", {
    method: "POST",
    body: JSON.stringify({ case_id: caseId }),
  });
  return toChatSummary(created);
}

export async function getMessages(chatId: string): Promise<ChatMessage[]> {
  const messages = await apiFetch<MessageApi[]>(`/chats/${chatId}/messages`);
  return messages.map(toChatMessage);
}

// Soft-hide: nunca hay un DELETE real sobre Chat/Message (append-only, ver app/schemas/chat.py).
export async function archiveChat(id: string): Promise<ChatSummary> {
  const updated = await apiFetch<ChatApi>(`/chats/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ archived: true }),
  });
  return toChatSummary(updated);
}

// `permission_mode` (spec-015) es exclusivamente mutable por una acción humana -- el selector
// del header de `ChatRoute.tsx` es el único caller de esta función. Se reusa el mismo `PATCH
// /api/chats/{id}` que `archiveChat`/renombrar título (nunca un endpoint dedicado).
export async function updateChatPermissionMode(chatId: string, mode: PermissionMode): Promise<ChatSummary> {
  const updated = await apiFetch<ChatApi>(`/chats/${chatId}`, {
    method: "PATCH",
    body: JSON.stringify({ permission_mode: mode }),
  });
  return toChatSummary(updated);
}

export interface PostMessageResult {
  messages: ChatMessage[];
  // Espejo de `ChatTurnResponse.pending_tool_run_id` (spec-015, Task 13): no-`null` cuando el
  // turno quedó pausado esperando aprobación humana de un `ToolRun`. `ChatRoute.tsx` lo usa
  // para pedir ese `ToolRun` puntual sin tener que hacer un `GET .../tool-runs?status=proposed`
  // extra en el caso común.
  pendingToolRunId: string | null;
}

export async function postMessage(chatId: string, content: string): Promise<PostMessageResult> {
  const result = await apiFetch<{ messages: MessageApi[]; pending_tool_run_id: string | null }>(
    `/chats/${chatId}/messages`,
    { method: "POST", body: JSON.stringify({ content }) },
  );
  return {
    messages: result.messages.map(toChatMessage),
    pendingToolRunId: result.pending_tool_run_id ?? null,
  };
}

// ---------------------------------------------------------------------------
// ToolRun (spec-015): propuestas de ejecución de comandos reales, gateadas por
// `Chat.permission_mode`. Consumido por `components/chat/ToolRunCard.tsx`.
// ---------------------------------------------------------------------------

interface ToolRunApi {
  id: string;
  chat_id: string;
  tool_key: string;
  action_id: string;
  command_resuelto: string;
  permission_mode_snapshot: string;
  status: ToolRunStatus;
  triggered_by: "human" | "llm";
  resolved_by: string | null;
  error_code: ToolRunErrorCode | null;
  error_detail: string | null;
  exit_code: number | null;
  stdout: string | null;
  stderr: string | null;
  created_at: string;
  updated_at: string;
}

function toToolRun(t: ToolRunApi): ToolRun {
  return {
    id: t.id,
    chatId: t.chat_id,
    toolKey: t.tool_key,
    actionId: t.action_id,
    commandResuelto: t.command_resuelto,
    // `permission_mode_snapshot` es un snapshot histórico (spec-015): siempre uno de los tres
    // valores de `PermissionMode` en la práctica, pero el backend lo tipa como `str` suelto
    // (`app/models/tool_run.py`) -- se castea acá, nunca se revalida contra el enum.
    permissionModeSnapshot: t.permission_mode_snapshot as PermissionMode,
    status: t.status,
    triggeredBy: t.triggered_by,
    resolvedBy: t.resolved_by,
    errorCode: t.error_code,
    errorDetail: t.error_detail,
    exitCode: t.exit_code,
    stdout: t.stdout,
    stderr: t.stderr,
    createdAt: t.created_at,
    updatedAt: t.updated_at,
  };
}

// `status` opcional -- sin filtro trae todos los `ToolRun` del chat (más recientes primero,
// ver `GET /api/chats/{chat_id}/tool-runs` en `app/routers/tool_runs.py`).
export async function getToolRuns(chatId: string, status?: ToolRunStatus): Promise<ToolRun[]> {
  const qs = status ? `?status=${status}` : "";
  const rows = await apiFetch<ToolRunApi[]>(`/chats/${chatId}/tool-runs${qs}`);
  return rows.map(toToolRun);
}

// `PATCH /api/tool-runs/{id}` -- única forma en que un humano aprueba/rechaza un `ToolRun`
// (`status=proposed` es el único origen válido, ver `VALID_TOOL_RUN_PATCH_TRANSITIONS`).
// `commandResuelto` editado es opcional: si se omite, se aprueba/rechaza tal cual se propuso.
export async function resolveToolRun(
  id: string,
  patch: { status: "approved" | "rejected"; commandResuelto?: string },
): Promise<ToolRun> {
  const body: Record<string, unknown> = { status: patch.status };
  if (patch.commandResuelto !== undefined) body.command_resuelto = patch.commandResuelto;
  const updated = await apiFetch<ToolRunApi>(`/tool-runs/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return toToolRun(updated);
}

// ---------------------------------------------------------------------------
// Catálogo global de herramientas
// ---------------------------------------------------------------------------

export async function getToolCatalog(): Promise<ToolCatalogEntry[]> {
  return apiFetch<ToolCatalogEntry[]>("/tools");
}

export async function setToolInstalled(key: string, installed: boolean): Promise<ToolCatalogEntry> {
  return apiFetch<ToolCatalogEntry>(`/tools/${key}`, {
    method: "PATCH",
    body: JSON.stringify({ installed }),
  });
}

export async function createTool(draft: ToolCatalogEntryDraft): Promise<ToolCatalogEntry> {
  return apiFetch<ToolCatalogEntry>("/tools", {
    method: "POST",
    body: JSON.stringify({
      key: draft.key || null,
      label: draft.label,
      description: draft.description,
      actions: draft.actions,
    }),
  });
}

export async function updateTool(key: string, patch: Omit<ToolCatalogEntryDraft, "key">): Promise<ToolCatalogEntry> {
  return apiFetch<ToolCatalogEntry>(`/tools/${key}`, { method: "PATCH", body: JSON.stringify(patch) });
}

// ---------------------------------------------------------------------------
// Herramientas de un proyecto (spec-013, Task 16/19)
//
// `GET .../tools` deja de devolver solo las filas `ProjectTool` agregadas explícitamente --
// devuelve la vista fusionada default-on de TODAS las `ToolCatalogEntry.installed=true`, cada
// una con su override opcional. La ausencia de `project_tool` YA NO significa "no disponible".
// `POST .../tools` pasó de "agregar tool al proyecto" a "crear/editar el override puntual de
// inclusión/exclusión" -- se mantiene el verbo/ruta HTTP.
// ---------------------------------------------------------------------------

interface ProjectToolApi {
  id: string;
  case_id: string;
  tool_key: string;
  enabled: boolean;
  allowed_action_ids: string[];
  created_at: string;
}

interface CaseToolApi {
  tool_key: string;
  label: string;
  description: string;
  eligible: boolean;
  project_tool: ProjectToolApi | null;
}

function toProjectTool(pt: ProjectToolApi): ProjectTool {
  return {
    id: pt.id,
    caseId: pt.case_id,
    toolKey: pt.tool_key,
    enabled: pt.enabled,
    allowedActionIds: pt.allowed_action_ids,
    createdAt: pt.created_at,
  };
}

function toCaseTool(entry: CaseToolApi): CaseTool {
  return {
    toolKey: entry.tool_key,
    label: entry.label,
    description: entry.description,
    eligible: entry.eligible,
    projectTool: entry.project_tool ? toProjectTool(entry.project_tool) : null,
  };
}

export async function getProjectTools(caseId: string): Promise<CaseTool[]> {
  const rows = await apiFetch<CaseToolApi[]>(`/audit-cases/${caseId}/tools`);
  return rows.map(toCaseTool);
}

// Crea/reutiliza el override `ProjectTool` para `key` (default `enabled=true` al crearse, ver
// `app/routers/project_tools.py::add_project_tool`). Ya NO significa "agregar la tool al
// proyecto" -- una tool instalada globalmente ya es elegible sin esta llamada; úsese
// `setToolEligibility`/`setProjectToolAllowedActions` para las operaciones de UI reales.
export async function addProjectTool(caseId: string, key: string): Promise<CaseTool[]> {
  await apiFetch(`/audit-cases/${caseId}/tools`, { method: "POST", body: JSON.stringify({ tool_key: key }) });
  return getProjectTools(caseId);
}

// Elimina el override puntual (si existe) -- la tool vuelve a su elegibilidad por default del
// catálogo global (`installed=true` => elegible), nunca queda "no disponible" por este llamado.
export async function removeProjectTool(caseId: string, key: string): Promise<CaseTool[]> {
  await apiFetch(`/audit-cases/${caseId}/tools/${key}`, { method: "DELETE" });
  return getProjectTools(caseId);
}

export async function updateProjectTool(
  caseId: string,
  key: string,
  patch: Partial<Pick<ProjectTool, "enabled" | "allowedActionIds">>,
): Promise<CaseTool[]> {
  const body: Record<string, unknown> = {};
  if (patch.enabled !== undefined) body.enabled = patch.enabled;
  if (patch.allowedActionIds !== undefined) body.allowed_action_ids = patch.allowedActionIds;
  await apiFetch(`/audit-cases/${caseId}/tools/${key}`, { method: "PATCH", body: JSON.stringify(body) });
  return getProjectTools(caseId);
}

// Toggle de inclusión/exclusión que la UI puede llamar sin preocuparse si ya existe un
// override: si `tool.projectTool` no existe y se pide `enabled=true`, no hace nada (ya es
// elegible por default); si se pide `enabled=false` sin fila previa, primero la crea (POST) y
// recién ahí aplica el override real (PATCH `enabled=false`) -- `POST .../tools` no acepta
// `enabled` en el payload de creación (`ProjectToolCreate` solo tiene `tool_key`).
export async function setToolEligibility(caseId: string, tool: CaseTool, enabled: boolean): Promise<CaseTool[]> {
  if (!tool.projectTool) {
    if (enabled) return getProjectTools(caseId);
    await addProjectTool(caseId, tool.toolKey);
  }
  return updateProjectTool(caseId, tool.toolKey, { enabled });
}

// Análogo a `setToolEligibility` pero para `allowedActionIds`: crea el override si todavía no
// existe (con `enabled=true` por default) antes de aplicar la restricción de acciones.
export async function setProjectToolAllowedActions(
  caseId: string,
  tool: CaseTool,
  allowedActionIds: string[],
): Promise<CaseTool[]> {
  if (!tool.projectTool) {
    await addProjectTool(caseId, tool.toolKey);
  }
  return updateProjectTool(caseId, tool.toolKey, { allowedActionIds });
}

// ---------------------------------------------------------------------------
// Fuentes (CaseFile) -- sin remove: son append-only en el backend real (a
// diferencia del mock, que sí permitía "quitar" para agilizar la validación de UX).
// ---------------------------------------------------------------------------

interface CaseFileApi {
  id: string;
  case_id: string;
  filename: string;
  size_bytes: number;
  created_at: string;
}

function humanSize(bytes: number): string {
  if (!bytes) return "0 KB";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function toCaseFile(f: CaseFileApi): CaseFile {
  return { id: f.id, name: f.filename, sizeLabel: humanSize(f.size_bytes) };
}

export async function getProjectSources(caseId: string): Promise<CaseFile[]> {
  const rows = await apiFetch<CaseFileApi[]>(`/audit-cases/${caseId}/files`);
  return rows.map(toCaseFile);
}

export async function addProjectSources(caseId: string, files: File[]): Promise<CaseFile[]> {
  for (const file of files) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`/api/audit-cases/${caseId}/files`, { method: "POST", body: formData });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(typeof body.detail === "string" ? body.detail : "Fallo la subida del archivo");
    }
  }
  return getProjectSources(caseId);
}

// ---------------------------------------------------------------------------
// Informes
// ---------------------------------------------------------------------------

interface ReportSectionApi {
  placeholder: string;
  narrative: string;
}

interface ReportApi {
  id: string;
  case_id: string;
  title: string;
  status: Report["status"];
  sections: ReportSectionApi[];
  updated_at: string;
}

function placeholderToHeading(placeholder: string): string {
  return placeholder.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

function toReport(r: ReportApi): Report {
  return {
    id: r.id,
    caseId: r.case_id,
    title: r.title,
    status: r.status,
    updatedAt: r.updated_at,
    sections: r.sections.map((s) => ({ heading: placeholderToHeading(s.placeholder), body: s.narrative })),
  };
}

export async function getReports(caseId: string): Promise<Report[]> {
  const rows = await apiFetch<ReportApi[]>(`/reports?case_id=${caseId}`);
  return rows.map(toReport);
}

export async function getReport(id: string): Promise<Report | undefined> {
  try {
    return toReport(await apiFetch<ReportApi>(`/reports/${id}`));
  } catch {
    return undefined;
  }
}

const DEV_APPROVER_ID = "dev-user-0";

export async function setReportStatus(id: string, status: Report["status"]): Promise<Report> {
  return toReport(
    await apiFetch<ReportApi>(`/reports/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status, approved_by: DEV_APPROVER_ID }),
    }),
  );
}

export type { ToolAction };
