import { useEffect, useState, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import Plot from 'react-plotly.js';
import { getSlides, getProject } from '../../services/api';

const PRIMARY = '#1F3864';
const ACCENT  = '#C9A84C';
const WHITE   = '#FFFFFF';
const DARK_GRAY = '#404040';

const SLIDE_W = 960;
const SLIDE_H = 540;

const base = {
  width:  SLIDE_W,
  height: SLIDE_H,
  position: 'relative',
  overflow: 'hidden',
  backgroundColor: WHITE,
  fontFamily: 'Calibri, Arial, sans-serif',
  boxSizing: 'border-box',
};

function HeaderBar() {
  return (
    <div style={{
      position: 'absolute', top: 0, left: 0,
      width: '100%', height: 6,
      backgroundColor: PRIMARY,
    }} />
  );
}

function SlideTitle({ text }) {
  return (
    <div style={{
      position: 'absolute', top: 10, left: 38, right: 38,
      fontSize: 22, fontWeight: 'bold', color: PRIMARY,
      lineHeight: 1.3,
    }}>
      {text}
    </div>
  );
}

function ChartArea({ slide, style }) {
  const plotData = useMemo(() => {
    if (!slide.chart_json) return null;
    try { return JSON.parse(slide.chart_json); } catch { return null; }
  }, [slide.chart_json]);

  if (plotData) {
    return (
      <div style={{ position: 'absolute', ...style }}>
        <Plot
          data={plotData.data}
          layout={{
            ...plotData.layout,
            autosize: true,
            margin: { l: 40, r: 20, t: 30, b: 40 },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            font: { size: 11 },
          }}
          config={{ displayModeBar: false, responsive: true, staticPlot: true }}
          style={{ width: '100%', height: '100%' }}
          useResizeHandler
        />
      </div>
    );
  }
  if (slide.chart_png_url) {
    return <img src={slide.chart_png_url} alt="" style={{ position: 'absolute', objectFit: 'contain', ...style }} />;
  }
  return null;
}

function TitleSlide({ slide }) {
  return (
    <div style={{ ...base, backgroundColor: PRIMARY, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ fontSize: 38, fontWeight: 'bold', color: WHITE, textAlign: 'center', padding: '0 60px', lineHeight: 1.3 }}>
        {slide.title}
      </div>
      {slide.subtitle && (
        <div style={{ fontSize: 18, color: ACCENT, marginTop: 24, textAlign: 'center' }}>
          {slide.subtitle}
        </div>
      )}
      <div style={{ width: 280, height: 3, backgroundColor: ACCENT, marginTop: 28 }} />
      <div style={{ fontSize: 13, color: '#cccccc', marginTop: 16 }}>
        {new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
      </div>
    </div>
  );
}

function ChartSlide({ slide }) {
  const hasChart = !!(slide.chart_json || slide.chart_png_url);
  const hasNarrative = !!slide.narrative;
  return (
    <div style={base}>
      <HeaderBar />
      <SlideTitle text={slide.title} />
      {slide.subtitle && (
        <div style={{ position: 'absolute', top: 48, left: 38, right: 38, fontSize: 12, color: '#606060', fontStyle: 'italic' }}>
          {slide.subtitle}
        </div>
      )}
      {hasChart && (
        <ChartArea slide={slide} style={{
          left: 30, top: hasNarrative ? 66 : 56,
          width: SLIDE_W - 60,
          height: hasNarrative ? 320 : 440,
        }} />
      )}
      {hasNarrative && (
        <div style={{
          position: 'absolute',
          bottom: 14, left: 38, right: 38,
          fontSize: 11, color: DARK_GRAY, lineHeight: 1.5,
          maxHeight: hasChart ? 110 : 420,
          overflow: 'hidden',
        }}>
          {slide.narrative}
        </div>
      )}
      <SlideFooter index={slide.slide_index} />
    </div>
  );
}

function OverviewSlide({ slide }) {
  const bullets = slide.bullet_points || [];
  return (
    <div style={base}>
      <HeaderBar />
      <SlideTitle text={slide.title} />
      <div style={{ position: 'absolute', top: 60, left: 38, width: 420, bottom: 28, overflowHidden: true }}>
        <div style={{ fontSize: 13, fontWeight: 'bold', color: PRIMARY, marginBottom: 8 }}>Key Findings</div>
        {bullets.slice(0, 6).map((b, i) => (
          <div key={i} style={{ fontSize: 11, color: DARK_GRAY, marginBottom: 6, lineHeight: 1.5 }}>• {b}</div>
        ))}
      </div>
      {slide.narrative && (
        <div style={{ position: 'absolute', top: 60, left: 500, right: 38, bottom: 28, fontSize: 11, color: DARK_GRAY, lineHeight: 1.6, overflow: 'hidden' }}>
          {slide.narrative}
        </div>
      )}
      <SlideFooter index={slide.slide_index} />
    </div>
  );
}

function ExecutiveSummarySlide({ slide }) {
  const bullets = slide.bullet_points || [];
  const hasChart = !!(slide.chart_json || slide.chart_png_url);
  return (
    <div style={base}>
      <HeaderBar />
      <SlideTitle text={slide.title} />
      {hasChart ? (
        <>
          <ChartArea slide={slide} style={{ left: 30, top: 56, width: SLIDE_W - 60, height: 320 }} />
          {slide.narrative && (
            <div style={{ position: 'absolute', bottom: 28, left: 38, right: 38, fontSize: 11, color: DARK_GRAY, lineHeight: 1.5, maxHeight: 110, overflow: 'hidden' }}>
              {slide.narrative}
            </div>
          )}
        </>
      ) : bullets.length > 0 ? (
        <div style={{ position: 'absolute', top: 66, left: 38, right: 38, bottom: 60 }}>
          {bullets.slice(0, 7).map((b, i) => (
            <div key={i} style={{ fontSize: 12, color: DARK_GRAY, marginBottom: 10, lineHeight: 1.5 }}>{i + 1}.&nbsp;&nbsp;{b}</div>
          ))}
        </div>
      ) : (
        <div style={{ position: 'absolute', top: 66, left: 38, right: 38, bottom: 60, fontSize: 12, color: DARK_GRAY, lineHeight: 1.6, overflow: 'hidden' }}>
          {slide.narrative}
        </div>
      )}
      <div style={{ position: 'absolute', bottom: 0, left: 0, width: '100%', height: 40, backgroundColor: PRIMARY }} />
      <SlideFooter index={slide.slide_index} light />
    </div>
  );
}

function RecommendationSlide({ slide }) {
  const bullets = slide.bullet_points || [];
  const items = bullets.length > 0 ? bullets : (slide.narrative || '').split('. ').filter(Boolean);
  const positions = [
    { left: 30,  top: 100 },
    { left: 343, top: 100 },
    { left: 656, top: 100 },
  ];
  return (
    <div style={base}>
      <HeaderBar />
      <SlideTitle text={slide.title} />
      {items.slice(0, 3).map((item, i) => (
        <div key={i} style={{
          position: 'absolute',
          left: positions[i].left, top: positions[i].top,
          width: 284, height: 380,
          backgroundColor: '#F2F2F2',
          border: '1px solid #cccccc',
          borderRadius: 4,
          boxSizing: 'border-box',
          padding: '48px 16px 16px',
        }}>
          <div style={{
            position: 'absolute', top: 12, left: 12,
            width: 32, height: 32, borderRadius: '50%',
            backgroundColor: PRIMARY,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: WHITE, fontWeight: 'bold', fontSize: 14,
          }}>{i + 1}</div>
          <div style={{ fontSize: 11, color: DARK_GRAY, lineHeight: 1.5 }}>{item.trim()}</div>
        </div>
      ))}
      <SlideFooter index={slide.slide_index} />
    </div>
  );
}

function SlideFooter({ index, light }) {
  return (
    <div style={{
      position: 'absolute', bottom: 8, right: 16,
      fontSize: 9, color: light ? 'rgba(255,255,255,0.6)' : '#808080',
    }}>
      Confidential · Slide {index + 1}
    </div>
  );
}

function renderSlide(slide) {
  switch (slide.slide_type) {
    case 'title':            return <TitleSlide slide={slide} />;
    case 'overview':         return <OverviewSlide slide={slide} />;
    case 'executive_summary':return <ExecutiveSummarySlide slide={slide} />;
    case 'recommendation':   return <RecommendationSlide slide={slide} />;
    default:                 return <ChartSlide slide={slide} />;
  }
}

export default function PrintView() {
  const { projectId } = useParams();
  const [slides, setSlides] = useState([]);
  const [title, setTitle]   = useState('Presentation');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getSlides(projectId), getProject(projectId)])
      .then(([slidesRes, projectRes]) => {
        setSlides(slidesRes.data.sort((a, b) => a.slide_index - b.slide_index));
        setTitle(projectRes.data.title || 'Presentation');
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  useEffect(() => {
    if (!loading && slides.length > 0) {
      // Extra delay for Plotly charts to finish rendering before print dialog
      const t = setTimeout(() => window.print(), 1200);
      return () => clearTimeout(t);
    }
  }, [loading, slides]);

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', fontFamily: 'Calibri, Arial, sans-serif', color: PRIMARY }}>
        Loading slides…
      </div>
    );
  }

  return (
    <>
      <style>{`
        @page { size: landscape; margin: 0; }
        @media print {
          body { margin: 0; }
          .print-slide-wrapper {
            page-break-after: always;
            page-break-inside: avoid;
            width: 100vw !important;
            height: 100vh !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            padding: 0 !important;
          }
          .print-slide-wrapper > div {
            transform: none !important;
            width: 100vw !important;
            height: 100vh !important;
          }
          .no-print { display: none !important; }
        }
        @media screen {
          body { background: #e0e0e0; margin: 0; padding: 24px 0; }
          .print-slide-wrapper {
            display: flex;
            justify-content: center;
            margin-bottom: 24px;
          }
          .print-slide-wrapper > div {
            transform-origin: top center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.25);
          }
        }
      `}</style>

      <div className="no-print" style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
        backgroundColor: PRIMARY, color: WHITE, padding: '10px 24px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        fontFamily: 'Calibri, Arial, sans-serif', fontSize: 14,
      }}>
        <span>{title} — {slides.length} slides</span>
        <button
          onClick={() => window.print()}
          style={{
            backgroundColor: ACCENT, color: WHITE, border: 'none',
            borderRadius: 4, padding: '6px 20px', cursor: 'pointer',
            fontSize: 13, fontWeight: 'bold',
          }}
        >
          Save as PDF
        </button>
      </div>

      <div style={{ paddingTop: 52 }}>
        {slides.map((slide) => (
          <div key={slide.id} className="print-slide-wrapper">
            {renderSlide(slide)}
          </div>
        ))}
      </div>
    </>
  );
}
