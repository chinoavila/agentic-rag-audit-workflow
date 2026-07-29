import type { PermissionMode } from "@/types/domain";

// Selector único de `Chat.permission_mode` (spec-015) en el header de `ChatRoute.tsx` -- no un
// control por tool. Componente controlado puro: `ChatRoute.tsx` es dueño del `PATCH
// /api/chats/{id}` real (optimista, revierte si falla) y de qué valor mostrar mientras el chat
// todavía no existe (nuevo chat sin crear -- ver `ChatRoute.tsx`, default "manual").
const OPTIONS: { value: PermissionMode; label: string; hint: string }[] = [
  { value: "auto", label: "Auto", hint: "Ejecuta sin pedir aprobación (solo turnos humanos explícitos)" },
  { value: "accept_edit", label: "Aceptar y editar", hint: "Revisá/editá el comando antes de correrlo" },
  { value: "manual", label: "Manual", hint: "El agente nunca ejecuta, solo te muestra el comando" },
];

export function PermissionModeSelector({
  value,
  onChange,
  disabled = false,
}: {
  value: PermissionMode;
  onChange: (mode: PermissionMode) => void;
  disabled?: boolean;
}) {
  return (
    <div
      role="radiogroup"
      aria-label="Modo de ejecución de comandos"
      className="flex items-center gap-0.5 rounded-full border border-border bg-bg-sunken p-0.5"
    >
      {OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          role="radio"
          aria-checked={value === opt.value}
          title={opt.hint}
          disabled={disabled}
          onClick={() => opt.value !== value && onChange(opt.value)}
          className={`rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
            value === opt.value
              ? "bg-accent text-[#1c1508]"
              : "text-text-dim hover:bg-bg-raised hover:text-text"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
