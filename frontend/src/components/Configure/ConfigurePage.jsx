import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import useProjectStore from '../../store/projectStore';
import { inferObjectives, updateObjectives } from '../../services/api';

const AUDIENCE = ['executive', 'analyst', 'client'];
const TONE     = ['formal', 'consultative', 'technical'];

function TagInput({ label, hint, values, onChange, placeholder }) {
  const [input, setInput] = useState('');

  const add = () => {
    const v = input.trim();
    if (v && !values.includes(v)) onChange([...values, v]);
    setInput('');
  };

  return (
    <div className="form-group">
      <label className="form-label">{label}</label>
      {values.length > 0 && (
        <div className="tag-list" style={{ marginBottom: 10 }}>
          {values.map(t => (
            <span key={t} className="tag">
              {t}
              <button className="tag-remove" onClick={() => onChange(values.filter(x => x !== t))}>×</button>
            </span>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', gap: 8 }}>
        <input className="input" value={input} placeholder={placeholder}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && add()} />
        <button className="btn btn-outline btn-sm" onClick={add} style={{ flexShrink: 0 }}>+ Add</button>
      </div>
      {hint && <div className="form-hint">{hint}</div>}
    </div>
  );
}

export default function ConfigurePage() {
  const navigate = useNavigate();
  const { projectId, setObjectives, setStatus } = useProjectStore();

  const [inferring, setInferring] = useState(false);
  const [saving,    setSaving]    = useState(false);
  const [error,     setError]     = useState('');
  const [saved,     setSaved]     = useState(false);
  const [brief,     setBrief]     = useState(null);  // BriefDecomposition fields
  const [form, setForm] = useState({
    presentation_title: '',
    audience: 'executive',
    tone: 'consultative',
    primary_objectives: [],
    key_metrics: [],
    comparison_dimensions: [],
  });

  useEffect(() => { if (!projectId) navigate('/projects'); }, [projectId, navigate]);

  const set = (key, val) => setForm(f => ({ ...f, [key]: val }));

  const handleInfer = async () => {
    setInferring(true); setError('');
    try {
      const { data } = await inferObjectives(projectId);
      setForm({
        presentation_title:   data.presentation_title   || '',
        audience:             data.audience             || 'executive',
        tone:                 data.tone                 || 'consultative',
        primary_objectives:   data.primary_objectives   || [],
        key_metrics:          data.key_metrics          || [],
        comparison_dimensions:data.comparison_dimensions|| [],
      });
      // Store the new brief decomposition fields (if returned by new pipeline)
      if (data.brief) setBrief(data.brief);
      setObjectives(data);
    } catch (e) {
      setError(e.response?.data?.error || e.message);
    } finally { setInferring(false); }
  };

  const handleSave = async () => {
    if (!form.presentation_title.trim()) return setError('Please enter a presentation title.');
    setSaving(true); setError(''); setSaved(false);
    try {
      const { data } = await updateObjectives(projectId, form);
      setObjectives(data);
      setStatus('configured');
      setSaved(true);
    } catch (e) {
      setError(e.response?.data?.error || e.message);
    } finally { setSaving(false); }
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <div className="page-title">Configure Objectives</div>
        <div className="page-sub">Let AI infer your presentation goals, or fill them in manually.</div>
      </div>

      {error && <div className="banner banner-error"><span className="banner-icon">⚠️</span>{error}</div>}
      {saved && <div className="banner banner-success"><span className="banner-icon">✅</span>Objectives saved — you can now generate the presentation.</div>}

      {/* AI infer button */}
      <div className="card" style={{ marginBottom: 20, background: 'linear-gradient(135deg, #f0f4ff 0%, #fff 100%)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h3 style={{ marginBottom: 4 }}>✨ Auto-Infer from Documents</h3>
            <p className="text-muted">Gemini reads your RFP/brief and data to suggest objectives, metrics, and audience.</p>
          </div>
          <button className="btn btn-primary" onClick={handleInfer} disabled={inferring} style={{ minWidth: 180 }}>
            {inferring ? <><span className="spinner" /> Analysing…</> : '✨ Infer Objectives'}
          </button>
        </div>
      </div>

      {/* Brief Decomposition panel — shown after inference */}
      {brief && (
        <div className="card" style={{ marginBottom: 20, borderLeft: '4px solid #C9A84C' }}>
          <h3 style={{ marginBottom: 16, color: '#1F3864' }}>Brief Analysis</h3>
          <div style={{ display: 'grid', gap: 16 }}>
            <div>
              <div className="form-label" style={{ marginBottom: 4 }}>Domain Context</div>
              <div style={{ padding: '8px 12px', background: '#f8f9fa', borderRadius: 6, fontSize: 14 }}>
                {brief.domain_context}
              </div>
            </div>
            <div>
              <div className="form-label" style={{ marginBottom: 4 }}>Analytical Questions</div>
              <ol style={{ margin: 0, paddingLeft: 20 }}>
                {(brief.analytical_questions || []).map((q, i) => (
                  <li key={i} style={{ fontSize: 14, marginBottom: 4, color: '#404040' }}>{q}</li>
                ))}
              </ol>
            </div>
            <div>
              <div className="form-label" style={{ marginBottom: 4 }}>Audience &amp; Tone</div>
              <div style={{ padding: '8px 12px', background: '#f8f9fa', borderRadius: 6, fontSize: 14 }}>
                {brief.audience_and_tone}
              </div>
            </div>
            <div>
              <div className="form-label" style={{ marginBottom: 4 }}>Summary</div>
              <div style={{ padding: '8px 12px', background: '#f8f9fa', borderRadius: 6, fontSize: 14, lineHeight: 1.6 }}>
                {brief.full_summary}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="card" style={{ marginBottom: 20 }}>
        <h3 style={{ marginBottom: 20 }}>Presentation Settings</h3>

        <div className="form-group">
          <label className="form-label">Presentation Title *</label>
          <input className="input" value={form.presentation_title}
            placeholder="e.g. Q3 Competitor Market Analysis"
            onChange={e => set('presentation_title', e.target.value)} />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Target Audience</label>
            <div className="seg-group">
              {AUDIENCE.map(a => (
                <button key={a} className={`seg-btn ${form.audience === a ? 'active' : ''}`}
                  onClick={() => set('audience', a)}>{a}</button>
              ))}
            </div>
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Narrative Tone</label>
            <div className="seg-group">
              {TONE.map(t => (
                <button key={t} className={`seg-btn ${form.tone === t ? 'active' : ''}`}
                  onClick={() => set('tone', t)}>{t}</button>
              ))}
            </div>
          </div>
        </div>

        <TagInput
          label="Primary Objectives"
          hint="What should this presentation achieve? Press Enter to add each."
          values={form.primary_objectives}
          onChange={v => set('primary_objectives', v)}
          placeholder="e.g. Benchmark competitor pricing strategies"
        />

        <TagInput
          label="Key Metrics to Highlight"
          hint="Which numeric KPIs matter most?"
          values={form.key_metrics}
          onChange={v => set('key_metrics', v)}
          placeholder="e.g. Market Share, Revenue Growth, NPS"
        />

        <TagInput
          label="Comparison Dimensions"
          hint="What categories to compare across? (brands, regions, segments…)"
          values={form.comparison_dimensions}
          onChange={v => set('comparison_dimensions', v)}
          placeholder="e.g. Brand, Region, Age Group"
        />
      </div>

      <div style={{ display: 'flex', gap: 12 }}>
        <button className="btn btn-primary btn-lg" onClick={handleSave}
          disabled={saving || !form.presentation_title.trim()}>
          {saving ? <><span className="spinner" /> Saving…</> : '💾 Save Objectives'}
        </button>
        {saved && (
          <button className="btn btn-accent btn-lg" onClick={() => navigate(`/projects/${projectId}/generate`)}>
            Generate Presentation →
          </button>
        )}
      </div>
    </div>
  );
}
