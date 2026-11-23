// PETRO-TWIN AI: Core Data Models & TypeScript Types

export type WellId = string;

export interface WellSummary {
  well_id: string;
  name: string;
  depth_m: number | null;
  pump_depth_m: number | null;
  cycle_number: number | null;
  days_in_production: number | null;
  status: string;
}

export interface TelemetryFrame {
  timestamp: string;
  well_id: string;
  data_source_mode: string;
  scientific_honesty_disclaimer: string;
  cycle_info: {
    cycle_number: number;
    days_in_production: number;
    steam_injected_tons: number;
    soak_days: number;
    sor_cumulative: number;
  };
  thermal_state: {
    reservoir_temperature_c: number;
    peak_cycle_temperature_c: number;
    cooling_rate_deg_per_week: number;
  };
  fluid_state: {
    estimated_viscosity_cp: number;
    darcy_mobility_md_cp: number;
    oil_density_kg_m3: number;
  };
  production_state: {
    oil_rate_bpd: number;
    water_rate_bpd: number;
    cumulative_oil_bbl: number;
    pump_volumetric_efficiency_pct: number;
  };
  srp_operating_state: {
    spm: number;
    stroke_length_m: number;
    vfd_frequency_hz: number;
    pprl_lbs: number;
    mprl_lbs: number;
    motor_power_kw: number;
    kwh_per_barrel: number;
    rod_floating_detected: boolean;
    rod_floating_risk: number;
    impact_loading_risk: number;
  };
  pressure_state: {
    bottomhole_pressure_bar: number;
    wellhead_pressure_bar: number;
  };
  wellbore_profile_summary: Array<{
    depth_m: number;
    temperature_c: number;
    pressure_bar: number;
    viscosity_cp: number;
  }>;
  data_quality_score: string;
}

export interface DynoCardPoint {
  crank_angle_deg: number;
  position_in: number;
  position_m: number;
  surface_load_lbs: number;
  downhole_load_lbs: number;
}

export interface DynoCardData {
  well_id: string;
  stroke_length_m: number;
  spm: number;
  viscosity_cp: number;
  rod_floating_detected: boolean;
  card_points: DynoCardPoint[];
}

export interface ProductionForecast {
  model_name: string;
  model_version: string;
  training_dataset: string;
  current_viscosity_cp: number;
  physics_baseline_bpd: number;
  ml_residual_bpd: number;
  forecast_horizons: {
    t_plus_1: { day: number; prediction_bpd: number; lower_estimate_bpd: number; upper_estimate_bpd: number; uncertainty_pct: number };
    t_plus_7: { day: number; prediction_bpd: number; lower_estimate_bpd: number; upper_estimate_bpd: number; uncertainty_pct: number };
    t_plus_30: { day: number; prediction_bpd: number; lower_estimate_bpd: number; upper_estimate_bpd: number; uncertainty_pct: number };
  };
  data_quality: string;
  confidence: string;
}

export interface FailureIntelligence {
  model_version: string;
  overall_health_score: number;
  current_viscosity_cp: number;
  risks: {
    rod_floating: { probability: number; level: string; is_active_threat: boolean };
    impact_loading: { probability: number; level: string; is_active_threat: boolean };
    parted_rod: { probability: number; level: string; is_active_threat: boolean };
    pump_unseating: { probability: number; level: string; is_active_threat: boolean };
  };
  mechanical_loads: {
    pprl_lbs: number;
    mprl_lbs: number;
    viscous_drag_lbf: number;
    net_downstroke_force_lbs: number;
  };
  feature_contributions: Array<{
    feature: string;
    contribution_pct: number;
  }>;
  contribution_method: string;
  proactive_action_recommended: boolean;
  recommended_action: string;
}

export interface ParetoPoint {
  production_bpd: number;
  sor: number;
  energy_kwh_bbl: number;
  failure_risk: number;
  spm: number;
  stroke_m: number;
  steam_tons: number;
  composite_score: number;
}

export interface OptimizationResult {
  status: string;
  algorithm: string;
  recommended_plan: {
    css: {
      steam_volume_tons: number;
      soak_time_days: number;
      injection_pressure_bar: number | null;
      production_horizon_days: number;
      unsupported_controls: string[];
    };
    srp: {
      stroke_length_m: number;
      spm: number;
      vfd_frequency_hz: number;
      operating_mode: string;
    };
  } | null;
  expected_outcome: {
    production_bpd: number;
    production_change_pct: number | null;
    sor: number;
    sor_change_pct: number | null;
    energy_kwh_bbl: number;
    energy_change_pct: number | null;
    failure_risk: number;
    failure_risk_change_pct: number | null;
  } | null;
  physics_coupling?: {
    model_id: string;
    status: string;
    field_eligible: boolean;
    calibration_status: string;
    representative_chain: Array<{
      stage: string;
      inputs: Record<string, number | string>;
      outputs: Record<string, unknown>;
    }>;
  };
  constraint_verification: Record<string, string | boolean | string[]>;
  pareto_frontier: ParetoPoint[];
  rejected_alternatives_sample: Array<{
    spm: number;
    stroke_m: number;
    steam_tons: number;
    production_bpd: number;
    rejection_reason: string;
  }>;
  decision_support_disclaimer: string;
}

export interface SRPPerformance {
  stroke_length_m: number;
  spm: number;
  v_max_m_s: number;
  pprl_lbs: number;
  mprl_lbs: number;
  net_downstroke_force_lbs: number;
  viscous_drag_lbf: number;
  rod_floating_detected: boolean;
  rod_floating_risk: number;
  impact_loading_risk: number;
  theoretical_displacement_bpd: number;
  estimated_production_bpd: number;
  pump_efficiency_pct: number;
  electrical_power_kw: number;
  kwh_per_barrel: number;
  gearbox_peak_torque_in_lbs: number;
}

export interface ScenarioEvaluation {
  steam_mass_tons: number;
  soak_days: number;
  stroke_length_m: number;
  spm: number;
  vfd_frequency_hz: number;
  production_bpd: number;
  production_cutoff_days: number;
  estimated_cycle_oil_bbl: number;
  peak_temperature_c: number;
  heated_radius_m: number;
  total_heat_injected_gj: number;
  heat_retained_post_soak_gj: number;
  temperature_at_cycle_day_c: number;
  sor: number;
  energy_kwh_bbl: number;
  failure_risk: number;
  peak_polished_rod_load_lbs: number;
  viscosity_cp: number;
  coupled_model_id: string;
  coupling_chain: Array<{ stage: string; inputs: Record<string, unknown>; outputs: Record<string, unknown> }>;
  model_validation_status: string;
  field_eligible: boolean;
  is_feasible: boolean;
  violations: string[];
}

export interface SavedAnalysisRun {
  run_id: string;
  well_id: string;
  kind: string;
  source_mode: string;
  result: Record<string, unknown>;
  created_at: string;
}
