import React, { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../services/api';
import { WellSummary } from '../types/petro';
import { OperationalDataWorkspace } from './OperationalDataWorkspace';

const residualHistogram = (series: Array<Record<string, unknown>>) => {
  const residuals = series.map(row => row.calibrated_residual).filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
  if (!residuals.length) return [];
  const min = Math.min(...residuals); const max = Math.max(...residuals);
  const binCount = Math.max(1, Math.min(10, Math.ceil(Math.sqrt(residuals.length))));
  const width = max === min ? 1 : (max - min) / binCount;
  const bins = Array.from({ length: binCount }, (_, index) => ({
    residual_bin: `${(min + index * width).toFixed(2)} to ${(index === binCount - 1 ? max : min + (index + 1) * width).toFixed(2)}`,
    observations: 0,
  }));
  residuals.forEach(value => { const index = max === min ? 0 : Math.min(binCount - 1, Math.floor((value - min) / width)); bins[index].observations += 1; });
  return bins;
};

export const DataWorkspaceView: React.FC<{ wellId: string; onWellCreated: (well: WellSummary) => void }> = ({ wellId, onWellCreated }) => {
  const today = new Date().toISOString().slice(0, 10);
  const prior = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
  const [newWellId, setNewWellId] = useState('');
  const [wellName, setWellName] = useState('');
  const [sourceId, setSourceId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [sources, setSources] = useState<Array<Record<string, unknown>>>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [rejections, setRejections] = useState<Array<{ row: string; reason: string }>>([]);
  const [quality, setQuality] = useState<Record<string, unknown> | null>(null);
  const [snapshot, setSnapshot] = useState<Record<string, unknown> | null>(null);
  const [configuration, setConfiguration] = useState<Record<string, unknown> | null>(null);
  const [configurationJson, setConfigurationJson] = useState('{}');
  const [physicsRun, setPhysicsRun] = useState<Record<string, unknown> | null>(null);
  const [physicsRuns, setPhysicsRuns] = useState<Array<Record<string, unknown>>>([]);
  const [eligibility, setEligibility] = useState<Record<string, unknown> | null>(null);
  const [calibration, setCalibration] = useState<Record<string, unknown> | null>(null);
  const [comparison, setComparison] = useState<Record<string, unknown> | null>(null);
  const [scientificModel, setScientificModel] = useState('viscosity');
  const [calibrationStart, setCalibrationStart] = useState(prior);
  const [calibrationEnd, setCalibrationEnd] = useState(today);
  const [validationStart, setValidationStart] = useState(today);
  const [validationEnd, setValidationEnd] = useState(today);
  const [validationGapHours, setValidationGapHours] = useState('24');
  const [pairingToleranceMinutes, setPairingToleranceMinutes] = useState('15');
  const [calibrationDataset, setCalibrationDataset] = useState<Record<string, unknown> | null>(null);
  const [identifiability, setIdentifiability] = useState<Record<string, unknown> | null>(null);
  const [calibrationResult, setCalibrationResult] = useState<Record<string, unknown> | null>(null);
  const [validationResult, setValidationResult] = useState<Record<string, unknown> | null>(null);
  const [candidates, setCandidates] = useState<Array<Record<string, unknown>>>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState('');
  const [fitParameters, setFitParameters] = useState<string[]>(['walther_a', 'walther_b']);
  const [boundsJson, setBoundsJson] = useState('{}');
  const [policyJson, setPolicyJson] = useState('{}');
  const [rejectionReason, setRejectionReason] = useState('');
  const [candidateDetails, setCandidateDetails] = useState<Record<string, unknown> | null>(null);
  const [activationHistory, setActivationHistory] = useState<Record<string, unknown> | null>(null);

  const refreshSources = () => api.getDataSources().then(({ sources: rows }) => setSources(rows)).catch((err: unknown) => {
    setError(err instanceof Error ? err.message : 'Could not load data source status.');
  });
  useEffect(() => { void refreshSources(); }, []);
  useEffect(() => {
    setQuality(null); setSnapshot(null); setPhysicsRun(null); setConfiguration(null); setEligibility(null); setComparison(null);
    setCalibrationDataset(null); setIdentifiability(null); setCalibrationResult(null); setValidationResult(null); setCandidates([]); setSelectedCandidateId(''); setCandidateDetails(null); setActivationHistory(null);
    if (wellId) {
      api.getDataQuality(wellId).then(setQuality).catch(() => setQuality(null));
      api.getCalibrationEligibility(wellId).then(setCalibration).catch(() => setCalibration(null));
      api.getPhysicalConfiguration(wellId).then((result) => {
        const config = result.configuration as Record<string, unknown> | null;
        setConfiguration(config);
        if (config && config.parameters) {
          const editable = Object.fromEntries(Object.entries(config.parameters as Record<string, Record<string, unknown>>).map(([key, value]) => [key, {
            value: value.value, unit: value.unit, source: value.source,
            classification: value.classification, validation_status: value.validation_status,
          }]));
          setConfigurationJson(JSON.stringify(editable, null, 2));
        }
      }).catch(() => setConfiguration(null));
      api.getFieldPhysicsRuns(wellId).then((result) => setPhysicsRuns(result.runs)).catch(() => setPhysicsRuns([]));
      api.getCalibrationCandidates(wellId).then((result) => {
        setCandidates(result.candidates);
        setSelectedCandidateId(result.candidates[0]?.candidate_id ? String(result.candidates[0].candidate_id) : '');
      }).catch(() => setCandidates([]));
      api.getActiveCalibrationHistory(wellId).then(setActivationHistory).catch(() => setActivationHistory(null));
    }
  }, [wellId]);

  const buildSnapshot = async () => {
    if (!wellId) return;
    setBusy(true); setError(null);
    try {
      const nextSnapshot = await api.buildFieldTwinState(wellId);
      setSnapshot(nextSnapshot);
      if (typeof nextSnapshot.snapshot_id === 'string') setEligibility(await api.getPhysicsEligibility(wellId, nextSnapshot.snapshot_id));
    }
    catch (err) { setError(err instanceof Error ? err.message : 'Field twin state unavailable.'); }
    finally { setBusy(false); }
  };

  const saveConfiguration = async () => {
    if (!wellId) return;
    setBusy(true); setError(null);
    try { setConfiguration(await api.savePhysicalConfiguration(wellId, JSON.parse(configurationJson))); }
    catch (err) { setError(err instanceof Error ? err.message : 'Configuration rejected.'); }
    finally { setBusy(false); }
  };

  const executePhysics = async () => {
    if (!wellId || typeof snapshot?.snapshot_id !== 'string') return;
    setBusy(true); setError(null);
    try {
      const run = await api.executeFieldPhysics(wellId, snapshot.snapshot_id);
      setPhysicsRun(run);
      setPhysicsRuns((rows) => [run, ...rows]);
      if (typeof run.run_id === 'string') setComparison(await api.comparePhysicsRun(run.run_id));
    } catch (err) { setError(err instanceof Error ? err.message : 'Physics execution unavailable.'); }
    finally { setBusy(false); }
  };

  const inspectPhysicsRun = async (run: Record<string, unknown>) => {
    setPhysicsRun(run); setComparison(null);
    if (typeof run.run_id === 'string') {
      try { setComparison(await api.comparePhysicsRun(run.run_id)); }
      catch (err) { setError(err instanceof Error ? err.message : 'Could not compare this physics run to measured outputs.'); }
    }
  };

  const loadScientificDataset = async () => {
    if (!wellId) return;
    setBusy(true); setError(null); setCalibrationResult(null); setValidationResult(null); setIdentifiability(null);
    try {
      const result = await api.createCalibrationDataset(wellId, {
        model_id: scientificModel, start_at: `${calibrationStart}T00:00:00.000Z`,
        end_at: `${calibrationEnd}T23:59:59.999Z`, tolerance_minutes: Number(pairingToleranceMinutes), dataset_role: 'CALIBRATION',
      });
      setCalibrationDataset(result);
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not build calibration dataset.'); }
    finally { setBusy(false); }
  };

  const inspectScientificDataset = async () => {
    if (typeof calibrationDataset?.dataset_id !== 'string') return;
    setBusy(true); setError(null);
    try { setCalibrationDataset(await api.getCalibrationDataset(calibrationDataset.dataset_id)); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not retrieve dataset details.'); }
    finally { setBusy(false); }
  };

  const assessScientificIdentifiability = async () => {
    if (typeof calibrationDataset?.dataset_id !== 'string') return;
    setBusy(true); setError(null);
    try { setIdentifiability(await api.assessIdentifiability(calibrationDataset.dataset_id, fitParameters)); }
    catch (err) { setError(err instanceof Error ? err.message : 'Identifiability assessment failed.'); }
    finally { setBusy(false); }
  };

  const runCalibration = async () => {
    if (!wellId || typeof calibrationDataset?.dataset_id !== 'string') return;
    setBusy(true); setError(null);
    try {
      const result = await api.executeCalibration(wellId, {
        dataset_id: calibrationDataset.dataset_id, selected_parameters: fitParameters,
        parameter_bounds: JSON.parse(boundsJson),
      });
      setCalibrationResult(result);
      const listed = await api.getCalibrationCandidates(wellId);
      setCandidates(listed.candidates);
      const candidate = result.candidate as Record<string, unknown> | undefined;
      if (candidate?.candidate_id) setSelectedCandidateId(String(candidate.candidate_id));
    } catch (err) { setError(err instanceof Error ? err.message : 'Calibration did not complete.'); }
    finally { setBusy(false); }
  };

  const saveValidationPolicy = async () => {
    setBusy(true); setError(null);
    try { await api.saveValidationPolicy('viscosity', JSON.parse(policyJson)); setMessage('Versioned viscosity validation policy saved. It is operator/research-defined.'); }
    catch (err) { setError(err instanceof Error ? err.message : 'Validation policy was rejected.'); }
    finally { setBusy(false); }
  };

  const runTemporalValidation = async () => {
    if (!selectedCandidateId) return;
    setBusy(true); setError(null);
    try {
      setValidationResult(await api.runTemporalValidation(selectedCandidateId, {
        start_at: `${validationStart}T00:00:00.000Z`, end_at: `${validationEnd}T23:59:59.999Z`,
        tolerance_minutes: Number(pairingToleranceMinutes), temporal_gap_hours: Number(validationGapHours),
      }));
      if (wellId) setCandidates((await api.getCalibrationCandidates(wellId)).candidates);
    } catch (err) { setError(err instanceof Error ? err.message : 'Temporal validation failed.'); }
    finally { setBusy(false); }
  };

  const inspectCandidateComparison = async (candidateId: string) => {
    setSelectedCandidateId(candidateId); setValidationResult(null); setCandidateDetails(null);
    if (!candidateId) return;
    api.getCalibrationCandidate(candidateId).then(setCandidateDetails).catch(() => setCandidateDetails(null));
    try {
      const comparisonResult = await api.compareCalibrationCandidate(candidateId);
      setValidationResult(comparisonResult.latest_validation as Record<string, unknown>);
    } catch { /* A candidate without validation has no comparison to display. */ }
  };

  const rejectCandidate = async () => {
    if (!selectedCandidateId || !rejectionReason.trim()) return;
    setBusy(true); setError(null);
    try {
      await api.rejectCalibrationCandidate(selectedCandidateId, rejectionReason.trim());
      if (wellId) setCandidates((await api.getCalibrationCandidates(wellId)).candidates);
    } catch (err) { setError(err instanceof Error ? err.message : 'Candidate rejection failed.'); }
    finally { setBusy(false); }
  };

  const createWell = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(null); setMessage(null); setRejections([]);
    try {
      const { well } = await api.createWell({ well_id: newWellId.trim(), name: wellName.trim() });
      onWellCreated(well);
      setMessage(`Well ${well.well_id} registered. It has no measured data until ingestion succeeds.`);
      setNewWellId(''); setWellName('');
    } catch (err) { setError(err instanceof Error ? err.message : 'Well registration failed.'); }
    finally { setBusy(false); }
  };

  const upload = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(null); setMessage(null);
    try {
      if (!file) throw new Error('Choose a CSV file first.');
      if (!sourceId.trim()) throw new Error('Enter a source ID for provenance.');
      const result = await api.uploadMeasurementsCsv(sourceId.trim(), file);
      setRejections(result.rejected);
      setMessage(`Ingestion recorded for ${result.source_id}: ${result.accepted} accepted, ${result.rejected?.length ?? 0} rejected. Review row errors and data source status below.`);
      setFile(null);
      await refreshSources();
    } catch (err) { setError(err instanceof Error ? err.message : 'CSV ingestion failed.'); }
    finally { setBusy(false); }
  };

  return <section style={{ padding: 24, display: 'grid', gap: 16 }} aria-labelledby="data-workspace-title">
    <header className="glass-panel" style={{ padding: 20 }}>
      <h1 id="data-workspace-title" style={{ margin: 0, fontSize: '1.2rem' }}>Field data workspace</h1>
      <p style={{ margin: '6px 0 0', color: '#52525b', fontSize: '.82rem' }}>Register well identifiers and ingest measured CSV records through the backend. No telemetry is generated by this workflow.</p>
    </header>
    {wellId && <OperationalDataWorkspace wellId={wellId} />}
    {error && <div role="alert" className="glass-panel" style={{ padding: 14, color: '#991b1b' }}>{error}</div>}
    {message && <div role="status" className="glass-panel" style={{ padding: 14 }}>{message}</div>}
    {rejections.length > 0 && <div className="glass-panel" style={{ padding: 14 }}>
      <h2 style={{ margin: '0 0 8px', fontSize: '.9rem' }}>Rejected CSV rows</h2>
      <ul style={{ margin: 0 }}>{rejections.map((item, index) => <li key={`${item.row}-${index}`}>Row {item.row}: {item.reason}</li>)}</ul>
    </div>}
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 16 }}>
      <form onSubmit={createWell} className="glass-panel" style={{ padding: 18, display: 'grid', gap: 10, alignContent: 'start' }}>
        <h2 style={{ margin: 0, fontSize: '1rem' }}>Register a well</h2>
        <label>Well ID<input required pattern="[A-Za-z0-9._-]+" maxLength={128} value={newWellId} onChange={e => setNewWellId(e.target.value)} /></label>
        <label>Display name<input required maxLength={256} value={wellName} onChange={e => setWellName(e.target.value)} /></label>
        <button disabled={busy} className="neo-btn neo-btn-primary">Register well</button>
      </form>
      <form onSubmit={upload} className="glass-panel" style={{ padding: 18, display: 'grid', gap: 10, alignContent: 'start' }}>
        <h2 style={{ margin: 0, fontSize: '1rem' }}>Import measurement CSV</h2>
        <label>Source ID<input required maxLength={128} value={sourceId} onChange={e => setSourceId(e.target.value)} placeholder="e.g. historian-export-2026-11" /></label>
        <label>CSV file<input required type="file" accept=".csv,text/csv" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label>
        <p style={{ margin: 0, color: '#52525b', fontSize: '.75rem' }}>Required headers: well_id, measured_at, variable, value, unit. Times must include a timezone. A well must already be registered.</p>
        <button disabled={busy || !file} className="neo-btn neo-btn-primary">{busy ? 'Submitting…' : 'Submit CSV'}</button>
      </form>
    </div>
    <div className="glass-panel" style={{ padding: 18 }}>
      <h2 style={{ margin: '0 0 10px', fontSize: '1rem' }}>Recorded data sources</h2>
      {sources.length === 0 ? <p role="status">No ingestion sources are recorded. Configured connectors are not connected automatically.</p> : <ul>{sources.map((source, index) => <li key={`${String(source.source_id)}-${index}`}>{String(source.source_id)} · {String(source.connection_status ?? 'status unavailable')} · {String(source.source_type ?? 'unknown source type')}</li>)}</ul>}
    </div>
    <div className="glass-panel" style={{ padding: 18 }}>
      <h2 style={{ margin: '0 0 8px', fontSize: '1rem' }}>Measurement-backed twin state</h2>
      {!wellId ? <p>Select a registered well to inspect its data readiness.</p> : <>
        <button type="button" className="neo-btn" disabled={busy} onClick={buildSnapshot}>Build traceable snapshot for {wellId}</button>
        {quality && <pre style={{ maxHeight: 260, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(quality, null, 2)}</pre>}
        {snapshot && <pre aria-label="Field twin snapshot" style={{ maxHeight: 420, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(snapshot, null, 2)}</pre>}
        {eligibility && <><h3>Physics eligibility for this snapshot</h3><pre aria-label="Physics model eligibility" style={{ maxHeight: 360, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(eligibility.models, null, 2)}</pre></>}
        <h3>Physical configuration (JSON)</h3>
        <p>Each entry requires value, unit, source, classification, and validation_status. Unset parameters block dependent models.</p>
        <textarea aria-label="Physical configuration JSON" value={configurationJson} onChange={(event) => setConfigurationJson(event.target.value)} rows={12} />
        <button type="button" disabled={busy} onClick={saveConfiguration}>Save versioned configuration</button>
        {configuration && <pre>{JSON.stringify(configuration, null, 2)}</pre>}
        <button type="button" disabled={busy || !snapshot} onClick={executePhysics}>Execute physics against this snapshot</button>
        {physicsRun && <><pre aria-label="Physics execution run" style={{ maxHeight: 520, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(physicsRun, null, 2)}</pre>{comparison && <><h3>Compatible measured-output comparisons</h3><pre aria-label="Physics comparison" style={{ maxHeight: 260, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(comparison, null, 2)}</pre></>}</>}
        <h3>Physics run history ({physicsRuns.length})</h3>
        {physicsRuns.map((run) => <button type="button" key={String(run.run_id)} onClick={() => void inspectPhysicsRun(run)}>{String(run.created_at)} · {String(run.execution_status)} · config v{String(run.configuration_version ?? 'none')}</button>)}
        {calibration && <><h3>Calibration eligibility assessment</h3><pre aria-label="Calibration eligibility" style={{ maxHeight: 320, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(calibration, null, 2)}</pre></>}
        <p style={{ color: '#52525b', fontSize: '.75rem' }}>Snapshot values are measurements only. Missing or stale inputs remain unavailable; physics, calibration, and ML status are reported explicitly.</p>
        <section aria-labelledby="scientific-workspace-title" style={{ borderTop: '1px solid #d4d4d8', marginTop: 18, paddingTop: 18 }}>
          <h2 id="scientific-workspace-title">Scientific calibration and temporal validation</h2>
          <p>Only persisted measurements are used. Historical test fixtures are not field evidence. Approval and activation remain disabled because this application has no authenticated review workflow.</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(190px,1fr))', gap: 10 }}>
            <label>Model<select aria-label="Calibration model" value={scientificModel} onChange={event => { setScientificModel(event.target.value); setCalibrationDataset(null); setIdentifiability(null); }}>
              <option value="viscosity">Oil viscosity</option><option value="css_thermal">CSS thermal</option><option value="srp">SRP</option>
            </select></label>
            <label>Period start<input aria-label="Calibration period start" type="date" value={calibrationStart} onChange={event => setCalibrationStart(event.target.value)} /></label>
            <label>Period end<input aria-label="Calibration period end" type="date" value={calibrationEnd} onChange={event => setCalibrationEnd(event.target.value)} /></label>
            <label>Validation period start<input aria-label="Validation period start" type="date" value={validationStart} onChange={event => setValidationStart(event.target.value)} /></label>
            <label>Validation period end<input aria-label="Validation period end" type="date" value={validationEnd} onChange={event => setValidationEnd(event.target.value)} /></label>
            <label>Input/target pairing tolerance (minutes)<input aria-label="Pairing tolerance minutes" type="number" min="0" max="1440" value={pairingToleranceMinutes} onChange={event => setPairingToleranceMinutes(event.target.value)} /></label>
            <label>Temporal gap (hours)<input aria-label="Temporal gap hours" type="number" min="0" max="8760" value={validationGapHours} onChange={event => setValidationGapHours(event.target.value)} /></label>
          </div>
          <button type="button" disabled={busy || !wellId} onClick={loadScientificDataset}>Build persisted measurement dataset</button>
          {calibrationDataset && <>
            <p role="status">Dataset {String(calibrationDataset.dataset_id)} · {String(calibrationDataset.observation_count)} paired observations · {String(calibrationDataset.fingerprint)}</p>
            <button type="button" disabled={busy} onClick={inspectScientificDataset}>Retrieve dataset details</button>
            <pre aria-label="Calibration dataset details" style={{ maxHeight: 300, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(calibrationDataset, null, 2)}</pre>
            <h3>Parameter identifiability</h3>
            {scientificModel === 'viscosity' ? <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              {['walther_a', 'walther_b', 'native_density_kg_m3'].map(name => <label key={name} style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
                <input type="checkbox" checked={fitParameters.includes(name)} onChange={event => setFitParameters(current => event.target.checked ? [...current, name] : current.filter(item => item !== name))} />{name}
              </label>)}
            </div> : <p>Calibration fitting is blocked for {scientificModel}: available measurements do not identify a supported parameter subset.</p>}
            <button type="button" disabled={busy} onClick={assessScientificIdentifiability}>Assess selected parameter identifiability</button>
            {identifiability && <pre aria-label="Parameter identifiability assessment" style={{ maxHeight: 320, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(identifiability, null, 2)}</pre>}
            {scientificModel === 'viscosity' && <>
              <label>Explicit parameter bounds JSON<textarea aria-label="Calibration parameter bounds" value={boundsJson} onChange={event => setBoundsJson(event.target.value)} rows={4} placeholder="Enter bounds and canonical units from a reviewed study protocol." /></label>
              <p>Use approved study bounds, include canonical units, and include the source configuration value. No bounds are suggested by this screen.</p>
              <button type="button" disabled={busy || !identifiability || identifiability.status !== 'POTENTIALLY_IDENTIFIABLE' || !fitParameters.length} onClick={runCalibration}>Run bounded calibration</button>
            </>}
          </>}
          {calibrationResult && <><h3>Persisted calibration result</h3><pre aria-label="Calibration result" style={{ maxHeight: 420, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(calibrationResult, null, 2)}</pre></>}
          <h3>Versioned viscosity validation policy</h3>
          <p>Provide operator/research-defined metric thresholds and a minimum observation count. No universal limits are prefilled.</p>
          <label>Policy JSON<textarea aria-label="Validation policy JSON" value={policyJson} onChange={event => setPolicyJson(event.target.value)} rows={4} placeholder="Enter model-specific thresholds and sample count from a reviewed study protocol." /></label>
          <button type="button" disabled={busy} onClick={saveValidationPolicy}>Save versioned validation policy</button>
          {candidates.length > 0 && <>
            <h3>Calibration candidates</h3>
            <label>Candidate<select aria-label="Calibration candidate" value={selectedCandidateId} onChange={event => void inspectCandidateComparison(event.target.value)}>
              {candidates.map(candidate => <option key={String(candidate.candidate_id)} value={String(candidate.candidate_id)}>{String(candidate.created_at)} · {String(candidate.lifecycle_status)} · {String(candidate.candidate_id)}</option>)}
            </select></label>
            {candidateDetails && <pre aria-label="Candidate configuration and lifecycle" style={{ maxHeight: 340, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(candidateDetails, null, 2)}</pre>}
            <button type="button" disabled={busy || !selectedCandidateId} onClick={runTemporalValidation}>Validate on later period</button>
            <label>Rejection reason<input aria-label="Candidate rejection reason" value={rejectionReason} onChange={event => setRejectionReason(event.target.value)} /></label>
            <button type="button" disabled={busy || !selectedCandidateId || !rejectionReason.trim()} onClick={rejectCandidate}>Reject candidate (unprotected development action)</button>
            <button type="button" disabled title="Approval/activation require authenticated RBAC and an authorized audit workflow">Approval disabled</button>
          </>}
          {activationHistory && <><h3>Active calibration configuration history</h3><pre aria-label="Active calibration history" style={{ maxHeight: 200, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(activationHistory, null, 2)}</pre></>}
          {validationResult && <><h3>Held-out temporal validation</h3><pre aria-label="Temporal validation result" style={{ maxHeight: 440, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(validationResult, null, 2)}</pre>
            {Array.isArray(validationResult.series) && validationResult.series.length > 0 && <>
              <h4>Observed and predicted viscosity (cP)</h4>
              <div style={{ width: '100%', height: 300 }}><ResponsiveContainer><LineChart data={(validationResult.series as Array<Record<string, unknown>>).map(row => ({ ...row, time: String(row.observed_at).slice(0, 10) }))}>
                <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="time" /><YAxis /><Tooltip /><Legend />
                <Line type="monotone" dataKey="observed_value" name="Measured" stroke="#111827" dot={false} />
                <Line type="monotone" dataKey="calibrated_prediction" name="Calibrated physics" stroke="#2563eb" dot={false} />
                <Line type="monotone" dataKey="uncalibrated_prediction" name="Original physics" stroke="#d97706" dot={false} />
                <Line type="monotone" dataKey="persistence_baseline" name="Persistence baseline" stroke="#64748b" dot={false} />
              </LineChart></ResponsiveContainer></div>
              <h4>Calibration residuals (prediction minus measurement, cP)</h4>
              <div style={{ width: '100%', height: 250 }}><ResponsiveContainer><LineChart data={(validationResult.series as Array<Record<string, unknown>>).map(row => ({ ...row, time: String(row.observed_at).slice(0, 10) }))}>
                <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="time" /><YAxis /><Tooltip /><Legend />
                <Line type="monotone" dataKey="calibrated_residual" name="Calibrated residual" stroke="#2563eb" dot={false} />
                <Line type="monotone" dataKey="uncalibrated_residual" name="Original residual" stroke="#d97706" dot={false} />
              </LineChart></ResponsiveContainer></div>
              <h4>Calibrated residual distribution (observed counts)</h4>
              <div style={{ width: '100%', height: 240 }}><ResponsiveContainer><BarChart data={residualHistogram(validationResult.series as Array<Record<string, unknown>>)}>
                <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="residual_bin" /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="observations" name="Validation observations" fill="#2563eb" />
              </BarChart></ResponsiveContainer></div>
            </>}
          </>}
        </section>
      </>}
    </div>
  </section>;
};
