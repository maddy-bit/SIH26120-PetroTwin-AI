import React, { useState } from 'react';
import { Sliders, ArrowRight, Check, AlertCircle, RefreshCw, Sparkles } from 'lucide-react';

export const ScenarioLabView: React.FC = () => {
  const [steamVol, setSteamVol] = useState<number>(2500);
  const [soakDays, setSoakDays] = useState<number>(7);
  const [injPressure, setInjPressure] = useState<number>(82);
  const [spm, setSpm] = useState<number>(5.5);
  const [stroke, setStroke] = useState<number>(2.8);
  const [vfd, setVfd] = useState<number>(35.5);

  // Baseline Current State
  const current = {
    prod: 84.5,
    sor: 4.65,
    energy: 2.35,
    cost: 18.5,
    risk: 0.38,
    recovery: 18.2
  };

  // Proposed Evaluation
  const vHorsehead = (Math.PI * stroke * spm) / 60.0;
  const propRisk = vHorsehead > 0.85 ? 0.75 : 0.08;
  const propProd = (stroke * spm * 29.5 * (1.0 - propRisk * 0.25)).toFixed(1);
  const propSor = (steamVol / (parseFloat(propProd) * 120 * 0.82) * 6.29).toFixed(2);
  const propEnergy = (1.45 + (spm / 7.0) * 0.4).toFixed(2);
  const propCost = (16.2).toFixed(1);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '24px 20px' }}>
      {/* Header */}
      <div className="glass-panel" style={{ padding: '18px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sliders size={20} color="#00e5ff" />
            <span>INTERACTIVE WHAT-IF SCENARIO LAB</span>
          </div>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8' }}>
            Perturb engineering setpoints across CSS injection and SRP pumping to immediately project operational deltas
          </div>
        </div>
        <span className="tech-badge badge-cyan">INSTANT NUMERICAL SOLVER</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1.3fr', gap: '20px' }}>
        {/* Sliders Box */}
        <div className="glass-panel" style={{ padding: '22px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#fff' }}>PROPOSED OPERATING HYPOTHESIS</div>

          {/* Steam Volume */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', marginBottom: '4px' }}>
              <span style={{ color: '#94a3b8' }}>Steam Volume (Tons)</span>
              <span style={{ color: '#00e5ff', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{steamVol} T</span>
            </div>
            <input type="range" min={1800} max={3200} step={100} value={steamVol} onChange={(e) => setSteamVol(parseInt(e.target.value))} />
          </div>

          {/* Soak Time */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', marginBottom: '4px' }}>
              <span style={{ color: '#94a3b8' }}>Soak Time (Days)</span>
              <span style={{ color: '#ff6d00', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{soakDays} Days</span>
            </div>
            <input type="range" min={2} max={14} step={1} value={soakDays} onChange={(e) => setSoakDays(parseInt(e.target.value))} />
          </div>

          {/* Injection Pressure */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', marginBottom: '4px' }}>
              <span style={{ color: '#94a3b8' }}>Injection Pressure (bar)</span>
              <span style={{ color: '#00e5ff', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{injPressure} bar</span>
            </div>
            <input type="range" min={65} max={105} step={1} value={injPressure} onChange={(e) => setInjPressure(parseInt(e.target.value))} />
          </div>

          {/* SPM */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', marginBottom: '4px' }}>
              <span style={{ color: '#94a3b8' }}>Pumping Speed (SPM)</span>
              <span style={{ color: propRisk > 0.4 ? '#ff334b' : '#00e676', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{spm} SPM</span>
            </div>
            <input type="range" min={2.5} max={9.5} step={0.1} value={spm} onChange={(e) => {
              const val = parseFloat(e.target.value);
              setSpm(val);
              setVfd(parseFloat((val * 6.46).toFixed(1)));
            }} />
          </div>

          {/* Stroke Length */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', marginBottom: '4px' }}>
              <span style={{ color: '#94a3b8' }}>Stroke Length (m)</span>
              <span style={{ color: '#00e5ff', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{stroke} m</span>
            </div>
            <input type="range" min={1.5} max={3.0} step={0.1} value={stroke} onChange={(e) => setStroke(parseFloat(e.target.value))} />
          </div>
        </div>

        {/* Comparison Result Grid */}
        <div className="glass-panel" style={{ padding: '22px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#fff' }}>CURRENT VS PROPOSED DELTAS</div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
            {/* Metric 1 */}
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Oil Production</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#fff', fontFamily: 'var(--font-mono)' }}>
                {propProd} bpd
              </div>
              <div style={{ fontSize: '0.68rem', color: '#00e676', marginTop: '2px' }}>
                {parseFloat(propProd) > current.prod ? `+${(parseFloat(propProd) - current.prod).toFixed(1)} bpd gain` : 'Decrease'}
              </div>
            </div>

            {/* Metric 2 */}
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Steam-Oil Ratio</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#ffb300', fontFamily: 'var(--font-mono)' }}>
                {propSor}
              </div>
              <div style={{ fontSize: '0.68rem', color: '#00e676', marginTop: '2px' }}>
                vs {current.sor} baseline
              </div>
            </div>

            {/* Metric 3 */}
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Failure Risk</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: propRisk > 0.4 ? '#ff334b' : '#00e676', fontFamily: 'var(--font-mono)' }}>
                {(propRisk * 100).toFixed(0)}%
              </div>
              <div style={{ fontSize: '0.68rem', color: propRisk > 0.4 ? '#ff334b' : '#00e676', marginTop: '2px' }}>
                {propRisk > 0.4 ? 'UNSAFE SETPOINT' : 'SAFE ENVELOPE'}
              </div>
            </div>
          </div>

          {/* Trade-off summary */}
          <div style={{
            background: 'rgba(0,0,0,0.3)',
            borderRadius: '8px',
            padding: '16px',
            fontSize: '0.78rem',
            color: '#cbd5e1',
            lineHeight: '1.5'
          }}>
            <strong style={{ color: '#00e5ff' }}>What-If Synthesis:</strong> Running at {spm} SPM with {stroke}m stroke length produces {propProd} bpd. 
            {propRisk > 0.4 ? (
              <span style={{ color: '#ff334b' }}> Warning: Downstroke speed exceeds sinking capacity, leading to severe rod float!</span>
            ) : (
              <span style={{ color: '#00e676' }}> Operates cleanly within the positive sinking force margin, protecting against parted rod failures while reducing SOR to {propSor}.</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
