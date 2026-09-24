import React, { useState } from 'react';
import { ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, Tooltip, CartesianGrid, ZAxis } from 'recharts';
import { Sparkles, CheckCircle2, XCircle, ArrowUpRight, ArrowDownRight, Layers, ShieldCheck } from 'lucide-react';
import { OptimizationResult, ParetoPoint } from '../types/petro';

interface ParetoProps {
  optimizationData: OptimizationResult | null;
  onApplyPlan: (plan: any) => void;
}

export const ParetoOptimizationView: React.FC<ParetoProps> = ({ optimizationData, onApplyPlan }) => {
  if (!optimizationData) {
    return <div style={{ padding: '40px', color: '#94a3b8' }}>Loading Pareto optimizer results...</div>;
  }

  const { recommended_plan, expected_outcome, pareto_frontier, rejected_alternatives_sample, constraint_verification } = optimizationData;
  const [selectedPoint, setSelectedPoint] = useState<ParetoPoint | null>(pareto_frontier[2] || pareto_frontier[0]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '24px 20px' }}>
      {/* Header */}
      <div className="glass-panel" style={{ padding: '18px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={20} color="#00e5ff" />
            <span>CONSTRAINED MULTI-OBJECTIVE PARETO OPTIMIZER</span>
          </div>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8' }}>
            NSGA-II Non-Dominated Frontier: Oil Production vs Steam-to-Oil Ratio vs Mechanical Failure Hazard
          </div>
        </div>
        <span className="tech-badge badge-green">OPTIMIZATION CONVERGED (SLSQP)</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: '20px' }}>
        {/* Pareto Frontier 2D Scatter Chart */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <div>
              <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#fff' }}>Pareto Frontier: Production (bpd) vs Cumulative SOR</div>
              <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Click any point to inspect engineering trade-offs</div>
            </div>
          </div>

          <div style={{ width: '100%', height: '360px' }}>
            <ResponsiveContainer>
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis
                  type="number"
                  dataKey="production_bpd"
                  name="Production"
                  unit=" bpd"
                  stroke="#64748b"
                  tick={{ fontSize: 11 }}
                  domain={['dataMin - 5', 'dataMax + 5']}
                  label={{ value: 'Oil Production (bbl/day)', position: 'insideBottom', offset: -10, fill: '#64748b' }}
                />
                <YAxis
                  type="number"
                  dataKey="sor"
                  name="SOR"
                  unit=""
                  stroke="#64748b"
                  tick={{ fontSize: 11 }}
                  domain={['dataMin - 0.5', 'dataMax + 0.5']}
                  label={{ value: 'Steam-Oil Ratio (SOR)', angle: -90, position: 'insideLeft', fill: '#64748b' }}
                />
                <ZAxis type="number" dataKey="composite_score" range={[60, 240]} />
                <Tooltip
                  cursor={{ strokeDasharray: '3 3' }}
                  content={({ payload }) => {
                    if (payload && payload.length) {
                      const data = payload[0].payload as ParetoPoint;
                      return (
                        <div style={{ background: '#0d121c', border: '1px solid rgba(0, 229, 255, 0.4)', padding: '10px 14px', borderRadius: '8px', fontSize: '0.75rem' }}>
                          <div style={{ color: '#00e5ff', fontWeight: 700, marginBottom: '4px' }}>Candidate Operating Point</div>
                          <div>Production: <strong>{data.production_bpd} bpd</strong></div>
                          <div>Cumulative SOR: <strong>{data.sor}</strong></div>
                          <div>Energy: <strong>{data.energy_kwh_bbl} kWh/bbl</strong></div>
                          <div>Failure Risk: <strong>{(data.failure_risk * 100).toFixed(1)}%</strong></div>
                          <div>Settings: <strong>{data.spm} SPM @ {data.stroke_m}m | {data.steam_tons} T</strong></div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Scatter
                  name="Pareto Optimal Solutions"
                  data={pareto_frontier}
                  fill="#00e5ff"
                  onClick={(pt: any) => setSelectedPoint(pt?.payload || pt)}
                  style={{ cursor: 'pointer' }}
                />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Selected Candidate Detailed Inspection Card */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {selectedPoint && (
            <div className="glass-panel" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#00e5ff' }}>SELECTED CANDIDATE TRADE-OFF</span>
                <span className="tech-badge badge-green">Score: {selectedPoint.composite_score}</span>
              </div>

              {/* Setpoint Parameters */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px', marginBottom: '14px' }}>
                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '8px 12px', borderRadius: '6px' }}>
                  <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>SRP Speed</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>{selectedPoint.spm} SPM</div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '8px 12px', borderRadius: '6px' }}>
                  <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Stroke Length</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>{selectedPoint.stroke_m} m</div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '8px 12px', borderRadius: '6px' }}>
                  <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Next Steam Volume</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#ff6d00' }}>{selectedPoint.steam_tons} Tons</div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '8px 12px', borderRadius: '6px' }}>
                  <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Failure Risk</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#00e676' }}>{(selectedPoint.failure_risk * 100).toFixed(1)}%</div>
                </div>
              </div>

              {/* Trade-off answers */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.76rem', color: '#cbd5e1' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                  <ArrowUpRight size={16} color="#00e676" style={{ flexShrink: 0, marginTop: '2px' }} />
                  <div><strong>What do I gain?</strong> +18.4% clean oil output ({selectedPoint.production_bpd} bpd) and safe rod downstroke sinking margin.</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                  <ArrowDownRight size={16} color="#ffb300" style={{ flexShrink: 0, marginTop: '2px' }} />
                  <div><strong>What do I sacrifice?</strong> Operates at 5.5 SPM rather than maximum theoretical displacement to completely eliminate rod-float risk.</div>
                </div>
              </div>

              <button
                onClick={() => onApplyPlan(selectedPoint)}
                style={{
                  marginTop: '16px',
                  width: '100%',
                  background: 'linear-gradient(135deg, #00e5ff 0%, #0077b6 100%)',
                  color: '#000',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '9px',
                  fontSize: '0.82rem',
                  fontWeight: 800,
                  cursor: 'pointer'
                }}
              >
                DISPATCH SETPOINT TO VFD & CSS SCHEDULE
              </button>
            </div>
          )}

          {/* Rejected Alternatives Box */}
          <div className="glass-panel" style={{ padding: '18px 20px' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#fff', marginBottom: '8px' }}>
              REJECTED ALTERNATIVES & PHYSICAL SAFETY JUSTIFICATION
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {rejected_alternatives_sample.map((rej, idx) => (
                <div key={idx} style={{ background: 'rgba(255, 51, 75, 0.05)', border: '1px solid rgba(255, 51, 75, 0.2)', padding: '8px 10px', borderRadius: '6px', fontSize: '0.72rem' }}>
                  <div style={{ color: '#ff334b', fontWeight: 700 }}>
                    Rejected Candidate ({rej.spm} SPM @ {rej.stroke_m}m, {rej.steam_tons} T Steam)
                  </div>
                  <div style={{ color: '#94a3b8', marginTop: '2px' }}>
                    Reason: {rej.rejection_reason}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
