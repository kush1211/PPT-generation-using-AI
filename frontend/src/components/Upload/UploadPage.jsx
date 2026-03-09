import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import useProjectStore from '../../store/projectStore';
import { uploadData, uploadDocument } from '../../services/api';

function DropZone({ label, accept, acceptLabel, icon, file, onFile, optional }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef();

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) onFile(f);
  };

  return (
    <div
      className={`drop-zone ${dragging ? 'drag-over' : ''} ${file ? 'has-file' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current.click()}
    >
      <input ref={inputRef} type="file" accept={accept}
        onChange={(e) => e.target.files[0] && onFile(e.target.files[0])} />

      <span className="drop-icon">{file ? '✅' : icon}</span>
      <div className="drop-title">{label}{optional && <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--text-muted)', marginLeft: 6 }}>(optional)</span>}</div>

      {file ? (
        <div className="drop-file-name">📎 {file.name}</div>
      ) : (
        <>
          <div className="drop-sub">Drag & drop or click to browse</div>
          <div className="drop-accept">{acceptLabel}</div>
        </>
      )}
    </div>
  );
}

export default function UploadPage() {
  const navigate = useNavigate();
  const store = useProjectStore();
  const projectId = store.projectId;

  const [dataFile, setDataFile] = useState(null);
  const [docFile,  setDocFile]  = useState(null);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState('');
  const [profile,  setProfile]  = useState(null);
  const [columnMap, setColumnMap] = useState(null);

  useEffect(() => {
    if (!projectId) navigate('/projects');
  }, [projectId, navigate]);

  const handleUpload = async () => {
    if (!projectId) return navigate('/projects');
    if (!dataFile) return setError('Please select a data file (CSV or Excel).');
    setError('');
    setLoading(true);
    try {
      const { data: result } = await uploadData(projectId, dataFile);
      store.setProfile(result.profile, result.column_map);
      setProfile(result.profile);
      setColumnMap(result.column_map);

      if (docFile) await uploadDocument(projectId, docFile);

      store.setStatus('uploaded');
    } catch (e) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <div className="page-title">Upload Your Data</div>
        <div className="page-sub">Add your market research spreadsheet and an optional RFP document to get started.</div>
      </div>

      {error && (
        <div className="banner banner-error">
          <span className="banner-icon">⚠️</span>
          {error}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
        <DropZone
          label="Data File"
          accept=".csv,.xlsx,.xls"
          acceptLabel="Supports .csv, .xlsx, .xls"
          icon="📊"
          file={dataFile}
          onFile={setDataFile}
        />
        <DropZone
          label="RFP / Brief"
          accept=".pdf,.docx,.txt"
          acceptLabel="Supports .pdf, .docx, .txt"
          icon="📄"
          file={docFile}
          onFile={setDocFile}
          optional
        />
      </div>

      <button className="btn btn-primary btn-lg" onClick={handleUpload} disabled={loading || !dataFile}>
        {loading ? <><span className="spinner" /> Uploading & Profiling…</> : '🚀 Upload & Analyse Data'}
      </button>

      {profile && columnMap && (
        <div className="fade-in" style={{ marginTop: 32 }}>
          <div className="card" style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
              <div>
                <h3>Data Profile</h3>
                <p className="text-muted" style={{ marginTop: 4 }}>
                  {profile.shape?.[0]} rows × {profile.shape?.[1]} columns detected
                </p>
              </div>
              <span className="status-pill pill-ready">✓ Profiled</span>
            </div>

            <div style={{ marginBottom: 20 }}>
              <div className="form-label" style={{ marginBottom: 10 }}>Column Types</div>
              <div className="tag-list">
                {columnMap.metrics?.map(c    => <span key={c} className="badge badge-metric">📈 {c}</span>)}
                {columnMap.dimensions?.map(c => <span key={c} className="badge badge-dimension">🏷 {c}</span>)}
                {columnMap.dates?.map(c      => <span key={c} className="badge badge-date">📅 {c}</span>)}
              </div>
              <div className="form-hint" style={{ marginTop: 10 }}>
                <strong>Blue</strong> = metrics (numeric KPIs) &nbsp;·&nbsp;
                <strong>Yellow</strong> = dimensions (categories) &nbsp;·&nbsp;
                <strong>Green</strong> = date/time columns
              </div>
            </div>

            {profile.sample_rows?.length > 0 && (
              <>
                <div className="form-label" style={{ marginBottom: 10 }}>Sample Data (first 5 rows)</div>
                <div className="data-table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>{Object.keys(profile.sample_rows[0]).map(k => <th key={k}>{k}</th>)}</tr>
                    </thead>
                    <tbody>
                      {profile.sample_rows.map((row, i) => (
                        <tr key={i}>
                          {Object.values(row).map((v, j) => <td key={j}>{v == null ? '—' : String(v)}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>

          <button className="btn btn-accent btn-lg" onClick={() => navigate(`/projects/${store.projectId}/configure`)}>
            Continue to Configure →
          </button>
        </div>
      )}
    </div>
  );
}
