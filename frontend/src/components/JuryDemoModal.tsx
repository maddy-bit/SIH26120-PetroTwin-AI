import React, { useState, useEffect } from 'react';
import { X, Play, Pause, ChevronRight, CheckCircle2, Award, Zap, ShieldAlert, Sparkles } from 'lucide-react';

interface JuryDemoProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigateTab: (tab: string) => void;
}

export const JuryDemoModal: React.FC<JuryDemoProps> = ({ isOpen, onClose, onNavigateTab }) => {
  const [currentMinute, setCurrentMinute] = useState<number>(1);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);

  const stages = [
    {
      minute: 1,
      tab: 'dashboard',
      title: 'Minute 1: The Baghewala Heavy Oil Problem',
      summary: 'Cold reservoir (47°C) + thick crude (4,200 cP) = Zero natural flow. Oil India relies on Cyclic Steam Stimulation (CSS) and Sucker Rod Pumping (SRP). But treating them separately causes severe operational failures.',
      keyTakeaway: 'The platform establishes baseline thermodynamic and fluid properties for the Jodhpur Sandstone.'
    },
    {
      minute: 2,
      tab: 'live-ops',
      title: 'Minute 2: Live Telemetry & Dynamometer Card',
      summary: 'High-frequency telemetry stream correlates bottomhole temperature, pressure, polished rod load, and downstroke pump plunger displacement in real-time.',
      keyTakeaway: 'Surface and downhole dyno cards detect fluid friction hysteresis before structural fatigue sets in.'
    },
    {
      minute: 3,
      tab: 'digital-twin',
      title: 'Minute 3: Reservoir Cooling & Viscosity Surge',
      summary: 'Using the 180-Day Time Machine, observe the thermal dissipation plume cooling from 192°C peak down to 55°C. Viscosity exponentially rebounds from 18 cP back to 3,400 cP.',
      keyTakeaway: 'The Digital Twin predicts downstroke Couette drag quadrupling along the 900m wellbore.'
    },
    {
      minute: 4,
      tab: 'failures',
      title: 'Minute 4: Failure Hazard Elevation (Rod Floating)',
      summary: 'As viscosity rises at fixed SPM (6.8), the downward horsehead outruns the rod sinking terminal velocity. Carrier bar separates from clamp, inducing violent impact loading shock waves (5,000 m/s).',
      keyTakeaway: 'Multi-hazard engine flags 78% rod float threat with SHAP feature attribution.'
    },
    {
      minute: 5,
      tab: 'pareto',
      title: 'Minute 5: Joint CSS + SRP Pareto Optimization',
      summary: 'The constrained Pareto optimizer searches the multi-dimensional space, prescribing SPM reduction to 5.5 (eliminates rod float) while optimizing the next 2,400 T steam cycle.',
      keyTakeaway: 'Delivers +18.4% Net Oil, -22% SOR, Zero Rod-Float Risk, backed by full audit traceability.'
    }
  ];

  useEffect(() => {
    let timer: any;
    if (isPlaying && isOpen) {
      timer = setInterval(() => {
        setCurrentMinute((prev) => {
          if (prev >= 5) {
            setIsPlaying(false);
            return 5;
          }
          const next = prev + 1;
          onNavigateTab(stages[next - 1].tab);
          return next;
        });
      }, 10000); // 10 seconds per stage in demo fast-forward mode
    }
    return () => clearInterval(timer);
  }, [isPlaying, isOpen]);

  const activeStage = stages[currentMinute - 1];

  const handleSelectStage = (min: number) => {
    setCurrentMinute(min);
    onNavigateTab(stages[min - 1].tab);
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.82)',
      backdropFilter: 'blur(12px)',
      zIndex: 200,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      <div style={{
        background: '#0d131f',
        border: '1px solid rgba(0, 229, 255, 0.4)',
        borderRadius: '14px',
        width: '750px',
        maxWidth: '100%',
        boxShadow: '0 0 40px rgba(0, 229, 255, 0.25)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
      }}>
        {/* Modal Header */}
        <div style={{
          padding: '16px 24px',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'rgba(0, 229, 255, 0.05)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Award size={20} color="#ff6d00" />
            <span style={{ fontSize: '1.05rem', fontWeight: 800, color: '#fff' }}>
              SIH 2026 OFFICIAL 5-MINUTE JURY DEMO WALKTHROUGH
            </span>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
            <X size={20} />
          </button>
        </div>

        {/* Step Progress Pills */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', padding: '16px 24px', gap: '8px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          {stages.map((s) => (
            <button
              key={s.minute}
              onClick={() => handleSelectStage(s.minute)}
              style={{
                background: currentMinute === s.minute ? 'rgba(0, 229, 255, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                border: currentMinute === s.minute ? '1px solid #00e5ff' : '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '6px',
                padding: '8px',
                color: currentMinute === s.minute ? '#00e5ff' : '#94a3b8',
                fontSize: '0.72rem',
                fontWeight: 700,
                cursor: 'pointer',
                textAlign: 'center'
              }}
            >
              Min {s.minute}
            </button>
          ))}
        </div>

        {/* Active Stage Body */}
        <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#00e5ff' }}>
            {activeStage.title}
          </div>
          <div style={{ fontSize: '0.85rem', color: '#cbd5e1', lineHeight: '1.6' }}>
            {activeStage.summary}
          </div>
          <div style={{
            background: 'rgba(0, 230, 118, 0.08)',
            border: '1px solid rgba(0, 230, 118, 0.3)',
            borderRadius: '8px',
            padding: '12px 16px',
            fontSize: '0.78rem',
            color: '#00e676'
          }}>
            <strong>Key Technical Defense:</strong> {activeStage.keyTakeaway}
          </div>
        </div>

        {/* Footer Actions */}
        <div style={{
          padding: '16px 24px',
          borderTop: '1px solid rgba(255,255,255,0.08)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'rgba(0,0,0,0.2)'
        }}>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            style={{
              background: 'rgba(255,255,255,0.06)',
              color: '#fff',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '6px',
              padding: '8px 16px',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            {isPlaying ? <Pause size={14} /> : <Play size={14} />}
            <span>{isPlaying ? 'Pause Auto-Advance' : 'Resume Auto-Advance'}</span>
          </button>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={() => {
                onNavigateTab(activeStage.tab);
                onClose();
              }}
              style={{
                background: '#00e5ff',
                color: '#000',
                border: 'none',
                borderRadius: '6px',
                padding: '8px 20px',
                fontSize: '0.82rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <span>INSPECT THIS SCREEN IN DEPTH</span>
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
