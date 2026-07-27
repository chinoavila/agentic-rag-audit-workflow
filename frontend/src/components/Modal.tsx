import type { ReactNode } from "react";

interface ModalProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer: ReactNode;
}

// Wrapper genérico (mismo look que el mockup: overlay oscuro + panel centrado con head/body
// scrolleable/foot). `ToolModal` (alta/edición de herramientas) y el futuro modal de
// crear/editar proyecto lo reusan en vez de reimplementar el overlay cada vez.
export function Modal({ title, onClose, children, footer }: ModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-6"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="flex max-h-[84vh] w-full max-w-[620px] flex-col overflow-hidden rounded-lg border border-border bg-bg-raised shadow-xl">
        <div className="flex flex-shrink-0 items-center gap-2.5 border-b border-border px-4.5 py-4">
          <div className="flex-1 text-[15px] font-semibold">{title}</div>
          <button
            className="flex h-8 w-8 items-center justify-center rounded-sm text-text-dim hover:bg-bg-sunken hover:text-text"
            onClick={onClose}
            aria-label="Cerrar"
          >
            ✕
          </button>
        </div>
        <div className="scrollbar-thin flex-1 overflow-y-auto p-5">{children}</div>
        <div className="flex flex-shrink-0 justify-end gap-2 border-t border-border px-4.5 py-3.5">{footer}</div>
      </div>
    </div>
  );
}
