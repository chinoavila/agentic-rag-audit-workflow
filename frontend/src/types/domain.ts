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

// Una herramienta agregada a un proyecto puntual (tab "Herramientas" de ProjectRoute, ver
// mockup): `allowedActionIds` es un subconjunto de las `actions` de su `ToolCatalogEntry` --
// permite restringir qué puede hacer la tool en ESTE proyecto sin afectar a otros.
export interface ToolInstance {
  key: string;
  enabled: boolean;
  confirm: boolean;
  allowedActionIds: string[];
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
