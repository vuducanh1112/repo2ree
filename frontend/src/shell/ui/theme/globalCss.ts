export const GLOBAL_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
  @keyframes spin    { to { transform: rotate(360deg); } }
  @keyframes fadeUp  { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
  @keyframes slideIn { from { opacity:0; transform:translateX(10px); } to { opacity:1; transform:translateX(0); } }
  @keyframes pulseGlow { 0%,100% { box-shadow: 0 0 0 0 currentColor; } 50% { box-shadow: 0 0 0 4px transparent; } }
  @keyframes busFlow { to { background-position-x: 8px; } }
  @keyframes cableFlow { to { stroke-dashoffset: -20; } }
  @keyframes dockIn { from { opacity:0; transform:translateX(26px) scale(.985); } to { opacity:1; transform:none; } }
  @keyframes growIn { from { opacity:0; transform:scale(.05); } to { opacity:1; transform:scale(1); } }
  @keyframes labDriftA { 0%,100% { transform:translate(0,0); opacity:.65; } 50% { transform:translate(26px,-18px); opacity:1; } }
  @keyframes labDriftB { 0%,100% { transform:translate(0,0); opacity:.5; } 50% { transform:translate(-22px,16px); opacity:.85; } }
  @keyframes labScan { 0% { transform:translateY(-30%); opacity:0; } 40% { opacity:.7; } 100% { transform:translateY(140%); opacity:0; } }
  @keyframes cradlePulse { 0%,100% { opacity:.45; transform:translate(-50%,-50%) scale(1); } 50% { opacity:.8; transform:translate(-50%,-50%) scale(1.04); } }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { font-family: Inter, system-ui, sans-serif; background: #f4f6f9; }
  ::-webkit-scrollbar { width:4px; height:4px; }
  ::-webkit-scrollbar-track { background:transparent; }
  ::-webkit-scrollbar-thumb { background:#c4cdd9; border-radius:99px; }
  ::-webkit-scrollbar-thumb:hover { background:#8896a5; }
  input, select, button, textarea { font-family:inherit; outline:none; }
  input:focus, select:focus, textarea:focus { border-color:#2563eb !important; box-shadow:0 0 0 3px #2563eb18 !important; }
  :where(button, [role="button"], a, input, select, textarea):focus-visible {
    outline: 2px solid #2563eb;
    outline-offset: 2px;
  }
  :where(button, [role="button"], a, input, select, textarea):focus:not(:focus-visible) {
    outline: none;
  }
  :where(button, [role="button"]):not(:disabled) { transition: transform 0.12s ease, filter 0.12s ease; }
  :where(button, [role="button"]):not(:disabled):hover { transform: translateY(-1px); filter: brightness(0.95); }
  :where(button, [role="button"]):not(:disabled):active { transform: translateY(1px); }
  .nav-item { transition: background 0.12s, color 0.12s; }
`;
