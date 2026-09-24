import React, { useState } from 'react';
import { Play, RotateCcw, Clock, Thermometer, Flame, Gauge, AlertTriangle, Layers } from 'lucide-react';
import { TelemetryFrame } from '../types/petro';
import { api } from '../services/api';

interface DigitalTwinProps {
  currentTelemetry: TelemetryFrame | null;
  selectedWell: string;
}

export const DigitalTwinView: React.FC<DigitalTwinProps> = ({ currentTelemetry, selectedWell }) => {
  const [scrubDay, setScrubDay] = useState<number>(currentTelemetry?.cycle_info.days_in_production || 68);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  // Derive dynamic state for the current scrubbed day
  const twinState = api.getTimeMachineState(selectedWell, scrubDay);

  const { thermal_state, fluid_state, srp_operating_state, production_state, wellbore_profile_summary } = twinState;

  // Thermal plume radius (scales with temperature: 47C is 0%, 200C is 100%)
  const plumeScale = Math.min(1.0, Math.max(0.15, (thermal_state.reservoir_temperature_c - 47.0) / 150.0));
  const isFloating = srp_operating_state.rod_floating_detected;

  // Handle play/pause time machine animation
  React.useEffect(() => {
    let timer: any;
    if (isPlaying) {
      timer = setInterval(() => {
        setScrubDay((prev) => {
          if (prev >= 150) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 2;
        });
      }, 150);
    }
    return () => clearInterval(timer);
  }, [isPlaying]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '24px 20px' }}>
      {/* Time Machine Control Bar */}
      <div className="glass-panel" style={{ padding: '18px 24px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '6px',
              background: 'rgba(0, 229, 255, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '1px solid rgba(0, 229, 255, 0.3)'
            }}>
              <Clock size={18} color="#00e5ff" />
            </div>
            <div>
              <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fff' }}>DIGITAL TWIN TIME MACHINE</div>
              <div style={{ fontSize: '0.74rem', color: '#94a3b8' }}>
                Scrub through the 180-day production lifecycle to simulate continuous reservoir thermal decay and mechanical stress
              </div>
            </div>
          </div>

          {/* Quick preset buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              style={{
                background: isPlaying ? '#ff334b' : '#00e5ff',
                color: '#000',
                border: 'none',
                borderRadius: '6px',
                padding: '6px 14px',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <Play size={12} fill="#000" />
              <span>{isPlaying ? 'PAUSE ANIMATION' : 'PLAY LIFECYCLE'}</span>
            </button>
            <button
              onClick={() => { setScrubDay(5); setIsPlaying(false); }}
              style={{
                background: 'rgba(255, 255, 255, 0.06)',
                color: '#cbd5e1',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '6px',
                padding: '6px 10px',
                fontSize: '0.75rem',
                cursor: 'pointer'
              }}
            >
              <RotateCcw size={12} />
            </button>
            {[
              { label: 'Day 5 (Hot Flush)', day: 5 },
              { label: 'Day 30 (Stable)', day: 30 },
              { label: 'Day 68 (Current)', day: 68 },
              { label: 'Day 95 (Cooling)', day: 95 },
              { label: 'Day 120 (Cut-Off)', day: 120 }
            ].map((p) => (
              <button
                key={p.day}
                onClick={() => { setScrubDay(p.day); setIsPlaying(false); }}
                style={{
                  background: scrubDay === p.day ? 'rgba(0, 229, 255, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                  color: scrubDay === p.day ? '#00e5ff' : '#94a3b8',
                  border: scrubDay === p.day ? '1px solid #00e5ff' : '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '4px',
                  padding: '5px 10px',
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {/* Time Slider */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)', color: '#64748b' }}>Day 0</span>
          <input
            type="range"
            min={1}
            max={150}
            value={scrubDay}
            onChange={(e) => { setScrubDay(parseInt(e.target.value)); setIsPlaying(false); }}
          />
          <div style={{
            background: '#161e30',
            border: '1px solid #00e5ff',
            padding: '4px 12px',
            borderRadius: '6px',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.88rem',
            fontWeight: 800,
            color: '#00e5ff',
            minWidth: '85px',
            textAlign: 'center'
          }}>
            DAY {scrubDay}
          </div>
        </div>
      </div>

      {/* Main Twin Schematic & State Panel */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '20px' }}>
        {/* Left: Discretized 2D Cyber-Physical Well Schematic */}
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.92rem', fontWeight: 700, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Layers size={16} color="#00e5ff" />
              <span>DISCRETIZED WELLBORE & RESERVOIR HYDRAULICS (950m TVD)</span>
            </span>
            <span className={`tech-badge ${isFloating ? 'badge-red' : 'badge-green'}`}>
              {isFloating ? 'ROD FLOATING DETECTED' : 'MECHANICAL HARMONIC OK'}
            </span>
          </div>

          {/* Schematic SVG Canvas */}
          <div style={{
            background: 'linear-gradient(180deg, #0d131f 0%, #171d2b 40%, #201712 100%)',
            borderRadius: '10px',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            padding: '20px',
            position: 'relative',
            height: '480px',
            display: 'flex',
            overflow: 'hidden'
          }}>
            {/* Depth Scale */}
            <div style={{ width: '60px', borderRight: '1px dashed rgba(255,255,255,0.1)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: '#64748b' }}>
              <span>0m (Surf)</span>
              <span>200m</span>
              <span>400m</span>
              <span>600m</span>
              <span>800m</span>
              <span style={{ color: '#00e5ff', fontWeight: 700 }}>900m (Pump)</span>
              <span style={{ color: '#ff6d00', fontWeight: 700 }}>950m (Res)</span>
            </div>

            {/* Well Diagram */}
            <div style={{ flex: 1, position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              {/* Surface Beam Unit Icon */}
              <div style={{
                position: 'absolute',
                top: 0,
                width: '160px',
                height: '50px',
                borderBottom: '3px solid #64748b',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#cbd5e1',
                fontSize: '0.72rem',
                fontFamily: 'var(--font-mono)'
              }}>
                [BEAM UNIT: {srp_operating_state.spm} SPM]
              </div>

              {/* Vertical Well Casing & Tubing */}
              <div style={{
                position: 'absolute',
                top: '50px',
                bottom: '80px',
                width: '28px',
                borderLeft: '2px solid #64748b',
                borderRight: '2px solid #64748b',
                background: 'rgba(0, 0, 0, 0.4)',
                display: 'flex',
                justifyContent: 'center'
              }}>
                {/* Sucker Rod String inside tubing */}
                <div style={{
                  width: '4px',
                  height: '100%',
                  background: isFloating ? '#ff334b' : '#00e5ff',
                  boxShadow: isFloating ? '0 0 8px #ff334b' : '0 0 6px #00e5ff',
                  transition: 'background 0.3s ease'
                }}></div>
              </div>

              {/* Subsurface SRP Pump Plunger (at 900m depth) */}
              <div style={{
                position: 'absolute',
                bottom: '80px',
                width: '40px',
                height: '24px',
                background: '#1e293b',
                border: '2px solid #00e5ff',
                borderRadius: '4px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.62rem',
                color: '#fff',
                fontFamily: 'var(--font-mono)'
              }}>
                PUMP
              </div>

              {/* Bottom Reservoir Thermal Plume Graphic */}
              <div style={{
                position: 'absolute',
                bottom: '10px',
                width: `${140 * plumeScale}px`,
                height: '60px',
                borderRadius: '50%',
                background: `radial-gradient(ellipse at center, rgba(255, 109, 0, ${0.8 * plumeScale}) 0%, rgba(255, 61, 0, ${0.4 * plumeScale}) 60%, rgba(0,0,0,0) 100%)`,
                filter: 'blur(8px)',
                transition: 'all 0.4s ease'
              }}></div>

              {/* Reservoir Label */}
              <div style={{
                position: 'absolute',
                bottom: '15px',
                textAlign: 'center',
                color: '#ff6d00',
                fontSize: '0.72rem',
                fontFamily: 'var(--font-mono)',
                fontWeight: 700
              }}>
                JODHPUR SANDSTONE RESERVOIR ({thermal_state.reservoir_temperature_c}°C)
              </div>
            </div>

            {/* Depth Segments Data Overlay */}
            <div style={{ width: '150px', display: 'flex', flexDirection: 'column', justifyContent: 'space-around', fontSize: '0.7rem', color: '#94a3b8' }}>
              {wellbore_profile_summary.map((seg, idx) => (
                <div key={idx} style={{ background: 'rgba(0,0,0,0.3)', padding: '3px 6px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.04)' }}>
                  <div style={{ color: '#fff', fontWeight: 600 }}>Depth {seg.depth_m}m</div>
                  <div style={{ color: '#ff6d00' }}>{seg.temperature_c}°C | {seg.viscosity_cp} cP</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Dynamic Physical State Indicators */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Dynamic Thermal Dissipation Card */}
          <div className="glass-panel" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <Thermometer size={18} color="#ff6d00" />
              <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#fff' }}>THERMAL DECAY & VISCOSITY RESPONSE</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px' }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Reservoir Temperature</div>
                <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#ff6d00', fontFamily: 'var(--font-mono)' }}>
                  {thermal_state.reservoir_temperature_c} °C
                </div>
                <div style={{ fontSize: '0.68rem', color: '#64748b', marginTop: '2px' }}>Native: 47.0°C | Peak: 192.0°C</div>
              </div>
              <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px' }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Fluid Viscosity (mu)</div>
                <div style={{ fontSize: '1.4rem', fontWeight: 800, color: fluid_state.estimated_viscosity_cp > 2200 ? '#ff334b' : '#ffb300', fontFamily: 'var(--font-mono)' }}>
                  {fluid_state.estimated_viscosity_cp} cP
                </div>
                <div style={{ fontSize: '0.68rem', color: '#64748b', marginTop: '2px' }}>Darcy Mobility: {fluid_state.darcy_mobility_md_cp} mD/cP</div>
              </div>
            </div>
          </div>

          {/* Dynamic SRP Kinematics & Rod Float Risk */}
          <div className="glass-panel" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <Gauge size={18} color="#00e5ff" />
              <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#fff' }}>SRP DYNAMICS & COUETTE DRAG</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px' }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Peak Rod Load (PPRL)</div>
                <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#00e5ff', fontFamily: 'var(--font-mono)' }}>
                  {srp_operating_state.pprl_lbs} lbs
                </div>
                <div style={{ fontSize: '0.68rem', color: '#64748b', marginTop: '2px' }}>MPRL: {srp_operating_state.mprl_lbs} lbs</div>
              </div>
              <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px' }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Rod Floating Probability</div>
                <div style={{ fontSize: '1.4rem', fontWeight: 800, color: isFloating ? '#ff334b' : '#00e676', fontFamily: 'var(--font-mono)' }}>
                  {Math.round(srp_operating_state.rod_floating_risk * 100)} %
                </div>
                <div style={{ fontSize: '0.68rem', color: isFloating ? '#ff334b' : '#00e676', marginTop: '2px' }}>
                  {isFloating ? 'CRITICAL SHOCK RISK' : 'POSITIVE SINKING MARGIN'}
                </div>
              </div>
            </div>

            {/* Explanatory text */}
            <div style={{ marginTop: '14px', fontSize: '0.76rem', color: '#cbd5e1', lineHeight: '1.4', background: 'rgba(0,0,0,0.25)', padding: '10px 12px', borderRadius: '6px' }}>
              <strong>Digital Twin Physics Insight:</strong> At Day {scrubDay}, the formation thermal dissipation has dropped bottomhole temperature to {thermal_state.reservoir_temperature_c}°C. 
              {isFloating 
                ? ' Viscous drag has exceeded rod gravitational sinking capability. The rod clamp is lifting off the carrier bar on downstroke, causing destructive impact pounding.'
                : ' Sinker bars maintain adequate gravitational downstroke sinking velocity. Operating in safe fatigue envelope.'}
            </div>
          </div>

          {/* Quick Action */}
          <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#fff' }}>Optimization Recommendation</div>
              <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Joint CSS steam volume + SRP VFD setpoints</div>
            </div>
            <button
              onClick={() => {}}
              style={{
                background: 'linear-gradient(135deg, #00e5ff 0%, #0077b6 100%)',
                color: '#000',
                border: 'none',
                borderRadius: '6px',
                padding: '8px 14px',
                fontSize: '0.78rem',
                fontWeight: 800,
                cursor: 'pointer'
              }}
            >
              RUN JOINT OPTIMIZER
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
