import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import UploadPage    from './components/Upload/UploadPage';
import ConfigurePage from './components/Configure/ConfigurePage';
import GeneratePage  from './components/Generate/GeneratePage';
import ChatPage      from './components/Chat/ChatPage';
import useProjectStore from './store/projectStore';
import './styles/globals.css';

const STEPS = [
  { path: '/upload',    icon: '📂', label: 'Upload Data',  sub: 'CSV / Excel + RFP',        minStatus: null },
  { path: '/configure', icon: '⚙️',  label: 'Configure',   sub: 'Objectives & tone',         minStatus: 'uploaded' },
  { path: '/generate',  icon: '✨',  label: 'Generate',    sub: 'AI builds your slides',     minStatus: 'configured' },
  { path: '/chat',      icon: '💬',  label: 'Chat',        sub: 'Refine conversationally',   minStatus: 'ready' },
];

const STATUS_ORDER = ['uploading', 'uploaded', 'configured', 'generating', 'ready'];

function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { status } = useProjectStore();

  const currentStatusIdx = STATUS_ORDER.indexOf(status ?? 'uploading');

  return (
    <aside className="sidebar">
      {STEPS.map((step) => {
        const isActive = location.pathname === step.path;
        const minIdx   = step.minStatus ? STATUS_ORDER.indexOf(step.minStatus) : 0;
        const isDone   = currentStatusIdx > minIdx;
        const canClick = currentStatusIdx >= minIdx;

        return (
          <button
            key={step.path}
            className={`sidebar-step ${isActive ? 'active' : ''} ${isDone && !isActive ? 'done' : ''}`}
            onClick={() => canClick && navigate(step.path)}
            style={{ cursor: canClick ? 'pointer' : 'default', opacity: canClick ? 1 : 0.4 }}
          >
            <span className="step-icon">{isDone && !isActive ? '✓' : step.icon}</span>
            <span className="step-info">
              <span className="step-label">{step.label}</span>
              <span className="step-sub">{step.sub}</span>
            </span>
          </button>
        );
      })}

      <div className="sidebar-divider" />

      <div style={{ padding: '8px 12px' }}>
        <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', lineHeight: 1.6 }}>
          Powered by Gemini 2.5 Flash<br />& python-pptx
        </p>
      </div>
    </aside>
  );
}

function Header() {
  const { status } = useProjectStore();
  const pillMap = {
    ready:      { cls: 'pill-ready',      label: 'Ready' },
    generating: { cls: 'pill-generating', label: 'Generating…' },
    configured: { cls: 'pill-configured', label: 'Configured' },
    error:      { cls: 'pill-error',      label: 'Error' },
  };
  const pill = pillMap[status];

  return (
    <header className="app-header">
      <div className="brand">
        <div className="brand-icon">📊</div>
        <span className="brand-text">PPT<span> Genius</span></span>
      </div>
      {pill && <span className={`status-pill ${pill.cls}`}>{pill.label}</span>}
      <span className="header-tag">AI Presentation Builder</span>
    </header>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <Header />
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/"         element={<Navigate to="/upload" replace />} />
            <Route path="/upload"    element={<UploadPage />} />
            <Route path="/configure" element={<ConfigurePage />} />
            <Route path="/generate"  element={<GeneratePage />} />
            <Route path="/chat"      element={<ChatPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
