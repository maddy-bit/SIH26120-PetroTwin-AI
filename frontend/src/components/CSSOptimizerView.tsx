import React, { useEffect, useState } from 'react';
import { Flame } from 'lucide-react';
import { api } from '../services/api';

type CssResult = Awaited<ReturnType<typeof api.simulateCss>>;

export const CSSOptimizerView: React.FC = () => {
  const [steamMass, setSteamMass] = useState(2400);
  const [soakDays, setSoakDays] = useState(6);
  const [projectionDay, setProjectionDay] = useState(90);
  const [result, setResult] = useState<CssResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setResult(null);
    setError(null);
    api.simulateCss(steamMass, soakDays).then((value) => {
      if (!cancelled) setResult(value);
    }).catch((err: unknown) => {
      if (!cancelled) setError(err instanceof Error ? err.message : 'CSS simulation failed.');
    });
    return () => { cancelled = true; };
  }, [steamMass, soakDays]);

  const projected = result?.cooling_projection.find((point) => point.day === projectionDay)
    ?? result?.cooling_projection.reduce((closest, point) => Math.abs(point.day - projectionDay) < Math.abs(closest.day - projectionDay) ? point : closest);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, padding: '24px 20px' }}>
      <div className="glass-panel" style={{ padding: '18px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 800 }}><Flame size={20} /> CSS THERMAL MODEL (SIMULATED)</div>
        <div style={{ fontSize: '.76rem', color: '#52525b', marginTop: 6 }}>Backend temperature projection only. This calculation does not optimize economics, injection pressure, or cycle cutoff.</div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.3fr', gap: 20 }}>
        <div className="glass-panel" style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 20 }}>
          <label>Steam mass: {steamMass} CWE tons<input aria-label="Steam mass" type="range" min={500} max={5000} step={100} value={steamMass} onChange={(e) => setSteamMass(Number(e.target.value))} /></label>
          <label>Soak duration: {soakDays} days<input aria-label="Soak duration" type="range" min={2} max={15} step={1} value={soakDays} onChange={(e) => setSoakDays(Number(e.target.value))} /></label>
          <label>Projection day: {projectionDay}<input aria-label="Projection day" type="range" min={0} max={180} step={5} value={projectionDay} onChange={(e) => setProjectionDay(Number(e.target.value))} /></label>
        </div>
        <div className="glass-panel" style={{ padding: 22 }}>
          {error && <div role="alert" style={{ color: '#991b1b' }}>CSS calculation unavailable: {error}</div>}
          {!result && !error && <div role="status">Calculating thermal response…</div>}
          {result && <>
            <div style={{ fontWeight: 800, marginBottom: 14 }}>BACKEND THERMAL MODEL RESULTS</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,minmax(0,1fr))', gap: 12 }}>
              <Metric label="Estimated post-soak peak temperature" value={`${result.peak_metrics.peak_temperature_c} °C`} />
              <Metric label="Estimated heated radius" value={`${result.peak_metrics.heated_radius_m} m`} />
              <Metric label="Injected heat estimate" value={`${result.peak_metrics.total_heat_injected_gj} GJ`} />
              <Metric label="Retained heat estimate" value={`${result.peak_metrics.heat_retained_post_soak_gj} GJ`} />
              <Metric label={`Projected reservoir temperature, day ${projected?.day ?? projectionDay}`} value={projected ? `${projected.reservoir_temperature_c} °C` : 'Unavailable'} />
            </div>
            <p style={{ marginTop: 16, fontSize: '.78rem', color: '#52525b' }}>Simplified project simulation; literature calibration and field validation have not been established.</p>
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
