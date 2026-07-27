import type { ReportStatus } from "@/types/domain";

const STATUS_META: Record<ReportStatus, { label: string; className: string }> = {
  pending_review: { label: "Pendiente de revisión", className: "bg-pending-tint text-pending" },
  published: { label: "Publicado", className: "bg-verdigris-tint text-verdigris" },
  rejected: { label: "Rechazado", className: "bg-flag-tint text-flag" },
};

export function StatusPill({ status }: { status: ReportStatus }) {
  const meta = STATUS_META[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10.5px] font-bold uppercase tracking-wide ${meta.className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {meta.label}
    </span>
  );
}
