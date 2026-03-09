import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import useProjectStore from '../../store/projectStore';
import { listProjects, createProject, deleteProject, downloadPresentation } from '../../services/api';

const STATUS_STEP = {
  ready:      'generate',
  configured: 'generate',
  generating: 'generate',
  uploaded:   'configure',
  error:      'generate',
};
const DEFAULT_STEP = 'upload';

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  const loadProjects = () => {
    setLoading(true);
    listProjects()
      .then(({ data }) => setProjects(data))
      .catch(() => setError('Failed to load projects.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const openProject = (project) => {
    store.reset();
    store.setProject(project.id, project.status);
    const step = STATUS_STEP[project.status] || DEFAULT_STEP;
    navigate(`/projects/${project.id}/${step}`);
  };

  const handleCreateProject = async (e) => {
    e.preventDefault();
    const name = newName.trim() || 'Untitled Project';
    setCreating(true);
    setError('');
    try {
      const { data } = await createProject(name);
      store.reset();
      store.setProject(data.id, data.status);
      setModalOpen(false);
      setNewName('');
      navigate(`/projects/${data.id}/upload`);
    } catch (e) {
      setError(e.response?.data?.error || e.message || 'Failed to create project.');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (e, projectId) => {
    e.stopPropagation();
    if (!window.confirm('Delete this project? This cannot be undone.')) return;
    setDeletingId(projectId);
    try {
      await deleteProject(projectId);
      setProjects((prev) => prev.filter((p) => p.id !== projectId));
    } catch {
      setError('Failed to delete project.');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="fade-in">
      <div className="page-header" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div className="page-title">Projects</div>
          <div className="page-sub">All your past and in-progress presentations.</div>
        </div>
        <button className="btn btn-primary" onClick={() => setModalOpen(true)}>+ New Project</button>
      </div>

      {error && <div className="banner banner-error"><span className="banner-icon">⚠️</span>{error}</div>}

      {loading ? (
        <div className="text-muted" style={{ marginTop: 32, textAlign: 'center' }}>Loading projects…</div>
      ) : projects.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>📂</div>
          <h3 style={{ marginBottom: 8 }}>No projects yet</h3>
          <p className="text-muted" style={{ marginBottom: 20 }}>Create a project and upload a dataset to build your first AI-generated presentation.</p>
          <button className="btn btn-primary" onClick={() => setModalOpen(true)}>+ New Project</button>
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
                  <button
                    className="btn btn-outline btn-danger"
                    onClick={(e) => handleDelete(e, p.id)}
                    disabled={deletingId === p.id}
                    title="Delete project"
                  >
                    {deletingId === p.id ? '…' : '🗑 Delete'}
                  </button>
                  <button className="btn btn-primary" onClick={() => openProject(p)}>
                    Open →
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {modalOpen && (
        <div className="modal-overlay" onClick={() => !creating && setModalOpen(false)}>
          <div className="modal card" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: 8 }}>New Project</h3>
            <p className="text-muted" style={{ marginBottom: 16, fontSize: 14 }}>Give your project a name. You can upload data in the next step.</p>
            <form onSubmit={handleCreateProject}>
              <label className="form-label">Project name</label>
              <input
                className="input"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Q3 Competitor Analysis"
                autoFocus
                style={{ marginBottom: 20 }}
              />
              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-secondary" onClick={() => !creating && setModalOpen(false)} disabled={creating}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={creating}>
                  {creating ? <><span className="spinner" /> Creating…</> : 'Create & Open'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
