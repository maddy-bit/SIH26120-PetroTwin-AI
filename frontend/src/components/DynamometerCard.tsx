import React from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from 'recharts';
import { Activity, AlertTriangle, ShieldCheck, HelpCircle } from 'lucide-react';
import { DynoCardData } from '../types/petro';

interface DynoCardProps {
  dynoData: DynoCardData | null;
  onRefresh: () => void;
}

export const DynamometerCard: React.FC<DynoCardProps> = ({ dynoData }) => {
  if (!dynoData) {
    return <div style={{ padding: '40px', color: '#94a3b8' }}>Loading dynamometer card...</div>;
  }

  const { card_points, stroke_length_m, spm, viscosity_cp, rod_floating_detected } = dynoData;
  const strokeIn = Math.round(stroke_length_m * 39.3701);

  // Compute maximum and minimum loads from points
  const maxLoad = Math.max(...card_points.map((p) => p.surface_load_lbs));
  const minLoad = Math.min(...card_points.map((p) => p.surface_load_lbs));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '24px 20px' }}>
      {/* Header Bar */}
      <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity size={20} color="#00e5ff" />
            <span>REAL-TIME SUCKER ROD DYNAMOMETER CARD ANALYZER</span>
          </div>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8' }}>
            Surface Polished Rod Load & Downhole Pump Barrel Load vs Polished Rod Position (API RP 11L)
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div className={`tech-badge ${rod_floating_detected ? 'badge-red' : 'badge-green'}`} style={{ padding: '6px 12px' }}>
            {rod_floating_detected ? <AlertTriangle size={14} /> : <ShieldCheck size={14} />}
            <span>{rod_floating_detected ? 'ROD FLOATING / SLACK BRIDLE DETECTED' : 'CARD SIGNATURE NORMAL'}</span>
          </div>
        </div>
      </div>

      {/* Main Dynamometer Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '20px' }}>
        {/* Left: Load vs Position Dyno Card Chart */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#fff' }}>Load vs Position Closed Cycle (1 Full Stroke)</span>
            <div style={{ display: 'flex', gap: '12px', fontSize: '0.74rem' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#00e5ff' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#00e5ff' }}></span> Surface Card (PPRL/MPRL)
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#ffb300' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ffb300' }}></span> Downhole Plunger Card
              </span>
            </div>
          </div>

          <div style={{ width: '100%', height: '380px' }}>
            <ResponsiveContainer>
              <LineChart data={card_points}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis
                  dataKey="position_in"
                  stroke="#64748b"
                  type="number"
                  domain={[0, strokeIn]}
                  tick={{ fontSize: 11 }}
                  label={{ value: 'Polished Rod Position (inches)', position: 'insideBottom', offset: -4, fill: '#64748b' }}
                />
                <YAxis
                  stroke="#64748b"
                  tick={{ fontSize: 11 }}
                  domain={[0, 24000]}
                  label={{ value: 'Load (lbf)', angle: -90, position: 'insideLeft', fill: '#64748b' }}
                />
                <Tooltip contentStyle={{ background: '#0d121c', borderColor: 'rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '0.78rem' }} />
                
                {/* Structural limit lines */}
                <ReferenceLine y={22000} stroke="#ff334b" strokeDasharray="4 4" label={{ value: 'API Beam Structure Limit (22k lbs)', fill: '#ff334b', fontSize: 10 }} />
                <ReferenceLine y={1200} stroke="#ffb300" strokeDasharray="4 4" label={{ value: 'Rod Float Minimum Limit (1.2k lbs)', fill: '#ffb300', fontSize: 10 }} />

                <Line
                  type="monotone"
                  dataKey="surface_load_lbs"
                  stroke="#00e5ff"
                  strokeWidth={2.5}
                  dot={{ r: 2 }}
                  name="Surface Load (lbs)"
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="downhole_load_lbs"
                  stroke="#ffb300"
                  strokeWidth={1.8}
                  strokeDasharray="3 3"
                  dot={false}
                  name="Downhole Load (lbs)"
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Right: Kinematics & Card Interpretation */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Kinematics Card */}
          <div className="glass-panel" style={{ padding: '20px' }}>
            <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#fff', marginBottom: '12px' }}>
              KINEMATIC & LOADING METRICS
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div style={{ background: 'rgba(255,255,255,0.03)', padding: '10px 12px', borderRadius: '6px' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Peak Surface Load</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#00e5ff', fontFamily: 'var(--font-mono)' }}>
                  {maxLoad} lbs
                </div>
              </div>
              <div style={{ background: 'rgba(255,255,255,0.03)', padding: '10px 12px', borderRadius: '6px' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Minimum Surface Load</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 800, color: minLoad < 1200 ? '#ff334b' : '#ffb300', fontFamily: 'var(--font-mono)' }}>
                  {minLoad} lbs
                </div>
              </div>
              <div style={{ background: 'rgba(255,255,255,0.03)', padding: '10px 12px', borderRadius: '6px' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Stroke Length & SPM</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', fontFamily: 'var(--font-mono)' }}>
                  {stroke_length_m}m @ {spm} SPM
                </div>
              </div>
              <div style={{ background: 'rgba(255,255,255,0.03)', padding: '10px 12px', borderRadius: '6px' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Fluid Viscosity</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#ff6d00', fontFamily: 'var(--font-mono)' }}>
                  {viscosity_cp} cP
                </div>
              </div>
            </div>
          </div>

          {/* Diagnostic Interpretation */}
          <div className="glass-panel" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
              <HelpCircle size={16} color="#00e5ff" />
              <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#fff' }}>PHYSICAL CARD DIAGNOSTICS</span>
            </div>
            <div style={{ fontSize: '0.78rem', color: '#cbd5e1', lineHeight: '1.5' }}>
              {rod_floating_detected ? (
                <div>
                  <p style={{ color: '#ff334b', fontWeight: 700, marginBottom: '6px' }}>
                    Warning: Rod Floating & Impact Pounding Signature Detected
                  </p>
                  <p>
                    The downstroke load has collapsed towards zero because upward Couette viscous shear force exceeds the downward rod weight. 
                    Slack bridle cables will violently re-engage at the turnaround, propagating destructive tensile shock waves down the steel string.
                  </p>
                </div>
              ) : (
                <div>
                  <p style={{ color: '#00e676', fontWeight: 700, marginBottom: '6px' }}>
                    Normal Harmonic Operation
                  </p>
                  <p>
                    Smooth load build-up on upstroke (traveling valve closure) and regular load release on downstroke. 
                    Net downstroke accelerating force is well above the minimum rod float threshold.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
