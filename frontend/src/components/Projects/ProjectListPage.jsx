import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import useProjectStore from '../../store/projectStore';
import { listProjects, downloadPresentation } from '../../services/api';

const STATUS_DEST = {
  ready:      '/generate',
  configured: '/generate',
  uploaded:   '/configure',
};

const PILL_MAP = {
  ready:      { cls: 'pill-ready',      label: 'Ready' },
  generating: { cls: 'pill-generating', label: 'Generating…' },
  configured: { cls: 'pill-configured', label: 'Configured' },
  uploaded:   { cls: 'pill-configured', label: 'Uploaded' },
  error:      { cls: 'pill-error',      label: 'Error' },
  uploading:  { cls: '',                label: 'New' },
};

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

export default function ProjectListPage() {
  const navigate = useNavigate();
  const store = useProjectStore();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');

  useEffect(() => {
    listProjects()
      .then(({ data }) => setProjects(data))
      .catch(() => setError('Failed to load projects.'))
      .finally(() => setLoading(false));
  }, []);

  const openProject = (project) => {
    store.reset();
    store.setProject(project.id, project.status);
    navigate(STATUS_DEST[project.status] || '/upload');
  };

  const newProject = () => {
    store.reset();
    navigate('/upload');
  };

  return (
    <div className="fade-in">
      <div className="page-header" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div className="page-title">Projects</div>
          <div className="page-sub">All your past and in-progress presentations.</div>
        </div>
        <button className="btn btn-primary" onClick={newProject}>+ New Project</button>
      </div>

      {error && <div className="banner banner-error"><span className="banner-icon">⚠️</span>{error}</div>}

      {loading ? (
        <div className="text-muted" style={{ marginTop: 32, textAlign: 'center' }}>Loading projects…</div>
      ) : projects.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>📂</div>
          <h3 style={{ marginBottom: 8 }}>No projects yet</h3>
          <p className="text-muted" style={{ marginBottom: 20 }}>Upload a dataset to create your first AI-generated presentation.</p>
          <button className="btn btn-primary" onClick={newProject}>+ New Project</button>
        </div>
      ) : (
        <div className="project-list">
          {projects.map((p) => {
            const pill = PILL_MAP[p.status] || { cls: '', label: p.status };
            const title = p.title || 'Untitled Project';
            return (
              <div key={p.id} className="project-row card">
                <div className="project-row-info">
                  <div className="project-row-title">{title}</div>
                  <div className="project-row-meta">
                    <span className={`status-pill ${pill.cls}`}>{pill.label}</span>
                    <span className="text-muted" style={{ fontSize: 12 }}>{formatDate(p.created_at)}</span>
                  </div>
                </div>
                <div className="project-row-actions">
                  {p.pptx_url && (
                    <a
                      href={downloadPresentation(p.id)}
                      download
                      className="btn btn-secondary"
                      onClick={(e) => e.stopPropagation()}
                    >
                      ⬇ .pptx
                    </a>
                  )}
                  <button className="btn btn-primary" onClick={() => openProject(p)}>
                    Open →
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
