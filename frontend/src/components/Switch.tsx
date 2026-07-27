export function Switch({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      onClick={onClick}
      className={`relative h-[19px] w-[34px] flex-shrink-0 rounded-full border transition-colors ${
        on ? "border-accent bg-accent-tint-strong" : "border-border bg-bg-sunken"
      }`}
    >
      <span
        className={`absolute left-[1px] top-[1px] h-[15px] w-[15px] rounded-full transition-transform ${
          on ? "translate-x-[15px] bg-accent" : "bg-text-faint"
        }`}
      />
    </button>
  );
}
