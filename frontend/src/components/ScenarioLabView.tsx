import React, { useEffect, useState } from 'react';
import { Sliders } from 'lucide-react';
import { api } from '../services/api';
import { ScenarioEvaluation } from '../types/petro';

export const ScenarioLabView: React.FC<{ selectedWell: string }> = ({ selectedWell }) => {
  const [steamVol, setSteamVol] = useState(2500);
  const [soakDays, setSoakDays] = useState(7);
  const [spm, setSpm] = useState(5.5);
  const [stroke, setStroke] = useState(2.8);
  const [productionCutoff, setProductionCutoff] = useState(115);
  const [result, setResult] = useState<ScenarioEvaluation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setResult(null);
    setError(null);
    api.runScenario({
      well_id: selectedWell,
      steam_volume: steamVol,
      soak_time: soakDays,
      production_cutoff: productionCutoff,
      stroke_length: stroke,
      spm
    }).then((evaluation) => {
      if (!cancelled) setResult(evaluation);
    }).catch((err: unknown) => {
      if (!cancelled) setError(err instanceof Error ? err.message : 'Scenario evaluation failed.');
    });
    return () => { cancelled = true; };
  }, [selectedWell, steamVol, soakDays, spm, stroke, productionCutoff]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, padding: '24px 20px' }}>
      <div className="glass-panel" style={{ padding: '18px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 800 }}><Sliders size={20} /> WHAT-IF SCENARIO EVALUATION</div>
        <div style={{ fontSize: '.76rem', color: '#52525b', marginTop: 6 }}>Scenario estimates use the simplified synthetic model. Production horizon affects estimated cycle oil and SOR. Injection pressure is unsupported; fixed steam properties are assumed. VFD frequency is derived from SPM.</div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1.3fr', gap: 20 }}>
        <div className="glass-panel" style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 18 }}>
          <label>Steam mass: {steamVol} CWE tons<input aria-label="Steam mass" type="range" min={500} max={5000} step={100} value={steamVol} onChange={(e) => setSteamVol(Number(e.target.value))} /></label>
          <label>Soak duration: {soakDays} days<input aria-label="Soak duration" type="range" min={2} max={15} step={1} value={soakDays} onChange={(e) => setSoakDays(Number(e.target.value))} /></label>
          <label>Pumping speed: {spm.toFixed(1)} SPM<input aria-label="Pumping speed" type="range" min={2} max={10.5} step={0.1} value={spm} onChange={(e) => setSpm(Number(e.target.value))} /></label>
          <label>Stroke length: {stroke.toFixed(1)} m<input aria-label="Stroke length" type="range" min={1.5} max={3} step={0.1} value={stroke} onChange={(e) => setStroke(Number(e.target.value))} /></label>
          <label>Production horizon: {productionCutoff} days<input aria-label="Production horizon" type="range" min={30} max={180} step={5} value={productionCutoff} onChange={(e) => setProductionCutoff(Number(e.target.value))} /></label>
        </div>
        <div className="glass-panel" style={{ padding: 22 }}>
          {error && <div role="alert" style={{ color: '#991b1b' }}>Scenario unavailable: {error}</div>}
          {!result && !error && <div role="status">Evaluating scenario…</div>}
          {result && <>
            <div style={{ fontWeight: 800, marginBottom: 14 }}>BACKEND SCENARIO RESULTS</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,minmax(0,1fr))', gap: 12 }}>
              <Metric label="Estimated production" value={`${result.production_bpd} bpd`} />
              <Metric label="Estimated cycle SOR" value={String(result.sor)} />
              <Metric label={`Estimated cycle oil (${result.production_cutoff_days} days)`} value={`${result.estimated_cycle_oil_bbl} bbl`} />
              <Metric label="Specific energy estimate" value={`${result.energy_kwh_bbl} kWh/bbl`} />
              <Metric label="Modeled rod-floating risk score" value={`${(result.failure_risk * 100).toFixed(1)}%`} />
              <Metric label="Modeled fluid viscosity" value={`${result.viscosity_cp} cP`} />
              <Metric label="Post-soak heat retained" value={`${result.heat_retained_post_soak_gj} GJ`} />
              <Metric label="Estimated heated radius" value={`${result.heated_radius_m} m`} />
              <Metric label="Peak polished rod load" value={`${result.peak_polished_rod_load_lbs} lb`} />
            </div>
            <div role="status" style={{ marginTop: 14, fontWeight: 700, color: result.is_feasible ? '#166534' : '#991b1b' }}>
              {result.is_feasible ? 'No implemented constraint violation was detected.' : `Constraint violations: ${result.violations.join('; ')}`}
            </div>
            <div style={{ marginTop: 14, padding: 12, border: '1px solid #d97706', background: '#fffbeb' }}>
              <strong style={{ fontSize: '.75rem' }}>COUPLED PHYSICS TRACE · SIMULATION ONLY</strong>
              <div style={{ fontSize: '.72rem', color: '#52525b', marginTop: 5 }}>
                {result.coupled_model_id} · {result.model_validation_status} · Field eligible: {result.field_eligible ? 'Yes' : 'No'}
              </div>
              <ol style={{ margin: '8px 0 0', paddingLeft: 18, fontSize: '.74rem' }}>
                {result.coupling_chain.map((stage) => <li key={stage.stage}>{stage.stage.replaceAll('_', ' ')}</li>)}
              </ol>
            </div>
            <p style={{ marginTop: 12, fontSize: '.78rem', color: '#52525b' }}>Model estimate only. The CSS → thermal cooling → viscosity → SRP chain is explicit and traceable, but not calibrated or field validated. Feasibility covers only constraints implemented by the current simulator.</p>
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
