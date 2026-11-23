import React, { useEffect, useState } from 'react';
import { api } from '../services/api';

type JsonRecord = Record<string, unknown>;
const box: React.CSSProperties = { padding: 18, display: 'grid', gap: 10, alignContent: 'start' };
const area: React.CSSProperties = { width: '100%', minHeight: 150, fontFamily: 'monospace', fontSize: 12 };

export const OperationalDataWorkspace: React.FC<{ wellId: string }> = ({ wellId }) => {
  const [timeline, setTimeline] = useState<JsonRecord | null>(null);
  const [readiness, setReadiness] = useState<JsonRecord | null>(null);
  const [measurements, setMeasurements] = useState<JsonRecord[]>([]);
  const [cycleJson, setCycleJson] = useState('');
  const [eventJson, setEventJson] = useState('');
  const [srpJson, setSrpJson] = useState('');
  const [linkType, setLinkType] = useState('css_cycle');
  const [linkEntity, setLinkEntity] = useState('');
  const [linkMeasurement, setLinkMeasurement] = useState('');
  const [measurementRelation, setMeasurementRelation] = useState('');
  const [datasetType, setDatasetType] = useState('css_cycle');
  const [calibrationFraction, setCalibrationFraction] = useState('0.8');
  const [temporalGapHours, setTemporalGapHours] = useState('0');
  const [regimeLabel, setRegimeLabel] = useState('');
  const [periodStart, setPeriodStart] = useState('');
  const [periodEnd, setPeriodEnd] = useState('');
  const [recordType, setRecordType] = useState('css_cycle');
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [dataset, setDataset] = useState<JsonRecord | null>(null);

  const reload = async () => {
    if (!wellId) return;
    setError(null);
    try {
      const [nextTimeline, nextReadiness, nextMeasurements] = await Promise.all([
        api.getOperationalTimeline(wellId), api.getOperationalCalibrationReadiness(wellId),
        api.getWellMeasurements(wellId),
      ]);
      setTimeline(nextTimeline); setReadiness(nextReadiness); setMeasurements(nextMeasurements.records);
    } catch (err) { setError(err instanceof Error ? err.message : 'Operational records are unavailable.'); }
  };
  useEffect(() => { void reload(); }, [wellId]);

  const submitJson = async (raw: string, action: (body: JsonRecord) => Promise<JsonRecord>, label: string) => {
    setLoading(true); setError(null); setNotice(null);
    try { await action(JSON.parse(raw)); setNotice(`${label} saved.`); await reload(); }
    catch (err) { setError(err instanceof Error ? err.message : `${label} failed.`); }
    finally { setLoading(false); }
  };
  const importJson = async (raw: string) => {
    setLoading(true); setError(null); setNotice(null);
    try {
      const body = JSON.parse(raw);
      const result = await api.importOperationalJson({ schema_version: '1.0', record_type: recordType, records: [body] });
      setNotice(`Operational import: ${String(result.accepted)} accepted, ${(result.rejected as unknown[] | undefined)?.length ?? 0} rejected. ${String(result.persistence ?? '')}`);
      await reload();
    } catch (err) { setError(err instanceof Error ? err.message : 'Operational JSON import failed.'); }
    finally { setLoading(false); }
  };
  const importCsv = async () => {
    if (!file) { setError('Choose an operational CSV file.'); return; }
    setLoading(true); setError(null); setNotice(null);
    try {
      const result = await api.importOperationalCsv(recordType, file);
      setNotice(`Operational CSV: ${String(result.accepted)} accepted; ${(result.rejected as unknown[] | undefined)?.length ?? 0} rejected.`);
      setFile(null); await reload();
    } catch (err) { setError(err instanceof Error ? err.message : 'Operational CSV import failed.'); }
    finally { setLoading(false); }
  };
  const createDataset = async () => {
    setLoading(true); setError(null); setDataset(null);
    try { setDataset(await api.createOperationalDataset(wellId, { dataset_type: datasetType, start_at: `${periodStart}T00:00:00Z`, end_at: `${periodEnd}T23:59:59Z`, calibration_fraction: Number(calibrationFraction), regime_label: regimeLabel.trim() || null, temporal_gap_hours: Number(temporalGapHours) })); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not create the operational dataset.'); }
    finally { setLoading(false); }
  };

  const entries = (timeline?.entries as Array<JsonRecord> | undefined) ?? [];
  const entryRecord = (entry: JsonRecord) => (entry.record ?? {}) as JsonRecord;
  const css = (readiness?.css ?? {}) as JsonRecord;
  const srp = (readiness?.srp ?? {}) as JsonRecord;
  const joint = (readiness?.css_srp_coupled ?? {}) as JsonRecord;

  return <section aria-labelledby="operational-data-title" style={{ display: 'grid', gap: 16 }}>
    <header className="glass-panel" style={box}>
      <h2 id="operational-data-title" style={{ margin: 0 }}>Petroleum operational records</h2>
      <p style={{ margin: 0, color: '#52525b' }}>Events, CSS cycles, SRP records, and measurement links are persisted as supplied. No cycle history or operating regime is inferred.</p>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}><button className="neo-btn" disabled={loading} onClick={() => void reload()}>Refresh operational data</button>
        <span role="status">{loading ? 'Saving/loading · ' : ''}{entries.length} persisted timeline entries · regime labels require explicit evidence</span></div>
      {error && <div role="alert" style={{ color: '#991b1b' }}>{error}</div>}{notice && <div role="status">{notice}</div>}
    </header>

    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 16 }}>
      <section className="glass-panel" style={box} aria-label="CSS cycles">
        <h3 style={{ margin: 0 }}>CSS cycle record</h3>
        <p style={{ margin: 0 }}>Use ISO-8601 timezone timestamps, canonical-unit quantity objects, source, and provenance. Partial phases are stored as INCOMPLETE.</p>
        <textarea aria-label="CSS cycle JSON" style={area} value={cycleJson} onChange={e => setCycleJson(e.target.value)} placeholder={'{\n  "cycle_number": 1,\n  "injection_start": "...+00:00",\n  "injection_end": "...+00:00",\n  "soak_start": "...+00:00",\n  "soak_end": "...+00:00",\n  "production_restart": "...+00:00",\n  "injection_mass_tons": {"value": 0, "unit": "metric_ton"},\n  "source": "operator/import name",\n  "provenance": {"source_record_id": "..."}\n}'} />
        <button className="neo-btn neo-btn-primary" disabled={loading || !cycleJson.trim()} onClick={() => void submitJson(cycleJson, body => api.createCssCycle(wellId, body), 'CSS cycle')}>Save CSS cycle</button>
      </section>
      <section className="glass-panel" style={box} aria-label="Operational event">
        <h3 style={{ margin: 0 }}>Intervention or event</h3><p style={{ margin: 0 }}>Examples of event_type values: SHUTDOWN, WORKOVER, MAINTENANCE, CSS_INJECTION, PRODUCTION_RESTART.</p>
        <textarea aria-label="Operational event JSON" style={area} value={eventJson} onChange={e => setEventJson(e.target.value)} placeholder={'{"event_type":"MAINTENANCE","occurred_at":"...+00:00","source":"operator","provenance":{"ticket":"..."},"metadata":{}}'} />
        <button className="neo-btn neo-btn-primary" disabled={loading || !eventJson.trim()} onClick={() => void submitJson(eventJson, body => api.createOperationalEvent(wellId, body), 'Operational event')}>Save event</button>
      </section>
      <section className="glass-panel" style={box} aria-label="SRP operational record">
        <h3 style={{ margin: 0 }}>SRP configuration or observation</h3><p style={{ margin: 0 }}>Record type is CONFIGURATION, OPERATING_OBSERVATION, or INTERVENTION. Every parameter requires its value, canonical unit, and quality.</p>
        <textarea aria-label="SRP record JSON" style={area} value={srpJson} onChange={e => setSrpJson(e.target.value)} placeholder={'{"record_type":"OPERATING_OBSERVATION","valid_at":"...+00:00","parameters":{"stroke_length_m":{"value":0,"unit":"m"},"spm":{"value":0,"unit":"stroke/min"}},"source":"operator","provenance":{"record":"..."}}'} />
        <button className="neo-btn neo-btn-primary" disabled={loading || !srpJson.trim()} onClick={() => void submitJson(srpJson, body => api.createSrpRecord(wellId, body), 'SRP record')}>Save SRP record</button>
      </section>
    </div>

    <section className="glass-panel" style={box} aria-label="Operational data import">
      <h3 style={{ margin: 0 }}>Import operational JSON or CSV</h3><p style={{ margin: 0 }}>CSV schema: schema_version,record_json; each record_json cell contains one JSON record. Imports report accepted and rejected rows; accepted rows persist independently.</p>
      <label>Record type<select aria-label="Operational import record type" value={recordType} onChange={e => setRecordType(e.target.value)}><option value="css_cycle">CSS cycle</option><option value="event">Operational event</option><option value="srp_record">SRP record</option></select></label>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'end' }}><label>Operational CSV<input aria-label="Operational CSV file" type="file" accept=".csv,text/csv" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label><button className="neo-btn" disabled={loading || !file} onClick={() => void importCsv()}>Import CSV</button><button className="neo-btn" disabled={loading || !(cycleJson || eventJson || srpJson)} onClick={() => void importJson(recordType === 'css_cycle' ? cycleJson : recordType === 'event' ? eventJson : srpJson)}>Import current JSON record</button></div>
    </section>

    <section className="glass-panel" style={box} aria-label="Link measurement to operational record">
      <h3 style={{ margin: 0 }}>Link a persisted measurement</h3><p style={{ margin: 0 }}>Links must use a measurement from this well. A measurement cannot belong to two CSS cycles.</p>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'end' }}>
        <label>Record type<select aria-label="Measurement link record type" value={linkType} onChange={e => setLinkType(e.target.value)}><option value="css_cycle">CSS cycle</option><option value="operational_event">Operational event</option><option value="srp_record">SRP record</option></select></label>
        <label>Record ID<input value={linkEntity} onChange={e => setLinkEntity(e.target.value)} /></label>
        <label>Measurement<select value={linkMeasurement} onChange={e => setLinkMeasurement(e.target.value)}><option value="">Select measurement</option>{measurements.map(row => <option key={String(row.measurement_id)} value={String(row.measurement_id)}>{String(row.variable)} · {String(row.measured_at)} · {String(row.measurement_id)}</option>)}</select></label>
        <label>Relation<input aria-label="Measurement relation" placeholder="POST_SOAK_TEMPERATURE" value={measurementRelation} onChange={e => setMeasurementRelation(e.target.value)} /></label>
        <button className="neo-btn" disabled={loading || !linkEntity || !linkMeasurement} onClick={async () => {
          setLoading(true); setError(null); setNotice(null);
          try { await api.linkOperationalMeasurement({ entity_type: linkType, entity_id: linkEntity, measurement_id: linkMeasurement, relation: measurementRelation.trim() }); setNotice('Measurement linked.'); await reload(); }
          catch (err) { setError(err instanceof Error ? err.message : 'Measurement link failed.'); } finally { setLoading(false); }
        }}>Link measurement</button>
      </div>
    </section>

    <section className="glass-panel" style={box} aria-label="Operational calibration readiness">
      <h3 style={{ margin: 0 }}>Calibration readiness evidence</h3><p style={{ margin: 0 }}>Data linkage readiness is not calibration, identifiability, validation, or approval.</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 12 }}><article><strong>CSS</strong><pre>{JSON.stringify(css, null, 2)}</pre></article><article><strong>SRP</strong><pre>{JSON.stringify(srp, null, 2)}</pre></article><article><strong>CSS–SRP interaction</strong><pre>{JSON.stringify(joint, null, 2)}</pre></article></div>
    </section>

    <section className="glass-panel" style={box} aria-label="Operational dataset builder">
      <h3 style={{ margin: 0 }}>Build traceable operational dataset</h3><p style={{ margin: 0 }}>Dataset rows are grouped by cycle/record and remain chronological; no random split or missing-value fill is applied.</p>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'end' }}><label>Dataset type<select value={datasetType} onChange={e => setDatasetType(e.target.value)}><option value="css_cycle">CSS cycles</option><option value="srp">SRP records</option><option value="css_srp_joint">Joint CSS–SRP records</option><option value="event_aligned">Event-aligned</option><option value="regime_aware">Explicitly labeled regimes</option></select></label><label>Period start<input type="date" value={periodStart} onChange={e => setPeriodStart(e.target.value)} /></label><label>Period end<input type="date" value={periodEnd} onChange={e => setPeriodEnd(e.target.value)} /></label><label>Calibration fraction<input type="number" min="0.5" max="0.99" step="0.05" value={calibrationFraction} onChange={e => setCalibrationFraction(e.target.value)} /></label><label>Temporal gap (hours)<input type="number" min="0" max="8760" value={temporalGapHours} onChange={e => setTemporalGapHours(e.target.value)} /></label><label>Explicit regime label<input value={regimeLabel} onChange={e => setRegimeLabel(e.target.value)} placeholder="Only filters supplied labels" /></label><button className="neo-btn" disabled={loading || !periodStart || !periodEnd} onClick={() => void createDataset()}>Build operational dataset</button></div>
      {dataset && <pre aria-label="Operational dataset result">{JSON.stringify(dataset, null, 2)}</pre>}
    </section>

    <section className="glass-panel" style={box} aria-label="Well operational timeline">
      <h3 style={{ margin: 0 }}>Persisted well timeline ({entries.length})</h3>
      {entries.length === 0 ? <p>No operational events, CSS cycles, or SRP records have been recorded for this well.</p> : <ol>{entries.map((entry, index) => { const record=entryRecord(entry); return <li key={`${String(entry.entry_type)}-${String(record.cycle_id ?? record.event_id ?? record.record_id)}-${index}`}><strong>{String(entry.entry_type)} · {String(entry.occurred_at)}</strong><details><summary>Inspect record and measurement links</summary><pre>{JSON.stringify({ record, links: entry.links }, null, 2)}</pre></details></li>; })}</ol>}
    </section>
  </section>;
};
