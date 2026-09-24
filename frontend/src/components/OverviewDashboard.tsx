import React from 'react';
import {
  Thermometer, Droplets, Zap, AlertTriangle, CheckCircle, Flame, ArrowUpRight, ArrowDownRight, Activity
} from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { TelemetryFrame } from '../types/petro';

interface DashboardProps {
  telemetry: TelemetryFrame | null;
  history: any[];
  onNavigateTab: (tab: string) => void;
}

export const OverviewDashboard: React.FC<DashboardProps> = ({ telemetry, history, onNavigateTab }) => {
  if (!telemetry) {
    return <div style={{ padding: '40px', color: '#94a3b8' }}>Loading telemetry stream...</div>;
  }

  const { thermal_state, fluid_state, production_state, srp_operating_state, cycle_info, pressure_state } = telemetry;
  const isRodFloating = srp_operating_state.rod_floating_detected;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '24px 20px' }}>
      {/* Top Banner Alert (If Rod Floating Threat Active) */}
      {isRodFloating && (
        <div style={{
          background: 'rgba(255, 51, 75, 0.12)',
          border: '1px solid rgba(255, 51, 75, 0.5)',
          borderRadius: '10px',
          padding: '14px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: '0 0 24px rgba(255, 51, 75, 0.25)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '50%',
              background: 'rgba(255, 51, 75, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <AlertTriangle color="#ff334b" size={22} />
            </div>
            <div>
              <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#ff334b', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>CRITICAL MECHANICAL THREAT: ROD FLOATING DETECTED</span>
                <span className="tech-badge badge-red">URGENT</span>
              </div>
              <div style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>
                Viscosity ({fluid_state.estimated_viscosity_cp} cP) Couette drag exceeds rod sinking capacity at {srp_operating_state.spm} SPM. Slack bridle cable is creating impact loading shock.
              </div>
            </div>
          </div>
          <button
            onClick={() => onNavigateTab('srp-optimizer')}
            style={{
              background: '#ff334b',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              padding: '8px 16px',
              fontSize: '0.82rem',
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            RESOLVE IN SRP OPTIMIZER
          </button>
        </div>
      )}

      {/* Main KPI Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '16px'
      }}>
        {/* KPI 1: Production */}
        <div className="glass-panel" style={{ padding: '18px 20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.78rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Oil Production</span>
            <Droplets size={16} color="#00e5ff" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
            <span className="metric-number" style={{ fontSize: '1.9rem', color: '#fff' }}>
              {production_state.oil_rate_bpd}
            </span>
            <span style={{ fontSize: '0.82rem', color: '#64748b' }}>bbl/day</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '6px', fontSize: '0.74rem', color: '#00e676' }}>
            <ArrowUpRight size={14} />
            <span>Water: {production_state.water_rate_bpd} bpd | Cum: {production_state.cumulative_oil_bbl} bbl</span>
          </div>
        </div>

        {/* KPI 2: Reservoir Temperature */}
        <div className="glass-panel" style={{ padding: '18px 20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.78rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Reservoir Temp (T_res)</span>
            <Thermometer size={16} color="#ff6d00" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
            <span className="metric-number" style={{ fontSize: '1.9rem', color: '#ff6d00' }}>
              {thermal_state.reservoir_temperature_c}
            </span>
            <span style={{ fontSize: '0.82rem', color: '#64748b' }}>°C</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '6px', fontSize: '0.74rem', color: '#94a3b8' }}>
            <ArrowDownRight size={14} color="#ff334b" />
            <span>Cooling from {thermal_state.peak_cycle_temperature_c}°C peak (Day {cycle_info.days_in_production})</span>
          </div>
        </div>

        {/* KPI 3: Fluid Viscosity */}
        <div className="glass-panel" style={{ padding: '18px 20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.78rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Estimated Viscosity</span>
            <Flame size={16} color={fluid_state.estimated_viscosity_cp > 2000 ? '#ff334b' : '#ffb300'} />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
            <span className="metric-number" style={{ fontSize: '1.9rem', color: fluid_state.estimated_viscosity_cp > 2000 ? '#ff334b' : '#fff' }}>
              {fluid_state.estimated_viscosity_cp}
            </span>
            <span style={{ fontSize: '0.82rem', color: '#64748b' }}>cP</span>
          </div>
          <div style={{ marginTop: '6px', fontSize: '0.74rem', color: '#64748b' }}>
            Mobility: {fluid_state.darcy_mobility_md_cp} mD/cP (Target: &gt; 0.5)
          </div>
        </div>

        {/* KPI 4: Polished Rod Loads */}
        <div className="glass-panel" style={{ padding: '18px 20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.78rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Peak Rod Load (PPRL)</span>
            <Activity size={16} color="#00e5ff" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
            <span className="metric-number" style={{ fontSize: '1.9rem', color: '#fff' }}>
              {srp_operating_state.pprl_lbs}
            </span>
            <span style={{ fontSize: '0.82rem', color: '#64748b' }}>lbs</span>
          </div>
          <div style={{ marginTop: '6px', fontSize: '0.74rem', color: '#94a3b8' }}>
            MPRL: {srp_operating_state.mprl_lbs} lbs | Rating: 22,000 lbs
          </div>
        </div>

        {/* KPI 5: Cumulative SOR & Energy */}
        <div className="glass-panel" style={{ padding: '18px 20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.78rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Steam-Oil Ratio (SOR)</span>
            <Zap size={16} color="#ffb300" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
            <span className="metric-number" style={{ fontSize: '1.9rem', color: '#ffb300' }}>
              {cycle_info.sor_cumulative}
            </span>
            <span style={{ fontSize: '0.82rem', color: '#64748b' }}>m³/m³</span>
          </div>
          <div style={{ marginTop: '6px', fontSize: '0.74rem', color: '#00e676' }}>
            Power: {srp_operating_state.kwh_per_barrel} kWh/bbl ({srp_operating_state.motor_power_kw} kW)
          </div>
        </div>
      </div>

      {/* 5 Health Cards Row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '14px'
      }}>
        {/* Reservoir Health */}
        <div className="glass-panel" style={{ padding: '14px 18px', borderLeft: '4px solid #00e5ff' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', fontWeight: 600 }}>RESERVOIR HEALTH</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px' }}>
            <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>Formation Stable</span>
            <span className="tech-badge badge-green">94%</span>
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '4px' }}>Pressure: {pressure_state.bottomhole_pressure_bar} bar (Native 55)</div>
        </div>

        {/* Pump Health */}
        <div className="glass-panel" style={{ padding: '14px 18px', borderLeft: '4px solid #00e676' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', fontWeight: 600 }}>PUMP HEALTH</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px' }}>
            <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>Volumetric Eff</span>
            <span className="tech-badge badge-cyan">{production_state.pump_volumetric_efficiency_pct}%</span>
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '4px' }}>Seated at 900m depth • Plunger 2.25"</div>
        </div>

        {/* Rod Health */}
        <div className="glass-panel" style={{ padding: '14px 18px', borderLeft: `4px solid ${isRodFloating ? '#ff334b' : '#ffb300'}` }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', fontWeight: 600 }}>ROD STRING HEALTH</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px' }}>
            <span style={{ fontSize: '1.1rem', fontWeight: 700, color: isRodFloating ? '#ff334b' : '#fff' }}>
              {isRodFloating ? 'Floats / Shock' : 'Goodman Normal'}
            </span>
            <span className={`tech-badge ${isRodFloating ? 'badge-red' : 'badge-amber'}`}>
              Risk: {Math.round(srp_operating_state.rod_floating_risk * 100)}%
            </span>
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '4px' }}>API Grade D Steel • Sinker Bar Section OK</div>
        </div>

        {/* Thermal State */}
        <div className="glass-panel" style={{ padding: '14px 18px', borderLeft: '4px solid #ff6d00' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', fontWeight: 600 }}>THERMAL STATE</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px' }}>
            <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>Cooling Phase</span>
            <span className="tech-badge badge-sim">Cycle {cycle_info.cycle_number}</span>
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '4px' }}>Days in Cycle: {cycle_info.days_in_production} of ~120</div>
        </div>

        {/* Production State */}
        <div className="glass-panel" style={{ padding: '14px 18px', borderLeft: '4px solid #3b82f6' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', fontWeight: 600 }}>DATA QUALITY</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px' }}>
            <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>Signal Integrity</span>
            <span className="tech-badge badge-green">GOOD (100%)</span>
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '4px' }}>Monotonic • Range Validated • No Spikes</div>
        </div>
      </div>

      {/* Real-Time Historical Telemetry Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))', gap: '20px' }}>
        {/* Chart 1: Production & Thermal Decay Trend */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fff' }}>90-Day Production & Thermal Dissipation Trend</div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Correlated CSS thermal cooling vs heavy oil inflow decay</div>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', color: '#00e5ff' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#00e5ff' }}></span> Oil Rate (bpd)
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', color: '#ff6d00' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ff6d00' }}></span> Temp (°C)
              </span>
            </div>
          </div>
          <div style={{ width: '100%', height: '260px' }}>
            <ResponsiveContainer>
              <AreaChart data={history}>
                <defs>
                  <linearGradient id="colorOil" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00e5ff" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#00e5ff" stopOpacity={0.0}/>
                  </linearGradient>
                  <linearGradient id="colorTemp" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ff6d00" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#ff6d00" stopOpacity={0.0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="day" stroke="#64748b" tick={{ fontSize: 11 }} label={{ value: 'Cycle Day', position: 'insideBottomRight', offset: -4, fill: '#64748b' }} />
                <YAxis yAxisId="left" stroke="#00e5ff" tick={{ fontSize: 11 }} />
                <YAxis yAxisId="right" orientation="right" stroke="#ff6d00" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ background: '#0d121c', borderColor: 'rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '0.78rem' }} />
                <Area yAxisId="left" type="monotone" dataKey="oil_rate_bpd" stroke="#00e5ff" fillOpacity={1} fill="url(#colorOil)" strokeWidth={2} name="Oil (bpd)" />
                <Area yAxisId="right" type="monotone" dataKey="reservoir_temperature_c" stroke="#ff6d00" fillOpacity={1} fill="url(#colorTemp)" strokeWidth={2} name="Temp (°C)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Polished Rod Load & Rod Floating Risk Build-Up */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fff' }}>Polished Rod Load vs Viscosity Drag</div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Downstroke MPRL drops as fluid viscosity triggers rod floating</div>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', color: '#00e5ff' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#00e5ff' }}></span> PPRL (lbs)
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', color: '#ff334b' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ff334b' }}></span> MPRL (lbs)
              </span>
            </div>
          </div>
          <div style={{ width: '100%', height: '260px' }}>
            <ResponsiveContainer>
              <AreaChart data={history}>
                <defs>
                  <linearGradient id="colorPPRL" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00e5ff" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#00e5ff" stopOpacity={0.0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="day" stroke="#64748b" tick={{ fontSize: 11 }} />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} domain={[0, 20000]} />
                <Tooltip contentStyle={{ background: '#0d121c', borderColor: 'rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '0.78rem' }} />
                <Area type="monotone" dataKey="pprl_lbs" stroke="#00e5ff" fill="url(#colorPPRL)" strokeWidth={2} name="PPRL (lbs)" />
                <Area type="monotone" dataKey="mprl_lbs" stroke="#ff334b" fill="none" strokeWidth={2} name="MPRL (lbs)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
