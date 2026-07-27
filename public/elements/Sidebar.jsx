// Sidebar de proyectos + herramientas (spec-014/spec-017). Estilo inline/CSS propio (no
// Tailwind): el sandbox de Custom Elements de Chainlit no corre el JIT de Tailwind sobre
// public/elements/, así que clases utilitarias sin una hoja generada no aplican -- ver el
// spike descartado (_Spike.jsx) donde bg-blue-600 etc. no tuvieron efecto. Paleta pensada
// para calzar con el tema oscuro default de Chainlit (acento rosa/rose, fondos casi negros).
export default function Sidebar() {
  const projects = props.projects || [];
  const tools = props.tools || [];
  const activeCaseId = props.activeCaseId;

  const newProject = async () => {
    await callAction({ name: "new_project", payload: {} });
  };

  const switchProject = async (caseId) => {
    if (caseId === activeCaseId) return;
    await callAction({ name: "switch_project", payload: { case_id: caseId } });
  };

  const runTool = async (toolName) => {
    await callAction({ name: "invoke_tool_explicit", payload: { tool_name: toolName } });
  };

  return (
    <div className="arw-sb">
      <style>{`
        .arw-sb { display: flex; flex-direction: column; gap: 22px; padding: 4px 2px 12px; font-size: 13px; }
        .arw-sb-section-title { font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: #8a8a94; margin: 0 0 8px 2px; }
        .arw-sb-new-btn { display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 10px; border-radius: 8px; border: 1px solid #33333a; background: transparent; color: #e6e6ea; font-size: 13px; cursor: pointer; transition: background .15s, border-color .15s; text-align: left; }
        .arw-sb-new-btn:hover { background: #1c1c22; border-color: #45454e; }
        .arw-sb-plus { color: #fb7185; font-weight: 700; font-size: 15px; line-height: 1; }
        .arw-sb-list { display: flex; flex-direction: column; gap: 2px; }
        .arw-sb-item { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; padding: 7px 10px; border-radius: 8px; cursor: pointer; border-left: 2px solid transparent; transition: background .15s; }
        .arw-sb-item:hover { background: #1a1a1f; }
        .arw-sb-item.active { background: #20161a; border-left-color: #fb7185; }
        .arw-sb-item-name { color: #e6e6ea; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .arw-sb-item.active .arw-sb-item-name { color: #fda4af; font-weight: 600; }
        .arw-sb-item-meta { color: #7a7a84; font-size: 10px; flex-shrink: 0; text-transform: uppercase; letter-spacing: .04em; }
        .arw-sb-empty { color: #7a7a84; font-size: 12px; padding: 4px 2px; }
        .arw-sb-tool { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; padding: 8px 10px; border-radius: 8px; }
        .arw-sb-tool:hover { background: #1a1a1f; }
        .arw-sb-tool-name { color: #e6e6ea; font-size: 13px; font-weight: 500; }
        .arw-sb-tool-desc { color: #7a7a84; font-size: 11px; margin-top: 2px; line-height: 1.35; }
        .arw-sb-run-btn { flex-shrink: 0; padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(251,113,133,.4); background: rgba(251,113,133,.1); color: #fb7185; font-size: 11px; font-weight: 600; cursor: pointer; white-space: nowrap; }
        .arw-sb-run-btn:hover { background: rgba(251,113,133,.2); }
        .arw-sb-chat-only { flex-shrink: 0; padding: 4px 8px; border-radius: 6px; color: #5c5c64; font-size: 10px; border: 1px solid #33333a; white-space: nowrap; }
      `}</style>

      <div>
        <div className="arw-sb-section-title">Proyectos</div>
        <button className="arw-sb-new-btn" onClick={newProject}>
          <span className="arw-sb-plus">+</span> Nuevo proyecto
        </button>
        <div className="arw-sb-list" style={{ marginTop: 8 }}>
          {projects.length === 0 && (
            <div className="arw-sb-empty">Todavía no hay proyectos.</div>
          )}
          {projects.map((p) => (
            <div
              key={p.id}
              className={`arw-sb-item${p.id === activeCaseId ? " active" : ""}`}
              onClick={() => switchProject(p.id)}
              title={p.name}
            >
              <span className="arw-sb-item-name">{p.name}</span>
              <span className="arw-sb-item-meta">{p.status}</span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="arw-sb-section-title">Herramientas</div>
        <div className="arw-sb-list">
          {tools.map((t) => (
            <div key={t.name} className="arw-sb-tool">
              <div>
                <div className="arw-sb-tool-name">{t.label}</div>
                <div className="arw-sb-tool-desc">{t.description}</div>
              </div>
              {t.runnable ? (
                <button className="arw-sb-run-btn" onClick={() => runTool(t.name)}>
                  Ejecutar
                </button>
              ) : (
                <span className="arw-sb-chat-only">Solo chat</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
