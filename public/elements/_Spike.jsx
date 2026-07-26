// Spike descartable (Fase 0 del plan de sidebar): confirma que cl.CustomElement +
// cl.ElementSidebar renderizan y que callAction hace round-trip a un @cl.action_callback
// en esta version pinneada de Chainlit (ver Chainlit/chainlit#1827). Se borra en cuanto
// se confirme o se decida el fallback -- no es parte del feature final.
export default function Spike() {
  const ping = async () => {
    await callAction({ name: "spike_ping", payload: { from: "ToolPanelSpike" } });
  };

  return (
    <div className="p-4 space-y-2">
      <div className="text-sm font-medium">Sidebar spike</div>
      <button
        className="px-3 py-1 rounded bg-blue-600 text-white text-sm"
        onClick={ping}
      >
        Probar callAction
      </button>
    </div>
  );
}
