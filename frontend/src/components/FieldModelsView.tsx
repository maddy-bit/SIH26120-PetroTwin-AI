import React, { useCallback, useEffect, useState } from 'react';
import { ApiError, api } from '../services/api';

type ModelRecord = {
  model_id: string;
  lifecycle_status: string;
  model_family: string;
  horizon_days: number;
  sample_count: number;
  metrics: {
    test?: { mae?: number; rmse?: number; bias?: number };
    persistence_baseline_test?: { mae?: number };
    test_mae_improvement_vs_persistence?: number | null;
    promotable?: boolean;
    chronological_split?: Record<string, string>;
  };
  dataset_fingerprint: string;
  created_at: string;
  approved_at?: string | null;
  approved_by?: string | null;
};

function dateValue(date: Date): string {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function FieldModelsView({ selectedWell, dataMode }: { selectedWell: string; dataMode: string }) {
  const [models, setModels] = useState<ModelRecord[]>([]);
  const [role, setRole] = useState('');
  const [horizon, setHorizon] = useState<1 | 7 | 30>(7);
  const [startAt, setStartAt] = useState(() => dateValue(new Date(Date.now() - 120 * 86400000)));
  const [endAt, setEndAt] = useState(() => dateValue(new Date()));
  const [minSamples, setMinSamples] = useState(30);
  const [maxAge, setMaxAge] = useState(72);
  const [training, setTraining] = useState(false);
  const [busyModel, setBusyModel] = useState('');
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [forecast, setForecast] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!selectedWell) {
      setModels([]);
      return;
    }
    const response = await api.getFieldModels(selectedWell);
    setModels(response.models as ModelRecord[]);
  }, [selectedWell]);

  useEffect(() => {
    let active = true;
    Promise.all([
      api.getHealth().then((health) => health.auth_required ? api.getCurrentUser() : null),
      selectedWell ? api.getFieldModels(selectedWell) : Promise.resolve({ models: [] }),
    ]).then(([session, registry]) => {
      if (!active) return;
      setRole(String(session?.user?.role ?? ''));
      setModels(registry.models as ModelRecord[]);
    }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : 'Unable to load field model registry.');
    });
    return () => { active = false; };
  }, [selectedWell]);

  const handleTrain = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedWell) return;
    setTraining(true);
    setError('');
    setResult(null);
    setForecast(null);
    try {
      const response = await api.trainFieldModel({
        well_id: selectedWell,
        horizon_days: horizon,
        start_at: `${startAt}T00:00:00Z`,
        end_at: `${endAt}T23:59:59Z`,
        min_samples: minSamples,
        max_feature_age_hours: maxAge,
      });
      setResult(response);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Field model training failed.');
    } finally {
      setTraining(false);
    }
  };

  const handlePromote = async (modelId: string) => {
    setBusyModel(modelId);
    setError('');
    try {
      await api.promoteFieldModel(modelId);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Model promotion failed.');
    } finally {
      setBusyModel('');
    }
  };

  const handlePredict = async (horizonDays: 1 | 7 | 30) => {
    setBusyModel(`predict-${horizonDays}`);
    setError('');
    try {
      setForecast(await api.predictFieldModel(selectedWell, horizonDays));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Field prediction failed.');
    } finally {
      setBusyModel('');
    }
  };

  const activeHorizons = new Set(models.filter((item) => item.lifecycle_status === 'ACTIVE').map((item) => item.horizon_days));

  return <section style={{ padding: 24, display: 'grid', gap: 18 }}>
    <header>
      <p style={{ margin: 0, fontSize: '.7rem', fontWeight: 800, letterSpacing: '.12em', color: '#2563eb' }}>MEASURED-DATA MODEL LIFECYCLE</p>
      <h1 style={{ margin: '6px 0' }}>Field Production Models</h1>
      <p style={{ margin: 0, maxWidth: 950, color: '#52525b', lineHeight: 1.55 }}>
        Train a candidate from quality-approved measurements, inspect untouched chronological test metrics, then require an administrator to promote an artifact. No model is automatically activated.
      </p>
    </header>

    {dataMode !== 'FIELD' && <div role="alert" style={{ padding: 14, border: '1px solid #d97706', background: '#fffbeb' }}>
      Field training and measured-data inference are disabled in simulation mode. Switch the backend to field mode and select a registered field well.
    </div>}

    <div style={{ border: '1px solid #d4d4d8', borderRadius: 10, padding: 18, background: '#fff' }}>
      <h2 style={{ marginTop: 0, fontSize: '1.05rem' }}>Create training candidate</h2>
      <form onSubmit={handleTrain} style={{ display: 'grid', gap: 12, maxWidth: 920 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 12 }}>
          <label style={{ display: 'grid', gap: 5, fontSize: '.82rem' }}>Forecast horizon
            <select value={horizon} onChange={(event) => setHorizon(Number(event.target.value) as 1 | 7 | 30)}>
              <option value={1}>1 day</option><option value={7}>7 days</option><option value={30}>30 days</option>
            </select>
          </label>
          <label style={{ display: 'grid', gap: 5, fontSize: '.82rem' }}>Start date
            <input type="date" value={startAt} onChange={(event) => setStartAt(event.target.value)} required />
          </label>
          <label style={{ display: 'grid', gap: 5, fontSize: '.82rem' }}>End date
            <input type="date" value={endAt} onChange={(event) => setEndAt(event.target.value)} required />
          </label>
          <label style={{ display: 'grid', gap: 5, fontSize: '.82rem' }}>Minimum examples
            <input type="number" min={30} max={5000} value={minSamples} onChange={(event) => setMinSamples(Number(event.target.value))} />
          </label>
          <label style={{ display: 'grid', gap: 5, fontSize: '.82rem' }}>Maximum feature age (hours)
            <input type="number" min={1} max={720} value={maxAge} onChange={(event) => setMaxAge(Number(event.target.value))} />
          </label>
        </div>
        <button type="submit" disabled={training || !selectedWell || dataMode !== 'FIELD' || !startAt || !endAt || endAt <= startAt}
          style={{ justifySelf: 'start', padding: '10px 16px', border: 0, borderRadius: 7, background: '#18181b', color: '#fff', fontWeight: 700 }}>
          {training ? 'Building dataset and evaluating…' : 'Train measured-data candidate'}
        </button>
      </form>
      <p style={{ margin: '12px 0 0', color: '#71717a', fontSize: '.76rem', lineHeight: 1.5 }}>
        Requires VALID temperature, bottomhole pressure, SPM, stroke and oil-rate records. Features are selected at or before each origin time; future oil-rate observations form the target. Minimum split: 18 train / 6 validation / 6 test. Synthetic demo wells are rejected.
      </p>
    </div>

    {error && <div role="alert" style={{ padding: 12, color: '#991b1b', background: '#fef2f2', border: '1px solid #fecaca' }}>{error}</div>}

    {result && <div style={{ padding: 14, border: '1px solid #2563eb', background: '#eff6ff', borderRadius: 8 }}>
      <strong>Training run completed</strong>
      <div style={{ fontSize: '.8rem', marginTop: 6 }}>Model: {String((result.model as ModelRecord)?.model_id)} · Status: {String((result.model as ModelRecord)?.lifecycle_status)}</div>
      <p style={{ marginBottom: 0, fontSize: '.78rem' }}>Field validation is still NOT ESTABLISHED. The model remains a review candidate; it was not automatically activated.</p>
    </div>}

    <div style={{ border: '1px solid #d4d4d8', borderRadius: 10, padding: 18, background: '#fff' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <h2 style={{ margin: 0, fontSize: '1.05rem' }}>Model registry · {selectedWell || 'No well selected'}</h2>
        <button type="button" onClick={() => void load().catch((reason) => setError(String(reason)))} disabled={!selectedWell}>Refresh</button>
      </div>
      {models.length === 0 ? <p style={{ color: '#71717a', fontSize: '.85rem' }}>No trained field models are registered for this well.</p> :
        <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
          {models.map((model) => <article key={model.model_id} style={{ border: '1px solid #e4e4e7', borderRadius: 8, padding: 14, display: 'grid', gap: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
              <strong>{model.horizon_days}-day · {model.model_family}</strong>
              <span style={{ fontSize: '.72rem', fontWeight: 800, color: model.lifecycle_status === 'ACTIVE' ? '#166534' : model.lifecycle_status === 'CANDIDATE_REVIEW_REQUIRED' ? '#1d4ed8' : '#71717a' }}>{model.lifecycle_status}</span>
            </div>
            <div style={{ fontSize: '.76rem', color: '#52525b' }}>{model.sample_count} paired examples · created {new Date(model.created_at).toLocaleString()}</div>
            <div style={{ fontSize: '.76rem' }}>
              Test MAE: {model.metrics.test?.mae?.toFixed(3) ?? '—'} bbl/day · Persistence MAE: {model.metrics.persistence_baseline_test?.mae?.toFixed(3) ?? '—'} bbl/day · Improvement: {model.metrics.test_mae_improvement_vs_persistence == null ? '—' : `${(model.metrics.test_mae_improvement_vs_persistence * 100).toFixed(1)}%`}
            </div>
            <div style={{ fontSize: '.68rem', color: '#71717a', wordBreak: 'break-all' }}>Dataset fingerprint: {model.dataset_fingerprint}</div>
            {role === 'admin' && model.lifecycle_status === 'CANDIDATE_REVIEW_REQUIRED' &&
              <button type="button" onClick={() => void handlePromote(model.model_id)} disabled={!!busyModel}
                style={{ justifySelf: 'start', padding: '8px 12px', border: 0, borderRadius: 7, background: '#166534', color: '#fff', fontWeight: 700 }}>
                {busyModel === model.model_id ? 'Verifying artifact…' : 'Review & promote model'}
              </button>}
          </article>)}
        </div>}
    </div>

    <div style={{ border: '1px solid #d4d4d8', borderRadius: 10, padding: 18, background: '#fff' }}>
      <h2 style={{ marginTop: 0, fontSize: '1.05rem' }}>Promoted model inference</h2>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {([1, 7, 30] as const).map((days) => <button key={days} type="button" disabled={!activeHorizons.has(days) || !!busyModel || dataMode !== 'FIELD'}
          onClick={() => void handlePredict(days)}>{busyModel === `predict-${days}` ? 'Running…' : `Predict ${days} day`}</button>)}
      </div>
      {forecast && <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', background: '#f4f4f5', padding: 12, borderRadius: 8, fontSize: '.76rem' }}>{JSON.stringify(forecast, null, 2)}</pre>}
      <p style={{ marginBottom: 0, fontSize: '.75rem', color: '#71717a' }}>Prediction requires a promoted model and fresh VALID measurements. The response includes source measurement IDs. It is decision support, not field validation or an operating setpoint.</p>
    </div>
  </section>;
}
