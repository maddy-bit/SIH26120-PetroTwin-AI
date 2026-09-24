import React from 'react';
import { ShieldAlert, AlertTriangle, Activity, CheckCircle, BarChart3, Wrench } from 'lucide-react';
import { FailureIntelligence } from '../types/petro';

interface FailureProps {
  failureData: FailureIntelligence | null;
}

export const FailureIntelligenceView: React.FC<FailureProps> = ({ failureData }) => {
  if (!failureData) {
    return <div style={{ padding: '40px', color: '#94a3b8' }}>Loading failure intelligence...</div>;
  }

  const { risks, mechanical_loads, feature_attribution_shap, overall_health_score, recommended_action } = failureData;

  const getBadgeClass = (lvl: string) => {
    switch (lvl) {
      case 'CRITICAL': return 'badge-red';
      case 'HIGH': return 'badge-red';
      case 'MEDIUM': return 'badge-amber';
      default: return 'badge-green';
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '24px 20px' }}>
      {/* Header */}
      <div className="glass-panel" style={{ padding: '18px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldAlert size={20} color="#ff334b" />
            <span>CALIBRATED EQUIPMENT FAILURE INTELLIGENCE & SHAP ATTRIBUTION</span>
          </div>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8' }}>
            Multi-hazard predictive survival analysis: Rod Floating, Impact Loading, Parted Rods, and Pump Unseating
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Composite Asset Health:</span>
          <span className="metric-number" style={{ fontSize: '1.3rem', color: overall_health_score > 70 ? '#00e676' : '#ff334b' }}>
            {overall_health_score} / 100
          </span>
        </div>
      </div>

      {/* 4 Hazard Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
        {/* Rod Floating */}
        <div className="glass-panel" style={{ padding: '18px 20px', borderTop: '3px solid #ff334b' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#fff' }}>ROD FLOATING RISK</span>
            <span className={`tech-badge ${getBadgeClass(risks.rod_floating.level)}`}>{risks.rod_floating.level}</span>
          </div>
          <div className="metric-number" style={{ fontSize: '2rem', color: '#fff', marginBottom: '4px' }}>
            {(risks.rod_floating.probability * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8', lineHeight: '1.4' }}>
            Couette viscous shear drag outrunning lower sinker bar terminal gravitational sinking velocity.
          </div>
        </div>

        {/* Impact Loading */}
        <div className="glass-panel" style={{ padding: '18px 20px', borderTop: '3px solid #ffb300' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#fff' }}>IMPACT LOADING (POUND)</span>
            <span className={`tech-badge ${getBadgeClass(risks.impact_loading.level)}`}>{risks.impact_loading.level}</span>
          </div>
          <div className="metric-number" style={{ fontSize: '2rem', color: '#fff', marginBottom: '4px' }}>
            {(risks.impact_loading.probability * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8', lineHeight: '1.4' }}>
            Slack carrier bridle catching delayed rod string; induces sonic shock waves at ~5,000 m/s.
          </div>
        </div>

        {/* Parted Rod */}
        <div className="glass-panel" style={{ padding: '18px 20px', borderTop: '3px solid #00e5ff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#fff' }}>PARTED ROD BREAKAGE</span>
            <span className={`tech-badge ${getBadgeClass(risks.parted_rod.level)}`}>{risks.parted_rod.level}</span>
          </div>
          <div className="metric-number" style={{ fontSize: '2rem', color: '#fff', marginBottom: '4px' }}>
            {(risks.parted_rod.probability * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8', lineHeight: '1.4' }}>
            Cyclic Goodman fatigue limit exceedance at rod pin threads and coupling shoulders.
          </div>
        </div>

        {/* Pump Unseating */}
        <div className="glass-panel" style={{ padding: '18px 20px', borderTop: '3px solid #00e676' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#fff' }}>PUMP UNSEATING RISK</span>
            <span className={`tech-badge ${getBadgeClass(risks.pump_unseating.level)}`}>{risks.pump_unseating.level}</span>
          </div>
          <div className="metric-number" style={{ fontSize: '2rem', color: '#fff', marginBottom: '4px' }}>
            {(risks.pump_unseating.probability * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8', lineHeight: '1.4' }}>
            Frictional upstroke hydraulic drag lifting pump barrel off bottomhole mechanical seating nipple.
          </div>
        </div>
      </div>

      {/* SHAP Feature Attribution Waterfall & Action */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '20px' }}>
        {/* SHAP Feature Attribution */}
        <div className="glass-panel" style={{ padding: '22px' }}>
          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <BarChart3 size={18} color="#00e5ff" />
            <span>EXPLAINABLE AI: SHAP FAILURE CONTRIBUTION BREAKDOWN</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {feature_attribution_shap.map((feat, idx) => (
              <div key={idx}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '4px' }}>
                  <span style={{ color: '#cbd5e1' }}>{feat.feature}</span>
                  <span style={{ color: '#00e5ff', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>+{feat.contribution_pct}%</span>
                </div>
                <div style={{ height: '7px', background: '#1e293b', borderRadius: '4px', overflow: 'hidden' }}>
                  <div style={{
                    height: '100%',
                    width: `${feat.contribution_pct}%`,
                    background: idx === 0 ? '#ff334b' : idx === 1 ? '#ffb300' : '#00e5ff',
                    borderRadius: '4px'
                  }}></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Actionable Engineering Recommendation */}
        <div className="glass-panel" style={{ padding: '22px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <Wrench size={18} color="#00e676" />
              <span>PROACTIVE RISK MITIGATION PRESCRIPTION</span>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '14px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '0.8rem', color: '#cbd5e1', lineHeight: '1.5' }}>
                {recommended_action}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px' }}>
            <span style={{ fontSize: '0.74rem', color: '#64748b' }}>Calibrated via Gibbs Wave Dynamics</span>
            <button
              onClick={() => {}}
              style={{
                background: '#00e5ff',
                color: '#000',
                border: 'none',
                borderRadius: '6px',
                padding: '8px 14px',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              APPLY SPEED REDUCTION
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
