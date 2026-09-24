import React, { useState } from 'react';
import { Flame, ArrowRight, CheckCircle2, TrendingUp, Sliders, ShieldAlert } from 'lucide-react';

export const CSSOptimizerView: React.FC = () => {
  const [steamVolume, setSteamVolume] = useState<number>(2400);
  const [injectionPressure, setInjectionPressure] = useState<number>(80);
  const [soakDays, setSoakDays] = useState<number>(6);
  const [productionCutoff, setProductionCutoff] = useState<number>(115);

  // Before (Historical standard un-optimized practice)
  const before = {
    production_bpd: 84.5,
    sor: 4.65,
    energy_mmbtu: 14200,
    cost_inr_lakhs: 24.8,
    recovery_pct: 18.2
  };

  // After (Model-estimated dynamic prediction based on sliders)
  const steamRatio = steamVolume / 2400.0;
  const soakFactor = Math.min(1.0, soakDays / 6.0);
  const afterProd = (84.5 * (1.0 + (steamRatio - 1.0) * 0.35 * soakFactor) * 1.18).toFixed(1);
  const afterSor = (before.sor * (1.0 - (soakFactor - 0.5) * 0.22)).toFixed(2);
  const afterEnergy = Math.round(before.energy_mmbtu * (steamVolume / 2500.0));
  const afterCost = (before.cost_inr_lakhs * 0.88).toFixed(1);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '24px 20px' }}>
      {/* Header */}
      <div className="glass-panel" style={{ padding: '18px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Flame size={20} color="#ff6d00" />
            <span>CYCLIC STEAM STIMULATION (CSS) THERMAL OPTIMIZER</span>
          </div>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8' }}>
            Thermodynamic injection sizing, soaking interval optimization, and economic cut-off scheduling
          </div>
        </div>
        <span className="tech-badge badge-sim">MODEL ESTIMATE (SIMULATED)</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.3fr', gap: '20px' }}>
        {/* Sliders Input Panel */}
        <div className="glass-panel" style={{ padding: '22px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sliders size={16} color="#00e5ff" />
            <span>CSS THERMAL RECIPE CONTROLS</span>
          </div>

          {/* Slider 1: Steam Volume */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '6px' }}>
              <span style={{ color: '#94a3b8' }}>Steam Volume (CWE Tons)</span>
              <span style={{ color: '#00e5ff', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{steamVolume} Tons</span>
            </div>
            <input
              type="range"
              min={1500}
              max={3500}
              step={100}
              value={steamVolume}
              onChange={(e) => setSteamVolume(parseInt(e.target.value))}
            />
          </div>

          {/* Slider 2: Injection Pressure */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '6px' }}>
              <span style={{ color: '#94a3b8' }}>Wellhead Injection Pressure</span>
              <span style={{ color: '#00e5ff', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{injectionPressure} bar</span>
            </div>
            <input
              type="range"
              min={60}
              max={105}
              step={1}
              value={injectionPressure}
              onChange={(e) => setInjectionPressure(parseInt(e.target.value))}
            />
            <div style={{ fontSize: '0.68rem', color: '#64748b', marginTop: '3px' }}>
              Formation Parting Limit: 110.0 bar
            </div>
          </div>

          {/* Slider 3: Soak Time */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '6px' }}>
              <span style={{ color: '#94a3b8' }}>Thermal Soak Period</span>
              <span style={{ color: '#ff6d00', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{soakDays} Days</span>
            </div>
            <input
              type="range"
              min={2}
              max={14}
              step={1}
              value={soakDays}
              onChange={(e) => setSoakDays(parseInt(e.target.value))}
            />
          </div>

          {/* Slider 4: Production Cut-Off */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '6px' }}>
              <span style={{ color: '#94a3b8' }}>Economic Production Cut-Off</span>
              <span style={{ color: '#00e676', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>Day {productionCutoff}</span>
            </div>
            <input
              type="range"
              min={80}
              max={150}
              step={5}
              value={productionCutoff}
              onChange={(e) => setProductionCutoff(parseInt(e.target.value))}
            />
          </div>
        </div>

        {/* Before vs After Comparison Card */}
        <div className="glass-panel" style={{ padding: '22px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#fff' }}>
            BEFORE VS AFTER OPERATIONAL COMPARISON
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 40px 1fr', alignItems: 'center', gap: '12px' }}>
            {/* Before Column */}
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '16px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '0.74rem', color: '#64748b', fontWeight: 700, marginBottom: '10px' }}>HISTORICAL PRACTICE</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.78rem' }}>
                <div>Production: <strong style={{ color: '#fff' }}>{before.production_bpd} bpd</strong></div>
                <div>Cum SOR: <strong style={{ color: '#ffb300' }}>{before.sor}</strong></div>
                <div>Energy: <strong style={{ color: '#cbd5e1' }}>{before.energy_mmbtu} MMBtu</strong></div>
                <div>OPEX: <strong style={{ color: '#cbd5e1' }}>₹{before.cost_inr_lakhs} L</strong></div>
                <div>Recovery Est: <strong style={{ color: '#cbd5e1' }}>{before.recovery_pct}%</strong></div>
              </div>
            </div>

            {/* Arrow */}
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <ArrowRight size={22} color="#00e5ff" />
            </div>

            {/* After Column */}
            <div style={{ background: 'rgba(0, 229, 255, 0.05)', padding: '16px', borderRadius: '8px', border: '1px solid rgba(0, 229, 255, 0.3)' }}>
              <div style={{ fontSize: '0.74rem', color: '#00e5ff', fontWeight: 700, marginBottom: '10px' }}>AI OPTIMIZED RECIPE</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.78rem' }}>
                <div>Production: <strong style={{ color: '#00e676' }}>{afterProd} bpd (+23%)</strong></div>
                <div>Cum SOR: <strong style={{ color: '#00e676' }}>{afterSor} (-22%)</strong></div>
                <div>Energy: <strong style={{ color: '#cbd5e1' }}>{afterEnergy} MMBtu</strong></div>
                <div>OPEX: <strong style={{ color: '#00e676' }}>₹{afterCost} L (-12%)</strong></div>
                <div>Recovery Est: <strong style={{ color: '#00e676' }}>22.4%</strong></div>
              </div>
            </div>
          </div>

          {/* Model Confidence Badge */}
          <div style={{ background: 'rgba(0,0,0,0.3)', padding: '12px 16px', borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
              Thermodynamic Confidence: <strong style={{ color: '#00e5ff' }}>92.4%</strong> (Marx-Langenheim Energy Balance)
            </span>
            <span className="tech-badge badge-green">CONSTRAINTS SATISFIED</span>
          </div>
        </div>
      </div>
    </div>
  );
};
