import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

// Estado del panel derecho tipo "Artifact" (preview/export de informes, ver plan spec-020 /
// mockup). Vive en Context (no en la URL) a propósito: como en Claude, el panel persiste
// abierto aunque se navegue de chat a chat -- si viviera en la URL, cambiar de ruta lo cerraría.
interface RightPanelState {
  open: boolean;
  reportId: string | null;
  openReport: (reportId: string) => void;
  close: () => void;
}

const RightPanelContext = createContext<RightPanelState | null>(null);

export function RightPanelProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [reportId, setReportId] = useState<string | null>(null);

  const value = useMemo<RightPanelState>(
    () => ({
      open,
      reportId,
      openReport: (id: string) => {
        setReportId(id);
        setOpen(true);
      },
      close: () => setOpen(false),
    }),
    [open, reportId],
  );

  return <RightPanelContext.Provider value={value}>{children}</RightPanelContext.Provider>;
}

export function useRightPanel(): RightPanelState {
  const ctx = useContext(RightPanelContext);
  if (!ctx) throw new Error("useRightPanel debe usarse dentro de RightPanelProvider");
  return ctx;
}
