import React, { useState } from 'react';
import { X, Send, Sparkles, Terminal, Wrench, ShieldCheck, HelpCircle } from 'lucide-react';
import { api } from '../services/api';

interface CopilotProps {
  isOpen: boolean;
  onClose: () => void;
  selectedWell: string;
}

export const AICopilotDrawer: React.FC<CopilotProps> = ({ isOpen, onClose, selectedWell }) => {
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; text: string; tools?: string[] }>>([
    {
      role: 'assistant',
      text: `Hello! I am the **PetroTwin Agentic AI Copilot**. I am connected directly to the **Baghewala Jodhpur Sandstone Digital Twin**, physics solvers, and deterministic tool supervisor for well **${selectedWell}**.\n\nHow can I assist your operational decisions today?`,
      tools: ['get_well_state']
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const quickPrompts = [
    "Why did failure risk increase?",
    "Recommend next CSS cycle settings",
    "What happens if we increase soak time?",
    "Forecast production for next 30 days"
  ];

  const handleSend = async (queryText?: string) => {
    const q = queryText || input;
    if (!q.trim()) return;

    setMessages((prev) => [...prev, { role: 'user', text: q }]);
    setInput('');
    setIsLoading(true);

    try {
      const res = await api.queryCopilot(q, selectedWell);
      setMessages((prev) => [...prev, {
        role: 'assistant',
        text: res.answer,
        tools: res.tools_used
      }]);
    } catch {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        text: 'An error occurred querying the agent service. Operating in offline fallback mode.',
        tools: []
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      right: 0,
      bottom: 0,
      width: '460px',
      maxWidth: '90vw',
      background: 'rgba(13, 18, 28, 0.96)',
      backdropFilter: 'blur(20px)',
      borderLeft: '1px solid rgba(0, 229, 255, 0.3)',
      boxShadow: '-8px 0 32px rgba(0,0,0,0.5)',
      zIndex: 100,
      display: 'flex',
      flexDirection: 'column'
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '28px',
            height: '28px',
            borderRadius: '6px',
            background: 'linear-gradient(135deg, #00e5ff 0%, #0077b6 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <Sparkles size={16} color="#000" />
          </div>
          <div>
            <div style={{ fontSize: '0.92rem', fontWeight: 800, color: '#fff' }}>PETRO-TWIN COPILOT</div>
            <div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>Grounded Petroleum Supervisor Agent</div>
          </div>
        </div>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
          <X size={20} />
        </button>
      </div>

      {/* Messages Scroll Area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {messages.map((m, idx) => (
          <div
            key={idx}
            style={{
              alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '92%',
              background: m.role === 'user' ? 'rgba(0, 229, 255, 0.15)' : 'rgba(255, 255, 255, 0.04)',
              border: m.role === 'user' ? '1px solid rgba(0, 229, 255, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '10px',
              padding: '12px 14px',
              fontSize: '0.8rem',
              color: '#f1f5f9',
              lineHeight: '1.5'
            }}
          >
            {/* Tool Executions Badge */}
            {m.tools && m.tools.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '8px' }}>
                {m.tools.map((t, i) => (
                  <span key={i} className="tech-badge badge-cyan" style={{ fontSize: '0.62rem', padding: '2px 6px' }}>
                    <Wrench size={10} />
                    <span>{t}()</span>
                  </span>
                ))}
              </div>
            )}
            <div style={{ whiteSpace: 'pre-wrap' }}>{m.text}</div>
          </div>
        ))}
        {isLoading && (
          <div style={{ alignSelf: 'flex-start', color: '#00e5ff', fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sparkles size={14} />
            <span>Agent planning & calling physical calculators...</span>
          </div>
        )}
      </div>

      {/* Quick Prompts Chips */}
      <div style={{ padding: '8px 16px', display: 'flex', flexWrap: 'wrap', gap: '6px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
        {quickPrompts.map((p, i) => (
          <button
            key={i}
            onClick={() => handleSend(p)}
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: '12px',
              padding: '4px 10px',
              fontSize: '0.68rem',
              color: '#94a3b8',
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            {p}
          </button>
        ))}
      </div>

      {/* Input Bar */}
      <div style={{ padding: '14px 16px', borderTop: '1px solid rgba(255,255,255,0.08)', display: 'flex', gap: '8px' }}>
        <input
          type="text"
          placeholder="Ask engineering question..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleSend(); }}
          style={{
            flex: 1,
            background: '#07090e',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '6px',
            padding: '8px 12px',
            color: '#fff',
            fontSize: '0.8rem',
            outline: 'none'
          }}
        />
        <button
          onClick={() => handleSend()}
          style={{
            background: '#00e5ff',
            color: '#000',
            border: 'none',
            borderRadius: '6px',
            padding: '0 14px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
};
