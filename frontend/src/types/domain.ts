// Tipos del dominio (espejo de app/schemas/*.py). Mientras no está wireado el backend real
// (tareas 2b/3c/4b del plan), estos tipos son también la forma que devuelve `src/data/mock.ts`
// -- migrar de mock a `apiFetch` real no debería requerir tocar los componentes, solo el
// `queryFn` de cada `useQuery` (ver src/lib/api.ts).

export type ToolKind = "ro" | "write";

export interface ToolAction {
  id: string;
  label: string;
  command: string;
}

export interface ToolCatalogEntry {
  key: string;
  label: string;
  description: string;
  kind: ToolKind;
  installed: boolean;
  actions: ToolAction[];
}

export interface ToolCatalogEntryDraft {
  label: string;
  key: string;
  description: string;
  kind: ToolKind;
  actions: ToolAction[];
}

// Una herramienta agregada a un proyecto puntual (tab "Herramientas" de ProjectRoute, ver
// mockup): `allowedActionIds` es un subconjunto de las `actions` de su `ToolCatalogEntry` --
// permite restringir qué puede hacer la tool en ESTE proyecto sin afectar a otros.
export interface ToolInstance {
  key: string;
  enabled: boolean;
  confirm: boolean;
  allowedActionIds: string[];
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
