import React, { useState } from 'react';
import { Gauge, Sliders, ShieldCheck, AlertTriangle, Zap, Activity } from 'lucide-react';

export const SRPOptimizerView: React.FC = () => {
  const [strokeLength, setStrokeLength] = useState<number>(2.4);
  const [spm, setSpm] = useState<number>(6.5);
  const [viscosity, setViscosity] = useState<number>(1450);

  // Mechanical kinematic and load calculations (API RP 11L)
  const vHorsehead = (Math.PI * strokeLength * spm) / 60.0;
  // Terminal settling speed of lower rod string through viscous fluid:
  const vTerminal = Math.max(0.2, 1900.0 / (viscosity * 0.95 + 10.0));
  const velocityRatio = vHorsehead / vTerminal;
  const rodFloatRisk = Math.min(0.99, Math.max(0.02, 1.0 / (1.0 + Math.exp(-6.5 * (velocityRatio - 0.78)))));
  const isFloating = velocityRatio >= 0.82;

  const pprl = Math.round(13200 + strokeLength * 650 + spm * 220 + viscosity * 0.45);
  const mprl = Math.max(350, Math.round(3900 - (isFloating ? 2400 : viscosity * 0.22)));
  const dispBpd = Math.round(strokeLength * spm * 30.5);
  const pumpEff = Math.max(55.0, parseFloat((92.0 - viscosity * 0.005).toFixed(1)));
  const estProd = Math.round((dispBpd * pumpEff) / 100.0);
  const powerKw = parseFloat((12.5 + strokeLength * 2.1 + spm * 0.8 + viscosity * 0.0018).toFixed(2));
  const kwhBbl = parseFloat(((powerKw * 24.0) / Math.max(1, estProd)).toFixed(2));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '24px 20px' }}>
      {/* Header */}
      <div className="glass-panel" style={{ padding: '18px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Gauge size={20} color="#00e5ff" />
            <span>SUCKER ROD PUMP (SRP) CONTINUOUS MECHANICAL OPTIMIZER</span>
          </div>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8' }}>
            API RP 11L Kinematics, Annular Couette Shear, Downstroke Sinking Margin & Rod-Float Protection
          </div>
        </div>
        <span className={`tech-badge ${isFloating ? 'badge-red' : 'badge-green'}`}>
          {isFloating ? 'ROD FLOATING DETECTED' : 'OPERATING IN SAFE ENVELOPE'}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: '20px' }}>
        {/* SRP Operating Sliders */}
        <div className="glass-panel" style={{ padding: '22px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sliders size={16} color="#00e5ff" />
            <span>SRP SPEED & GEOMETRY CONTROLS</span>
          </div>

          {/* Stroke Length Slider */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '6px' }}>
              <span style={{ color: '#94a3b8' }}>Polished Rod Stroke Length</span>
              <span style={{ color: '#00e5ff', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{strokeLength} m</span>
            </div>
            <input
              type="range"
              min={1.5}
              max={3.0}
              step={0.1}
              value={strokeLength}
              onChange={(e) => setStrokeLength(parseFloat(e.target.value))}
            />
          </div>

          {/* SPM Slider */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '6px' }}>
              <span style={{ color: '#94a3b8' }}>Pumping Speed (SPM)</span>
              <span style={{ color: isFloating ? '#ff334b' : '#00e5ff', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                {spm} SPM (VFD: {(spm * 6.46).toFixed(1)} Hz)
              </span>
            </div>
            <input
              type="range"
              min={2.5}
              max={9.5}
              step={0.1}
              value={spm}
              onChange={(e) => setSpm(parseFloat(e.target.value))}
            />
          </div>

          {/* Simulated Viscosity (Fluid Condition) */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '6px' }}>
              <span style={{ color: '#94a3b8' }}>Fluid Viscosity (Thermal State)</span>
              <span style={{ color: '#ff6d00', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{viscosity} cP</span>
            </div>
            <input
              type="range"
              min={50}
              max={4500}
              step={50}
              value={viscosity}
              onChange={(e) => setViscosity(parseInt(e.target.value))}
            />
          </div>

          {/* Velocity Ratio Visual Gauge */}
          <div style={{ background: 'rgba(0,0,0,0.3)', padding: '12px 14px', borderRadius: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.74rem', marginBottom: '4px' }}>
              <span style={{ color: '#94a3b8' }}>Downstroke Speed vs Terminal Sinking Velocity Ratio</span>
              <span style={{ color: isFloating ? '#ff334b' : '#00e676', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                {velocityRatio.toFixed(2)}x (Limit: 0.82x)
              </span>
            </div>
            <div style={{ height: '6px', background: '#1e293b', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${Math.min(100, (velocityRatio / 1.2) * 100)}%`,
                background: isFloating ? '#ff334b' : '#00e676',
                transition: 'all 0.2s ease'
              }}></div>
            </div>
          </div>
        </div>

        {/* Output Metrics Panel */}
        <div className="glass-panel" style={{ padding: '22px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#fff' }}>
            PREDICTED MECHANICAL & LIFT PERFORMANCE
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Estimated Production</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#00e5ff', fontFamily: 'var(--font-mono)' }}>
                {estProd} bpd
              </div>
              <div style={{ fontSize: '0.68rem', color: '#64748b' }}>Displacement: {dispBpd} bpd • Eff: {pumpEff}%</div>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Rod Floating Risk</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: isFloating ? '#ff334b' : '#00e676', fontFamily: 'var(--font-mono)' }}>
                {(rodFloatRisk * 100).toFixed(1)}%
              </div>
              <div style={{ fontSize: '0.68rem', color: isFloating ? '#ff334b' : '#00e676' }}>
                {isFloating ? 'IMPACT POUNDING ACTIVE' : 'POSITIVE NET DOWN FORCE'}
              </div>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Peak Polished Rod Load</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#fff', fontFamily: 'var(--font-mono)' }}>
                {pprl} lbs
              </div>
              <div style={{ fontSize: '0.68rem', color: '#64748b' }}>MPRL: {mprl} lbs (Structure: 22k lbs)</div>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Electrical Power & Cost</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#ffb300', fontFamily: 'var(--font-mono)' }}>
                {powerKw} kW
              </div>
              <div style={{ fontSize: '0.68rem', color: '#00e676' }}>{kwhBbl} kWh / bbl</div>
            </div>
          </div>

          {/* AI Recommendation Card */}
          <div style={{
            background: 'rgba(0, 229, 255, 0.05)',
            border: '1px solid rgba(0, 229, 255, 0.25)',
            borderRadius: '8px',
            padding: '14px',
            fontSize: '0.76rem',
            color: '#cbd5e1',
            lineHeight: '1.5'
          }}>
            <strong style={{ color: '#00e5ff' }}>AI Pumping Rule:</strong> At {viscosity} cP, maximum allowable speed without rod float is{' '}
            <strong style={{ color: '#00e676' }}>
              {Math.max(3.2, Math.min(7.5, (1.9 / (strokeLength * Math.PI)) * 60 * 0.8)).toFixed(1)} SPM
            </strong>
            . Reducing SPM while extending stroke length preserves displacement while eliminating rod shock!
          </div>
        </div>
      </div>
    </div>
  );
};
