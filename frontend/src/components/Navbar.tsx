import React from 'react';
import { Activity, ShieldAlert, Cpu, Sparkles, Play, Database } from 'lucide-react';
import { WellId } from '../types/petro';

interface NavbarProps {
  selectedWell: WellId;
  onSelectWell: (id: WellId) => void;
  activeTab: string;
  onSelectTab: (tab: string) => void;
  onOpenJuryDemo: () => void;
  onOpenCopilot: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  selectedWell,
  onSelectWell,
  activeTab,
  onSelectTab,
  onOpenJuryDemo,
  onOpenCopilot
}) => {
  const tabs = [
    { id: 'dashboard', label: 'Overview' },
    { id: 'digital-twin', label: 'Digital Twin' },
    { id: 'live-ops', label: 'Live Operations' },
    { id: 'css-optimizer', label: 'CSS Optimizer' },
    { id: 'srp-optimizer', label: 'SRP Optimizer' },
    { id: 'failures', label: 'Failure Intelligence' },
    { id: 'scenario-lab', label: 'Scenario Lab' },
    { id: 'pareto', label: 'Pareto Optimization' }
  ];

  return (
    <header style={{
      background: 'rgba(10, 14, 23, 0.92)',
      backdropFilter: 'blur(16px)',
      borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      padding: '0 20px'
    }}>
      {/* Top Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '60px',
        borderBottom: '1px solid rgba(255, 255, 255, 0.05)'
      }}>
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #00e5ff 0%, #0077b6 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 16px rgba(0, 229, 255, 0.4)'
          }}>
            <Cpu size={22} color="#000" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.15rem', fontWeight: 800, letterSpacing: '0.02em', color: '#fff' }}>
                PETRO-TWIN <span style={{ color: '#00e5ff' }}>AI</span>
              </span>
              <span className="tech-badge badge-cyan" style={{ fontSize: '0.65rem' }}>SIH26120</span>
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
              Oil India Limited • Baghewala Field Jodhpur Sandstone Digital Twin
            </div>
          </div>
        </div>

        {/* Data Honesty Watermark Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div className="tech-badge badge-sim" style={{ padding: '4px 10px', fontSize: '0.72rem' }}>
            <Database size={12} />
            <span>DATA MODE: SIMULATION (LITERATURE-CALIBRATED)</span>
          </div>

          {/* Live Status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(255,255,255,0.04)', padding: '5px 12px', borderRadius: '20px', border: '1px solid rgba(255,255,255,0.06)' }}>
            <span className="live-indicator"></span>
            <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: '#00e676', fontWeight: 600 }}>LIVE STREAM</span>
          </div>

          {/* Well Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>ACTIVE WELL:</span>
            <select
              value={selectedWell}
              onChange={(e) => onSelectWell(e.target.value as WellId)}
              style={{
                background: '#161e30',
                color: '#00e5ff',
                border: '1px solid rgba(0, 229, 255, 0.35)',
                padding: '6px 12px',
                borderRadius: '6px',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.8rem',
                fontWeight: 700,
                outline: 'none',
                cursor: 'pointer'
              }}
            >
              <option value="BW-DEMO-001">BW-DEMO-001 (Late Cycle Cooling)</option>
              <option value="BW-DEMO-002">BW-DEMO-002 (Peak Thermal Flush)</option>
              <option value="BW-DEMO-003">BW-DEMO-003 (Critical Rod Float Alert)</option>
            </select>
          </div>

          {/* SIH Jury Demo Action */}
          <button
            onClick={onOpenJuryDemo}
            style={{
              background: 'linear-gradient(135deg, #ff6d00 0%, #e65100 100%)',
              color: '#fff',
              border: 'none',
              padding: '7px 14px',
              borderRadius: '6px',
              fontSize: '0.78rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: '0 0 16px rgba(255, 109, 0, 0.35)'
            }}
          >
            <Play size={14} fill="#fff" />
            <span>5-MIN JURY DEMO</span>
          </button>

          {/* AI Copilot Drawer Trigger */}
          <button
            onClick={onOpenCopilot}
            style={{
              background: 'rgba(0, 229, 255, 0.12)',
              color: '#00e5ff',
              border: '1px solid rgba(0, 229, 255, 0.4)',
              padding: '7px 14px',
              borderRadius: '6px',
              fontSize: '0.78rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Sparkles size={14} />
            <span>AI COPILOT</span>
          </button>
        </div>
      </div>

      {/* Navigation Sub-Bar */}
      <nav style={{ display: 'flex', gap: '6px', overflowX: 'auto', padding: '6px 0' }}>
        {tabs.map((t) => {
          const isActive = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => onSelectTab(t.id)}
              style={{
                background: isActive ? 'rgba(0, 229, 255, 0.14)' : 'transparent',
                color: isActive ? '#00e5ff' : '#94a3b8',
                border: isActive ? '1px solid rgba(0, 229, 255, 0.4)' : '1px solid transparent',
                borderRadius: '6px',
                padding: '6px 14px',
                fontSize: '0.82rem',
                fontWeight: isActive ? 700 : 500,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all 0.15s ease'
              }}
            >
              {t.label}
            </button>
          );
        })}
      </nav>
    </header>
  );
};
