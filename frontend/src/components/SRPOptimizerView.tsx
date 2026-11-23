import React, { useEffect, useState } from 'react';
import { Gauge, Sliders } from 'lucide-react';
import { api } from '../services/api';
import { SRPPerformance } from '../types/petro';

export const SRPOptimizerView: React.FC = () => {
  const [strokeLength, setStrokeLength] = useState(2.4);
  const [spm, setSpm] = useState(6.5);
  const [viscosity, setViscosity] = useState(1450);
  const [performance, setPerformance] = useState<SRPPerformance | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setPerformance(null);
    setError(null);
    api.simulateSrp(strokeLength, spm, viscosity).then((result) => {
      if (!cancelled) setPerformance(result.performance);
    }).catch((err: unknown) => {
      if (!cancelled) setError(err instanceof Error ? err.message : 'SRP simulation failed.');
    });
    return () => { cancelled = true; };
  }, [strokeLength, spm, viscosity]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, padding: '24px 20px' }}>
      <div className="glass-panel" style={{ padding: '18px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 800 }}><Gauge size={20} /> SRP MODEL RESPONSE (SIMULATED)</div>
        <div style={{ fontSize: '.76rem', color: '#52525b', marginTop: 6 }}>Approximate mechanics calculation; outputs are not calibrated to field measurements.</div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: 20 }}>
        <div className="glass-panel" style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div style={{ fontWeight: 800, display: 'flex', alignItems: 'center', gap: 8 }}><Sliders size={16} /> INPUT ASSUMPTIONS</div>
          <label>Stroke length: {strokeLength.toFixed(1)} m<input aria-label="Stroke length" type="range" min={1.5} max={3} step={0.1} value={strokeLength} onChange={(e) => setStrokeLength(Number(e.target.value))} /></label>
          <label>Pumping speed: {spm.toFixed(1)} SPM<input aria-label="Pumping speed" type="range" min={2} max={10.5} step={0.1} value={spm} onChange={(e) => setSpm(Number(e.target.value))} /></label>
          <label>Assumed fluid viscosity: {viscosity} cP<input aria-label="Assumed fluid viscosity" type="range" min={50} max={4500} step={50} value={viscosity} onChange={(e) => setViscosity(Number(e.target.value))} /></label>
          <small>Viscosity is an operator-entered scenario assumption for this calculation.</small>
        </div>
        <div className="glass-panel" style={{ padding: 22 }}>
          {error && <div role="alert" style={{ color: '#991b1b' }}>SRP calculation unavailable: {error}</div>}
          {!performance && !error && <div role="status">Calculating SRP response…</div>}
          {performance && <>
            <div style={{ fontWeight: 800, marginBottom: 14 }}>BACKEND CALCULATION RESULTS</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,minmax(0,1fr))', gap: 12 }}>
              <Metric label="Estimated displacement-limited rate" value={`${performance.estimated_production_bpd} bpd`} />
              <Metric label="Modeled rod-floating risk score" value={`${(performance.rod_floating_risk * 100).toFixed(1)}%`} />
              <Metric label="Peak polished rod load" value={`${performance.pprl_lbs} lb`} />
              <Metric label="Minimum polished rod load" value={`${performance.mprl_lbs} lb`} />
              <Metric label="Electrical power estimate" value={`${performance.electrical_power_kw} kW`} />
              <Metric label="Specific energy estimate" value={`${performance.kwh_per_barrel} kWh/bbl`} />
            </div>
            <p style={{ marginTop: 16, fontSize: '.78rem', color: '#52525b' }}>
              {performance.rod_floating_detected ? 'The simplified model flags a rod-floating condition for these inputs.' : 'The simplified model does not flag rod floating for these inputs.'} This is not a calibrated probability or an operating instruction.
            </p>
          </>}
        </div>
      </div>
    </div>
  );
};

const Metric: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div style={{ background: '#f8f9fa', padding: 12, border: '1px solid #18181b' }}>
    <div style={{ fontSize: '.72rem', color: '#52525b' }}>{label}</div>
    <div style={{ fontSize: '1.1rem', fontWeight: 800 }}>{value}</div>
  </div>
);
