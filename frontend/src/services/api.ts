import {
  TelemetryFrame,
  DynoCardData,
  ProductionForecast,
  FailureIntelligence,
  OptimizationResult,
  WellSummary,
  ScenarioEvaluation,
  SRPPerformance,
  DynoCardPoint,
  SavedAnalysisRun
} from '../types/petro';

const BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

export class ApiError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

const AUTH_TOKEN_KEY = 'petrotwin_access_token';

export function getAuthToken(): string | null {
  return typeof window === 'undefined' ? null : window.sessionStorage.getItem(AUTH_TOKEN_KEY);
}

export function setAuthToken(token: string): void {
  window.sessionStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearAuthToken(): void {
  if (typeof window !== 'undefined') window.sessionStorage.removeItem(AUTH_TOKEN_KEY);
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getAuthToken();
  return { ...extra, ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  const headers = new Headers(init?.headers);
  if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const token = getAuthToken();
  if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`);
  try {
    response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError('The PETRO-TWIN API is unreachable. Check that the backend is running.');
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    if (response.status === 401 && path !== '/api/v1/auth/login') {
      clearAuthToken();
      window.dispatchEvent(new Event('petrotwin:unauthorized'));
    }
    throw new ApiError(body?.detail || `API request failed (${response.status}).`, response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  login: async (username: string, password: string) => {
    const result = await request<{ access_token: string; user: Record<string, unknown> }>('/api/v1/auth/login', {
      method: 'POST', body: JSON.stringify({ username, password })
    });
    setAuthToken(result.access_token);
    return result.user;
  },
  getCurrentUser: () => request<{ user: Record<string, unknown> }>('/api/v1/auth/me'),
  logout: async () => {
    try { await request('/api/v1/auth/logout', { method: 'POST' }); }
    finally { clearAuthToken(); }
  },
  getHealth: () => request<{ status: string; service: string; data_mode: string; data_availability: string; disclaimer: string; auth_required: boolean }>('/health'),
  getWells: () => request<{ wells: WellSummary[] }>('/api/wells'),
  getDataSources: () => request<{ sources: Array<Record<string, unknown>> }>('/api/v1/data-sources'),
  getDataQuality: (wellId: string) => request<Record<string, unknown>>(`/api/v1/wells/${encodeURIComponent(wellId)}/data-quality`),
  getWellMeasurements: (wellId: string) => request<{ well_id: string; records: Array<Record<string, unknown>> }>(`/api/v1/wells/${encodeURIComponent(wellId)}/measurements?days=3650`),
  buildFieldTwinState: (wellId: string, windowHours = 168) => request<Record<string, unknown>>(`/api/v1/wells/${encodeURIComponent(wellId)}/twin-state?window_hours=${windowHours}`, { method: 'POST' }),
  getPhysicalConfiguration: (wellId: string) => request<Record<string, unknown>>(`/api/v1/wells/${encodeURIComponent(wellId)}/physical-configuration`),
  savePhysicalConfiguration: (wellId: string, parameters: Record<string, unknown>) => request<Record<string, unknown>>(`/api/v1/wells/${encodeURIComponent(wellId)}/physical-configuration`, { method: 'PUT', body: JSON.stringify({ parameters }) }),
  executeFieldPhysics: (wellId: string, snapshotId: string) => request<Record<string, unknown>>(`/api/v1/wells/${encodeURIComponent(wellId)}/physics-runs`, { method: 'POST', body: JSON.stringify({ snapshot_id: snapshotId }) }),
  getFieldPhysicsRuns: (wellId: string) => request<{ runs: Array<Record<string, unknown>> }>(`/api/v1/wells/${encodeURIComponent(wellId)}/physics-runs`),
  getPhysicsEligibility: (wellId: string, snapshotId: string) => request<Record<string, unknown>>(`/api/v1/wells/${encodeURIComponent(wellId)}/physics-eligibility?snapshot_id=${encodeURIComponent(snapshotId)}`),
  getCalibrationEligibility: (wellId: string) => request<Record<string, unknown>>(`/api/v1/wells/${encodeURIComponent(wellId)}/calibration-eligibility`),
  getOperationalTimeline: (wellId: string) => request<Record<string, unknown>>(`/api/v1/wells/${encodeURIComponent(wellId)}/operational-timeline`),
  getOperationalCalibrationReadiness: (wellId: string) => request<Record<string, unknown>>(`/api/v1/wells/${encodeURIComponent(wellId)}/operational-calibration-readiness`),
  createCssCycle: (wellId: string, body: Record<string, unknown>) => request<Record<string, unknown>>(`/api/v1/wells/${encodeURIComponent(wellId)}/css-cycles`, { method: 'POST', body: JSON.stringify(body) }),
  createOperationalEvent: (wellId: string, body: Record<string, unknown>) => request<Record<string, unknown>>(`/api/v1/wells/${encodeURIComponent(wellId)}/operational-events`, { method: 'POST', body: JSON.stringify(body) }),
  createSrpRecord: (wellId: string, body: Record<string, unknown>) => request<Record<string, unknown>>(`/api/v1/wells/${encodeURIComponent(wellId)}/srp-records`, { method: 'POST', body: JSON.stringify(body) }),
  linkOperationalMeasurement: (body: Record<string, unknown>) => request<Record<string, unknown>>('/api/v1/operational-measurement-links', { method: 'POST', body: JSON.stringify(body) }),
  createOperationalDataset: (wellId: string, body: Record<string, unknown>) => request<Record<string, unknown>>(`/api/v1/wells/${encodeURIComponent(wellId)}/operational-datasets`, { method: 'POST', body: JSON.stringify(body) }),
  importOperationalJson: (body: Record<string, unknown>) => request<Record<string, unknown>>('/api/v1/operational-data/import/json', { method: 'POST', body: JSON.stringify(body) }),
  importOperationalCsv: async (recordType: string, file: File) => {
    let response: Response;
    try { response = await fetch(`${BASE_URL}/api/v1/operational-data/import/csv?record_type=${encodeURIComponent(recordType)}`, { method: 'POST', headers: authHeaders({ 'Content-Type': 'text/csv' }), body: file }); }
    catch { throw new ApiError('The PETRO-TWIN API is unreachable. Check that the backend is running.'); }
    if (!response.ok) { const body = await response.json().catch(() => null) as { detail?: string } | null; throw new ApiError(body?.detail || `Operational CSV import failed (${response.status}).`, response.status); }
    return response.json() as Promise<Record<string, unknown>>;
  },
  comparePhysicsRun: (runId: string) => request<Record<string, unknown>>(`/api/v1/physics-runs/${encodeURIComponent(runId)}/comparisons`),
  createCalibrationDataset: (wellId: string, body: Record<string, unknown>) => request<Record<string, unknown>>(`/api/v1/wells/${encodeURIComponent(wellId)}/calibration-datasets`, { method: 'POST', body: JSON.stringify(body) }),
  getCalibrationDataset: (datasetId: string) => request<Record<string, unknown>>(`/api/v1/calibration-datasets/${encodeURIComponent(datasetId)}`),
  assessIdentifiability: (datasetId: string, parameterNames?: string[]) => request<Record<string, unknown>>(`/api/v1/calibration-datasets/${encodeURIComponent(datasetId)}/identifiability`, { method: 'POST', body: JSON.stringify({ parameter_names: parameterNames }) }),
  executeCalibration: (wellId: string, body: Record<string, unknown>) => request<Record<string, unknown>>(`/api/v1/wells/${encodeURIComponent(wellId)}/calibrations`, { method: 'POST', body: JSON.stringify(body) }),
  runTemporalValidation: (candidateId: string, body: Record<string, unknown>) => request<Record<string, unknown>>(`/api/v1/calibration-candidates/${encodeURIComponent(candidateId)}/validate`, { method: 'POST', body: JSON.stringify(body) }),
  getCalibrationCandidates: (wellId: string) => request<{ candidates: Array<Record<string, unknown>> }>(`/api/v1/wells/${encodeURIComponent(wellId)}/calibration-candidates`),
  saveValidationPolicy: (modelId: string, body: Record<string, unknown>) => request<Record<string, unknown>>(`/api/v1/models/${encodeURIComponent(modelId)}/validation-policy`, { method: 'PUT', body: JSON.stringify(body) }),
  rejectCalibrationCandidate: (candidateId: string, reason: string) => request<Record<string, unknown>>(`/api/v1/calibration-candidates/${encodeURIComponent(candidateId)}/reject`, { method: 'POST', body: JSON.stringify({ reason }) }),
  compareCalibrationCandidate: (candidateId: string) => request<Record<string, unknown>>(`/api/v1/calibration-candidates/${encodeURIComponent(candidateId)}/comparison`),
  getCalibrationCandidate: (candidateId: string) => request<Record<string, unknown>>(`/api/v1/calibration-candidates/${encodeURIComponent(candidateId)}`),
  getActiveCalibrationHistory: (wellId: string) => request<Record<string, unknown>>(`/api/v1/wells/${encodeURIComponent(wellId)}/active-calibration-history`),
  createWell: (well: { well_id: string; name: string; depth_m?: number; pump_depth_m?: number }) =>
    request<{ well: WellSummary }>('/api/v1/wells', { method: 'POST', body: JSON.stringify(well) }),
  uploadMeasurementsCsv: async (sourceId: string, file: File) => {
    let response: Response;
    try {
      response = await fetch(`${BASE_URL}/api/v1/measurements/csv?source_id=${encodeURIComponent(sourceId)}`, {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'text/csv' }), body: file
      });
    } catch {
      throw new ApiError('The PETRO-TWIN API is unreachable. Check that the backend is running.');
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null) as { detail?: string } | null;
      throw new ApiError(body?.detail || `CSV ingestion failed (${response.status}).`, response.status);
    }
    return response.json() as Promise<{ accepted: number; rejected: Array<{ row: string; reason: string }>; source_id: string; duplicates: number; provenance: Record<string, unknown> }>;
  },
  getTelemetry: (wellId = 'BW-DEMO-001') => request<TelemetryFrame>(`/api/wells/${encodeURIComponent(wellId)}/telemetry`),
  getDynoCard: (wellId = 'BW-DEMO-001') => request<DynoCardData>(`/api/wells/${encodeURIComponent(wellId)}/srp/dyno-card`),
  getProductionHistory: (wellId = 'BW-DEMO-001') =>
    request<{ history: Array<Record<string, number | boolean>> }>(`/api/wells/${encodeURIComponent(wellId)}/production?days=90`),

  async getProductionForecast(wellId = 'BW-DEMO-001'): Promise<ProductionForecast> {
    const state = await this.getTelemetry(wellId);
    return request('/predict/production', {
      method: 'POST',
      body: JSON.stringify({
        temperature_c: state.thermal_state.reservoir_temperature_c,
        well_id: wellId,
        pressure_bar: state.pressure_state.bottomhole_pressure_bar,
        spm: state.srp_operating_state.spm,
        stroke_length_m: state.srp_operating_state.stroke_length_m,
        days_since_injection: state.cycle_info.days_in_production,
        recent_oil_rate_bpd: state.production_state.oil_rate_bpd
      })
    });
  },

  async getFailureIntelligence(wellId = 'BW-DEMO-001'): Promise<FailureIntelligence> {
    const state = await this.getTelemetry(wellId);
    return request('/predict/failure', {
      method: 'POST',
      body: JSON.stringify({
        stroke_length_m: state.srp_operating_state.stroke_length_m,
        spm: state.srp_operating_state.spm,
        temperature_c: state.thermal_state.reservoir_temperature_c,
        well_id: wellId,
        pressure_bar: state.pressure_state.bottomhole_pressure_bar,
        days_in_production: state.cycle_info.days_in_production
      })
    });
  },

  runOptimization: (wellId = 'BW-DEMO-001') => request<OptimizationResult>('/optimize/joint', {
    method: 'POST',
    body: JSON.stringify({ well_id: wellId })
  }),

  getAnalysisRuns: (wellId: string, limit = 50) =>
    request<{ runs: SavedAnalysisRun[] }>(`/api/wells/${encodeURIComponent(wellId)}/analysis-runs?limit=${limit}`),

  getFieldModels: (wellId: string, limit = 50) => request<{ models: Array<Record<string, unknown>> }>(`/api/v1/models/production?well_id=${encodeURIComponent(wellId)}&limit=${limit}`),
  trainFieldModel: (body: { well_id: string; horizon_days: 1 | 7 | 30; start_at: string; end_at: string; min_samples: number; max_feature_age_hours: number }) => request<Record<string, unknown>>('/api/v1/models/production/train', { method: 'POST', body: JSON.stringify(body) }),
  promoteFieldModel: (modelId: string) => request<Record<string, unknown>>(`/api/v1/models/${encodeURIComponent(modelId)}/promote`, { method: 'POST', body: JSON.stringify({ acknowledgement: 'I_HAVE_REVIEWED_FIELD_MODEL_EVIDENCE' }) }),
  predictFieldModel: (wellId: string, horizonDays: 1 | 7 | 30) => request<Record<string, unknown>>(`/api/v1/models/production/predict?well_id=${encodeURIComponent(wellId)}&horizon_days=${horizonDays}`),
  getAgentStatus: () => request<Record<string, unknown>>('/api/v1/agent/status'),
  getAgentRuns: (wellId: string, limit = 50) => request<{ runs: Array<Record<string, unknown>> }>(`/api/v1/agent/runs?well_id=${encodeURIComponent(wellId)}&limit=${limit}`),
  queryCopilot: (query: string, wellId = 'BW-DEMO-001') => request<{ answer: string; tools_used: string[]; run_id: string }>('/api/v1/agent/investigate', {
    method: 'POST',
    body: JSON.stringify({ question: query, well_id: wellId, days: 30 })
  }),

  getTimeMachineState: (wellId: string, day: number) =>
    request<TelemetryFrame>(`/api/wells/${encodeURIComponent(wellId)}/time-machine/${day}`),

  runScenario: (input: {
    well_id: string;
    steam_volume: number; soak_time: number;
    production_cutoff: number; stroke_length: number; spm: number;
  }) => request<ScenarioEvaluation>('/simulate/scenario', { method: 'POST', body: JSON.stringify(input) }),

  simulateCss: (steam_mass_tons: number, soak_days: number) =>
    request<{ peak_metrics: { peak_temperature_c: number; heated_radius_m: number; total_heat_injected_gj: number; heat_retained_post_soak_gj: number }; cooling_projection: Array<{day: number; reservoir_temperature_c: number}> }>('/simulate/css', { method: 'POST', body: JSON.stringify({ steam_mass_tons, soak_days }) }),

  simulateSrp: (stroke_length_m: number, spm: number, avg_viscosity_cp: number) =>
    request<{ performance: SRPPerformance; dynamometer_card: DynoCardPoint[] }>('/simulate/srp', { method: 'POST', body: JSON.stringify({ stroke_length_m, spm, avg_viscosity_cp }) })
};
