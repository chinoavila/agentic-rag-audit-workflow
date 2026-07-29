// Tipos del dominio (espejo de app/schemas/*.py). Es la forma que devuelve `src/lib/backend.ts`
// para cada `queryFn`/`mutationFn` de `useQuery`/`useMutation`.

export interface ToolAction {
  id: string;
  label: string;
  command: string;
}

export interface ToolCatalogEntry {
  key: string;
  label: string;
  description: string;
  installed: boolean;
  actions: ToolAction[];
}

export interface ToolCatalogEntryDraft {
  label: string;
  key: string;
  description: string;
  actions: ToolAction[];
}

// Override puntual de una tool para un proyecto (spec-013, Task 16/19). Espejo de
// `ProjectToolOut` (`app/schemas/project_tool.py`): representa exclusivamente la fila
// `ProjectTool` cuando existe -- NO decide por sí sola si la tool está disponible en el
// proyecto (eso es `CaseTool.eligible`, ver abajo). `confirm` fue removido del backend
// (spec-015, Bloque 3): el mecanismo real de confirmación humana es `Chat.permission_mode` +
// `ToolRun`, ajeno a este tipo.
export interface ProjectTool {
  id: string;
  caseId: string;
  toolKey: string;
  enabled: boolean;
  allowedActionIds: string[];
  createdAt: string;
}

// Vista fusionada de una tool para un caso puntual (spec-013, Task 16/19; tab "Herramientas"
// de ProjectRoute, ver mockup). Una entrada por cada `ToolCatalogEntry.installed=true` del
// catálogo global -- el modelo es default-on: `projectTool === null` significa "elegible por
// default, sin override", NUNCA "no disponible". `eligible` es el resultado ya resuelto por
// el backend (`app.services.tool_eligibility`, nunca recalculado acá).
export interface CaseTool {
  toolKey: string;
  label: string;
  description: string;
  eligible: boolean;
  projectTool: ProjectTool | null;
}

// Archivo adjunto a un proyecto (tab "Fuentes" de ProjectRoute, ver mockup). En el backend real
// esto es `CaseFile` (tarea 3a-3b del plan): se ingesta en Chroma taggeado con `case_id` real,
// buscable junto con la normativa general vía `search_evidence`.
export interface CaseFile {
  id: string;
  name: string;
  sizeLabel: string;
}

export interface Project {
  id: string;
  name: string;
  status: string;
  context: string | null;
  updatedAt: string;
}

export interface ChatSummary {
  id: string;
  caseId: string | null;
  title: string | null;
  archived: boolean;
  updatedAt: string;
}

export type MessageRole = "user" | "assistant" | "tool";

export interface ChatMessage {
  id: string;
  chatId: string;
  role: MessageRole;
  content: string | null;
  toolName: string | null;
  toolInput: Record<string, unknown> | null;
  toolOutput: Record<string, unknown> | null;
  reportId: string | null;
  createdAt: string;
}

export type ReportStatus = "pending_review" | "published" | "rejected";

export interface ReportSection {
  heading: string;
  body: string;
}

export interface Report {
  id: string;
  caseId: string;
  title: string;
  status: ReportStatus;
  updatedAt: string;
  sections: ReportSection[];
}
