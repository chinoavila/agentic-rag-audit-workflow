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
    },
  },
  plugins: [],
};
