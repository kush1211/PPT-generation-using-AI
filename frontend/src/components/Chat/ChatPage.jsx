import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import useProjectStore from '../../store/projectStore';
import { sendChat, getChatHistory, downloadPresentation } from '../../services/api';

const SUGGESTIONS = [
  'Explain the key insight on slide 2',
  'Rewrite slide 3 for a leadership audience',
  'Add a chart comparing top 3 brands only',
  'Focus only on underperforming regions',
  'Summarize the main findings',
];

function SlideViewer({ slides, selectedIdx, onSelect, updatedIdx }) {
  if (!slides.length) {
    return (
      <div className="slide-viewer" style={{ alignItems: 'center', justifyContent: 'center', minHeight: 400 }}>
        <div style={{ textAlign: 'center', color: 'var(--text-light)' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>📊</div>
          <p>No slides yet. Generate a presentation first.</p>
        </div>
      </div>
    );
  }

  const slide = slides.find(s => s.slide_index === selectedIdx) || slides[0];

  return (
    <div className="slide-viewer">
      <div className="slide-thumb-strip">
        {slides.map((s, i) => (
          <button
            key={s.id}
            className={`slide-thumb ${s.slide_index === (selectedIdx ?? 0) ? 'active' : ''} ${s.slide_index === updatedIdx ? 'updated' : ''}`}
            onClick={() => onSelect(s.slide_index)}
          >
            {i + 1}
          </button>
        ))}
      </div>

      <div className="slide-detail">
        <div className="slide-detail-header">
          <div className="slide-detail-meta">
            Slide {slide.slide_index + 1} · {slide.slide_type?.replace(/_/g, ' ')}
          </div>
          <div className="slide-detail-title">{slide.title}</div>
          {slide.subtitle && <div className="slide-detail-sub">{slide.subtitle}</div>}
        </div>

        {slide.chart_png_url && (
          <img src={slide.chart_png_url} alt="chart" className="slide-detail-chart" />
        )}

        {slide.narrative && (
          <div className="slide-section">
            <div className="slide-section-label">Analyst Narrative</div>
            <p style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--text)' }}>{slide.narrative}</p>
          </div>
        )}

        {slide.bullet_points?.length > 0 && (
          <div className="slide-section">
            <div className="slide-section-label">Key Points</div>
            <ul className="slide-bullets">
              {slide.bullet_points.map((b, i) => <li key={i}>{b}</li>)}
            </ul>
          </div>
        )}

        {slide.speaker_notes && (
          <div className="slide-section">
            <details>
              <summary style={{ fontSize: 13, color: 'var(--text-light)', cursor: 'pointer', userSelect: 'none' }}>
                Speaker Notes
              </summary>
              <p style={{ fontSize: 13, marginTop: 8, color: 'var(--text-light)', fontStyle: 'italic', lineHeight: 1.6 }}>
                {slide.speaker_notes}
              </p>
            </details>
          </div>
        )}
      </div>
    </div>
  );
}

function ChatBubble({ msg }) {
  const isUser = msg.role === 'user';
  const avatar = isUser ? '👤' : '🤖';

  return (
    <div className={`chat-bubble-row ${isUser ? 'user' : ''}`} style={{ marginBottom: 16 }}>
      <div className="chat-avatar">{avatar}</div>
      <div className="chat-bubble-wrap">
        <div className={`chat-bubble ${isUser ? 'user' : 'assistant'}`}>
          {msg.content}
        </div>
      </div>
    </div>
  );
}

export default function ChatPage() {
  const navigate = useNavigate();
  const { projectId, chatHistory, addChatMessage, setChatHistory, setPptxUrl, updateSlide } = useProjectStore();
  const storedSlides = useProjectStore(s => s.slides);

  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [selectedSlide, setSelectedSlide] = useState(null);
  const [localSlides, setLocalSlides] = useState(storedSlides);
  const [updatedIdx, setUpdatedIdx] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (!projectId) navigate('/upload');
    if (projectId) {
      getChatHistory(projectId).then(({ data }) => setChatHistory(data));
    }
  }, [projectId]);

  useEffect(() => {
    setLocalSlides(storedSlides);
  }, [storedSlides]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, sending]);

  const handleSend = async (msg = message) => {
    const text = msg.trim();
    if (!text || sending) return;

    setSending(true);
    setError('');
    setMessage('');
    setUpdatedIdx(null);
    addChatMessage({ role: 'user', content: text });

    try {
      const { data } = await sendChat(projectId, text);

      addChatMessage({ role: 'assistant', content: data.message });

      if (data.updated_slide_index !== null && data.slide_data) {
        if (data.slide_data?.is_new_slide) {
          setLocalSlides(s => [...s, data.slide_data]);
        } else {
          updateSlide(data.updated_slide_index, data.slide_data);
          setLocalSlides(s => s.map(sl =>
            sl.slide_index === data.updated_slide_index ? { ...sl, ...data.slide_data } : sl
          ));
        }
        setSelectedSlide(data.updated_slide_index);
        setUpdatedIdx(data.updated_slide_index);
      }

      if (data.pptx_url) setPptxUrl(data.pptx_url);
    } catch (e) {
      setError(e.response?.data?.error || e.message);
      addChatMessage({ role: 'assistant', content: `Error: ${e.response?.data?.error || e.message}` });
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div className="page-title">Chat with Slides</div>
            <div className="page-sub">Ask questions, request changes, or generate new slides conversationally.</div>
          </div>
          <a href={downloadPresentation(projectId)} download className="btn btn-primary">
            ⬇ Download .pptx
          </a>
        </div>
      </div>

      {error && <div className="banner banner-error"><span className="banner-icon">⚠️</span>{error}</div>}

      <div className="chat-layout">
        {/* Chat panel */}
        <div className="chat-panel">
          <div className="chat-panel-header">
            <div className="chat-panel-title">AI Assistant</div>
            <div className="chat-panel-sub">{localSlides.length} slides loaded</div>
          </div>

          {chatHistory.length === 0 && (
            <div className="chat-suggestions">
              <div className="suggestions-label">Try asking</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {SUGGESTIONS.map(s => (
                  <button key={s} className="suggestion-chip" onClick={() => handleSend(s)}>
                    "{s}"
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="chat-messages">
            {chatHistory.map((msg, i) => (
              <ChatBubble key={i} msg={msg} index={i} />
            ))}
            {sending && (
              <div className="chat-bubble-row" style={{ marginBottom: 16 }}>
                <div className="chat-avatar">🤖</div>
                <div className="typing-indicator">
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="chat-input-area">
            <input
              className="chat-input"
              value={message}
              onChange={e => setMessage(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder="Ask about slides, request changes…"
              disabled={sending}
            />
            <button
              className="send-btn"
              onClick={() => handleSend()}
              disabled={sending || !message.trim()}
            >
              {sending ? <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} /> : '↑'}
            </button>
          </div>
        </div>

        {/* Slides panel */}
        <SlideViewer
          slides={localSlides}
          selectedIdx={selectedSlide}
          onSelect={setSelectedSlide}
          updatedIdx={updatedIdx}
        />
      </div>
    </div>
  );
}
