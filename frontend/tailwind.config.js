/**
 * Tokens portados 1:1 del mockup validado (sidebar-mockup.html, publicado como Artifact):
 * paleta "libro de auditoría" (tinta azul-negra profunda, no negro puro, + acento latón/sello
 * oficial), semántica (pending/ok/critical) separada del acento. `darkMode: "media"` porque el
 * mockup siempre siguió `prefers-color-scheme` -- swap a "class" el día que se agregue un
 * toggle manual de tema.
 */
export default {
  darkMode: "media",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--color-bg)",
        "bg-raised": "var(--color-bg-raised)",
        "bg-sunken": "var(--color-bg-sunken)",
        text: "var(--color-text)",
        "text-dim": "var(--color-text-dim)",
        "text-faint": "var(--color-text-faint)",
        border: "var(--color-border)",
        "sidebar-bg": "var(--color-sidebar-bg)",
        "sidebar-border": "var(--color-sidebar-border)",
        accent: "var(--color-accent)",
        "accent-tint": "var(--color-accent-tint)",
        "accent-tint-strong": "var(--color-accent-tint-strong)",
        verdigris: "#2f7a6d",
        "verdigris-tint": "rgba(47, 122, 109, .14)",
        flag: "#b0432f",
        "flag-tint": "rgba(176, 67, 47, .13)",
        pending: "#4c62a8",
        "pending-tint": "rgba(76, 98, 168, .13)",
      },
      fontFamily: {
        ui: [
          "-apple-system",
          "Segoe UI",
          "Inter",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SF Mono", "Cascadia Code", "Consolas", "monospace"],
      },
      borderRadius: {
        sm: "6px",
        DEFAULT: "10px",
        lg: "16px",
      },
      // El default de Tailwind solo tiene pasos de .5 hasta 3.5 (0, 0.5, 1, 1.5, ..., 3, 3.5) y
      // de a 1 entero después -- las clases que usan 4.5/5.5/6.5/7.5/8.5/13 (gap-4.5, h-6.5,
      // px-4.5, h-13, etc., portadas del mockup) no existen en esa escala y Tailwind las
      // generaba vacías (sin ninguna regla CSS), por eso los paddings/gaps/tamaños se veían
      // colapsados. Se agregan como claves explícitas siguiendo el mismo múltiplo (n * 0.25rem)
      // que usa el resto de la escala, en vez de reescribir cada className a `[…px]`.
      spacing: {
        "4.5": "1.125rem",
        "5.5": "1.375rem",
        "6.5": "1.625rem",
        "7.5": "1.875rem",
        "8.5": "2.125rem",
        "13": "3.25rem",
      },
    },
  },
  plugins: [],
};
