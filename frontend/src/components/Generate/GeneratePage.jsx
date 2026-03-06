import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import Plot from 'react-plotly.js';
import useProjectStore from '../../store/projectStore';
import { generatePresentation, getSlides, downloadPresentation, downloadPdf } from '../../services/api';

const PIPELINE = [
  { label: 'Extracting key insights from data',   icon: '🔍' },
  { label: 'Planning slide structure',             icon: '🗂' },
  { label: 'Building charts & visualisations',    icon: '📈' },
  { label: 'Writing analyst narratives',           icon: '✍️' },
  { label: 'Assembling PowerPoint file',           icon: '📊' },
];

const CHIP_ICONS = {
  title:             '🎯',
  chart:             '📊',
  insight:           '💡',
  overview:          '🗂',
  executive_summary: '📋',
  recommendation:    '✅',
  comparison:        '⚖️',
};

function SlideChart({ slide }) {
  const plotData = useMemo(() => {
    if (!slide.chart_json) return null;
    try { return JSON.parse(slide.chart_json); } catch { return null; }
  }, [slide.chart_json]);

  if (plotData) {
    return (
      <Plot
        data={plotData.data}
        layout={{
          ...plotData.layout,
          autosize: true,
          margin: { l: 28, r: 12, t: 28, b: 28 },
          paper_bgcolor: 'transparent',
          plot_bgcolor: 'transparent',
          font: { size: 10 },
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: '100%', height: '100%' }}
        useResizeHandler
      />
    );
  }
  if (slide.chart_png_url) {
    return <img src={slide.chart_png_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />;
  }
  const type = slide.slide_type || 'chart';
  return (
    <div className="slide-card-preview-empty">
      <span className="slide-card-preview-empty-icon">{CHIP_ICONS[type] || '📄'}</span>
      <span>{type.replace(/_/g, ' ')}</span>
    </div>
  );
}

function SlideCard({ slide, index }) {
  const type = slide.slide_type || 'chart';
  const chipClass = `slide-type-chip chip-${type in CHIP_ICONS ? type : 'default'}`;
  const preview = slide.narrative || slide.bullet_points?.[0] || '';

  return (
    <div className="slide-card fade-in">
      <div className="slide-card-header">
        <span className="slide-num">{index + 1}</span>
        <span className="slide-card-title">{slide.title}</span>
      </div>

      <div className="slide-card-preview">
        <SlideChart slide={slide} />
      </div>

      <div className="slide-card-body">
        <span className={chipClass}>
          {CHIP_ICONS[type] || '📄'} {type.replace(/_/g, ' ')}
        </span>
        {preview && <p className="slide-narrative">{preview}</p>}
      </div>
    </div>
  );
}

export default function GeneratePage() {
  const navigate = useNavigate();
  const { projectId, status, slides, setSlides, setPptxUrl, setStatus } = useProjectStore();

  const [generating, setGenerating] = useState(false);
  const [step,       setStep]       = useState(-1);
  const [error,      setError]      = useState('');

  // Auto-fetch slides when navigating back to a ready project
  useEffect(() => {
    if (status === 'ready' && slides.length === 0 && projectId) {
      getSlides(projectId).then(({ data }) => setSlides(data)).catch(() => {});
    }
  }, [projectId, status]);

  const isReady  = status === 'ready' && slides.length > 0;

  const handleGenerate = async () => {
    setGenerating(true); setError(''); setStep(0);

    const timer = setInterval(() => {
      setStep(s => (s < PIPELINE.length - 1 ? s + 1 : s));
    }, 9000);

    try {
      const { data } = await generatePresentation(projectId);
      clearInterval(timer);
      setStep(PIPELINE.length);

      const { data: slidesData } = await getSlides(projectId);
      setSlides(slidesData);
      setPptxUrl(data.pptx_url);
      setStatus('ready');
    } catch (e) {
      clearInterval(timer);
      setError(e.response?.data?.error || e.message);
    } finally {
      setGenerating(false);
    }
  };

  const progress = step < 0 ? 0 : Math.round((Math.min(step, PIPELINE.length) / PIPELINE.length) * 100);

  return (
    <div className="fade-in">
      <div className="page-header">
        <div className="page-title">Generate Presentation</div>
        <div className="page-sub">AI analyses your data, extracts insights, builds charts, and writes analyst narratives.</div>
      </div>

      {error && <div className="banner banner-error"><span className="banner-icon">⚠️</span>{error}</div>}

      {!isReady && (
        <div className="card" style={{ marginBottom: 28, maxWidth: 560 }}>
          {!generating ? (
            <>
              <h3 style={{ marginBottom: 8 }}>Ready to generate</h3>
              <p className="text-muted" style={{ marginBottom: 20 }}>
                This will take 40–90 seconds. Gemini will make several AI calls to plan and write each slide.
              </p>
              <button className="btn btn-primary btn-lg" onClick={handleGenerate}>
                🚀 Generate Presentation
              </button>
            </>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <h3>Building your presentation…</h3>
                <span className="text-muted">{progress}%</span>
              </div>
              <div className="progress-track" style={{ marginBottom: 24 }}>
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
              {PIPELINE.map((p, i) => {
                const state = i < step ? 'done' : i === step ? 'active' : 'pending';
                return (
                  <div key={i} className="pipeline-step">
                    <div className={`pipeline-dot ${state}`}>
                      {state === 'done' ? '✓' : state === 'active' ? <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> : p.icon}
                    </div>
                    <span className={`pipeline-label ${state}`}>{p.label}</span>
                  </div>
                );
              })}
            </>
          )}
        </div>
      )}

      {isReady && (
        <>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 28, flexWrap: 'wrap' }}>
            <span className="status-pill pill-ready">✓ {slides.length} slides generated</span>
            <a href={downloadPresentation(projectId)} download className="btn btn-primary">
              ⬇ Download .pptx
            </a>
            <a href={downloadPdf(projectId)} download className="btn btn-primary">
              📄 Download PDF
            </a>
            <button className="btn btn-accent" onClick={() => navigate('/chat')}>
              💬 Chat with Slides →
            </button>
          </div>

          <div className="slide-grid">
            {slides.map((slide, i) => (
              <SlideCard key={slide.id} slide={slide} index={i} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
