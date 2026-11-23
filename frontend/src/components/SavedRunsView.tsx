import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../services/api';
import { SavedAnalysisRun } from '../types/petro';

type RunFilter = 'all' | 'production_forecast' | 'optimization';

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isSavedRun(value: unknown): value is SavedAnalysisRun {
  if (!isObject(value)) return false;
  return typeof value.run_id === 'string'
    && value.run_id.length > 0
    && typeof value.well_id === 'string'
    && typeof value.kind === 'string'
    && typeof value.created_at === 'string'
    && Number.isFinite(Date.parse(value.created_at))
    && isObject(value.result);
}

function kindLabel(kind: string): string {
  if (kind === 'production_forecast') return 'Production forecast';
  if (kind === 'optimization') return 'Joint optimization';
  return `Other run (${kind})`;
}

export const SavedRunsView: React.FC<{ wellId: string }> = ({ wellId }) => {
  const [runs, setRuns] = useState<SavedAnalysisRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [filter, setFilter] = useState<RunFilter>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [invalidCount, setInvalidCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setRuns([]);
    setSelectedRunId(null);
    api.getAnalysisRuns(wellId, 100).then((response) => {
      const rawRuns: unknown = response.runs;
      if (!Array.isArray(rawRuns)) throw new Error('The saved-run response has an invalid format.');
      const validRuns = rawRuns.filter(isSavedRun);
      if (!cancelled) {
        setRuns(validRuns);
        setInvalidCount(rawRuns.length - validRuns.length);
        setSelectedRunId(validRuns[0]?.run_id ?? null);
      }
    }).catch((err: unknown) => {
      if (!cancelled) {
        setRuns([]);
        setError(err instanceof Error ? err.message : 'Saved-run history could not be loaded.');
      }
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [wellId]);

  const visibleRuns = useMemo(
    () => runs.filter((run) => filter === 'all' || run.kind === filter),
    [runs, filter]
  );
  const selectedRun = visibleRuns.find((run) => run.run_id === selectedRunId) ?? visibleRuns[0] ?? null;
  const outputs = selectedRun
    ? Object.fromEntries(Object.entries(selectedRun.result).filter(([key]) => key !== 'inputs'))
    : null;

  return (
    <section style={{ padding: 24, display: 'grid', gap: 16 }} aria-labelledby="saved-runs-title">
      <div className="glass-panel" style={{ padding: 20 }}>
        <h1 id="saved-runs-title" style={{ margin: 0, fontSize: '1.2rem' }}>Saved analysis runs</h1>
        <p style={{ margin: '6px 0 0', color: '#52525b', fontSize: '.82rem' }}>
          Persisted forecast and optimization results for {wellId}. Results are retrieved from the backend analysis history.
        </p>
      </div>

      {loading && <div role="status" className="glass-panel" style={{ padding: 20 }}>Loading saved runs…</div>}
      {!loading && error && <div role="alert" className="glass-panel" style={{ padding: 20, color: '#991b1b' }}>Could not load saved runs: {error}</div>}
      {!loading && !error && invalidCount > 0 && (
        <div role="status" className="glass-panel" style={{ padding: 12, color: '#854d0e' }}>
          Skipped {invalidCount} invalid saved {invalidCount === 1 ? 'record' : 'records'}; valid records remain available below.
        </div>
      )}
      {!loading && !error && runs.length === 0 && (
        <div role="status" className="glass-panel" style={{ padding: 20 }}>
          No saved forecast or optimization runs for {wellId}. Generate a forecast or run the optimizer to create history.
        </div>
      )}

      {!loading && !error && runs.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, .8fr) minmax(320px, 1.5fr)', gap: 16 }}>
          <div className="glass-panel" style={{ padding: 16, display: 'grid', alignContent: 'start', gap: 10 }}>
            <label style={{ display: 'grid', gap: 5, fontSize: '.8rem', fontWeight: 700 }}>
              Run type
              <select aria-label="Filter saved runs by type" value={filter} onChange={(event) => setFilter(event.target.value as RunFilter)}>
                <option value="all">All types</option>
                <option value="production_forecast">Forecasts</option>
                <option value="optimization">Optimizations</option>
              </select>
            </label>
            {visibleRuns.length === 0 && <p role="status">No runs match this type.</p>}
            {visibleRuns.map((run) => (
              <button
                type="button"
                key={run.run_id}
                aria-pressed={selectedRun?.run_id === run.run_id}
                onClick={() => setSelectedRunId(run.run_id)}
                style={{ textAlign: 'left', padding: 12, border: '1px solid #18181b', background: selectedRun?.run_id === run.run_id ? '#eff6ff' : '#fff', cursor: 'pointer' }}
              >
                <strong>{kindLabel(run.kind)}</strong>
                <div style={{ fontSize: '.75rem', marginTop: 4 }}>{new Date(run.created_at).toLocaleString()}</div>
                <div style={{ fontSize: '.72rem', color: '#52525b', marginTop: 3 }}>{run.well_id} · {run.source_mode || 'source mode unavailable'}</div>
              </button>
            ))}
          </div>

          {selectedRun && <article className="glass-panel" style={{ padding: 18, minWidth: 0 }}>
            <h2 style={{ margin: '0 0 6px', fontSize: '1rem' }}>{kindLabel(selectedRun.kind)}</h2>
            <div style={{ fontSize: '.78rem', color: '#52525b', overflowWrap: 'anywhere' }}>
              Well: {selectedRun.well_id} · Run ID: {selectedRun.run_id} · {new Date(selectedRun.created_at).toLocaleString()} · {selectedRun.source_mode || 'source mode unavailable'}
            </div>
            <h3 style={{ margin: '18px 0 8px', fontSize: '.9rem' }}>Inputs</h3>
            {isObject(selectedRun.result.inputs)
              ? <pre style={jsonStyle}>{JSON.stringify(selectedRun.result.inputs, null, 2)}</pre>
              : <p>Inputs were not recorded for this run (likely created before input provenance was added).</p>}
            <h3 style={{ margin: '18px 0 8px', fontSize: '.9rem' }}>Outputs</h3>
            <pre style={jsonStyle}>{JSON.stringify(outputs, null, 2)}</pre>
          </article>}
        </div>
      )}
    </section>
  );
};

const jsonStyle: React.CSSProperties = {
  margin: 0,
  padding: 12,
  maxHeight: 520,
  overflow: 'auto',
  background: '#f8fafc',
  border: '1px solid #d4d4d8',
  fontSize: '.72rem',
  whiteSpace: 'pre-wrap',
  overflowWrap: 'anywhere'
};
