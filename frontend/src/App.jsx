import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate, useParams, Outlet } from 'react-router-dom';
import { useEffect } from 'react';
import UploadPage      from './components/Upload/UploadPage';
import ConfigurePage   from './components/Configure/ConfigurePage';
import GeneratePage    from './components/Generate/GeneratePage';
import ChatPage        from './components/Chat/ChatPage';
import PrintView       from './components/Print/PrintView';
import ProjectListPage from './components/Projects/ProjectListPage';
import useProjectStore from './store/projectStore';
import { getProject } from './services/api';
import './styles/globals.css';

const PROJECT_STEPS = [
  { pathKey: 'upload',    icon: '📂', label: 'Upload Data',  sub: 'CSV / Excel + RFP',        minStatus: null },
  { pathKey: 'configure', icon: '⚙️',  label: 'Configure',   sub: 'Objectives & tone',         minStatus: 'uploaded' },
  { pathKey: 'generate',  icon: '✨',  label: 'Generate',    sub: 'AI builds your slides',     minStatus: 'configured' },
  { pathKey: 'chat',      icon: '💬',  label: 'Chat',        sub: 'Refine conversationally',   minStatus: 'ready' },
];

const STATUS_ORDER = ['uploading', 'uploaded', 'configured', 'generating', 'ready'];

function ProjectSidebar() {
  const { projectId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { status } = useProjectStore();

  const currentStatusIdx = STATUS_ORDER.indexOf(status ?? 'uploading');

  return (
    <aside className="sidebar">
      <button
        className="sidebar-step"
        onClick={() => navigate('/projects')}
      >
        <span className="step-icon">←</span>
        <span className="step-info">
          <span className="step-label">Back to Projects</span>
          <span className="step-sub">All presentations</span>
        </span>
      </button>

      <div className="sidebar-divider" />

      {PROJECT_STEPS.map((step) => {
        const path = `/projects/${projectId}/${step.pathKey}`;
        const isActive = location.pathname === path;
        const minIdx   = step.minStatus ? STATUS_ORDER.indexOf(step.minStatus) : 0;
        const isDone   = currentStatusIdx > minIdx;
        const canClick = currentStatusIdx >= minIdx || step.minStatus === null;

        return (
          <button
            key={step.pathKey}
            className={`sidebar-step ${isActive ? 'active' : ''} ${isDone && !isActive ? 'done' : ''}`}
            onClick={() => canClick && navigate(path)}
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

function ProjectShell() {
  const { projectId } = useParams();
  const { projectId: storeId, setProject } = useProjectStore();

  useEffect(() => {
    if (!projectId) return;
    if (storeId === projectId) return;
    getProject(projectId)
      .then(({ data }) => setProject(data.id, data.status))
      .catch(() => {});
  }, [projectId, storeId, setProject]);

  return (
    <div className="app-shell">
      <Header />
      <ProjectSidebar />
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}

function ListLayout() {
  return (
    <div className="app-shell app-shell--no-sidebar">
      <Header />
      <main className="main-content">
        <ProjectListPage />
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/print/:projectId" element={<PrintView />} />
        <Route path="/"          element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<ListLayout />} />
        <Route path="/projects/:projectId" element={<ProjectShell />}>
          <Route index element={<Navigate to="upload" replace />} />
          <Route path="upload"    element={<UploadPage />} />
          <Route path="configure" element={<ConfigurePage />} />
          <Route path="generate" element={<GeneratePage />} />
          <Route path="chat"     element={<ChatPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
