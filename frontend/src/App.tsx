import React, { Suspense, lazy, useState, useEffect } from 'react';
import { AuthGate } from './components/AuthGate';
import { Navbar } from './components/Navbar';
import { AICopilotDrawer } from './components/AICopilotDrawer';
import { JuryDemoModal } from './components/JuryDemoModal';

const OverviewDashboard = lazy(() => import('./components/OverviewDashboard').then((m) => ({ default: m.OverviewDashboard })));
const DigitalTwinView = lazy(() => import('./components/DigitalTwinView').then((m) => ({ default: m.DigitalTwinView })));
const DynamometerCard = lazy(() => import('./components/DynamometerCard').then((m) => ({ default: m.DynamometerCard })));
const CSSOptimizerView = lazy(() => import('./components/CSSOptimizerView').then((m) => ({ default: m.CSSOptimizerView })));
const SRPOptimizerView = lazy(() => import('./components/SRPOptimizerView').then((m) => ({ default: m.SRPOptimizerView })));
const FailureIntelligenceView = lazy(() => import('./components/FailureIntelligenceView').then((m) => ({ default: m.FailureIntelligenceView })));
const ScenarioLabView = lazy(() => import('./components/ScenarioLabView').then((m) => ({ default: m.ScenarioLabView })));
const ParetoOptimizationView = lazy(() => import('./components/ParetoOptimizationView').then((m) => ({ default: m.ParetoOptimizationView })));
const SavedRunsView = lazy(() => import('./components/SavedRunsView').then((m) => ({ default: m.SavedRunsView })));
const DataWorkspaceView = lazy(() => import('./components/DataWorkspaceView').then((m) => ({ default: m.DataWorkspaceView })));
const FieldModelsView = lazy(() => import('./components/FieldModelsView').then((m) => ({ default: m.FieldModelsView })));

import { api } from './services/api';
import {
  WellId,
  TelemetryFrame,
  DynoCardData,
  FailureIntelligence,
  OptimizationResult,
  WellSummary,
  ProductionForecast
} from './types/petro';

function MainApp() {
  const [selectedWell, setSelectedWell] = useState<WellId>('');
  const [dataMode, setDataMode] = useState('CONNECTING');
  const [initialized, setInitialized] = useState(false);
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [isCopilotOpen, setIsCopilotOpen] = useState<boolean>(false);
  const [isJuryModalOpen, setIsJuryModalOpen] = useState<boolean>(false);

  // Core Data States
  const [telemetry, setTelemetry] = useState<TelemetryFrame | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [dynoData, setDynoData] = useState<DynoCardData | null>(null);
  const [failureData, setFailureData] = useState<FailureIntelligence | null>(null);
  const [optData, setOptData] = useState<OptimizationResult | null>(null);
  const [serviceError, setServiceError] = useState<string | null>(null);
  const [wells, setWells] = useState<WellSummary[]>([]);
  const [optimizationRunning, setOptimizationRunning] = useState(false);
  const [forecast, setForecast] = useState<ProductionForecast | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);

  // Load the backend's configured mode and well registry before requesting any well data.
  useEffect(() => {
    let isMounted = true;
    api.getHealth().then(async (health) => {
      const { wells: knownWells } = await api.getWells();
      if (!isMounted) return;
      setDataMode(health.data_mode);
      setWells(knownWells);
      setSelectedWell((current) => knownWells.some((well) => well.well_id === current) ? current : (knownWells[0]?.well_id ?? ''));
      setInitialized(true);
      setServiceError(null);
    }).catch((err: unknown) => {
      if (isMounted) {
        setInitialized(true);
        setServiceError(err instanceof Error ? err.message : 'Unable to connect to backend.');
      }
    });
    return () => { isMounted = false; };
  }, []);

  // Simulation-only twin endpoints are requested only when the API explicitly reports simulation mode.
  useEffect(() => {
    if (!initialized || !selectedWell || dataMode !== 'SIMULATION') return;
    let isMounted = true;
    setTelemetry(null);
    setDynoData(null);
    setFailureData(null);
    setOptData(null);
    setForecast(null);
    setHistory([]);
    setServiceError(null);

    const fetchData = async () => {
      try {
        const [tel, dyno, fail] = await Promise.all([
          api.getTelemetry(selectedWell),
          api.getDynoCard(selectedWell),
          api.getFailureIntelligence(selectedWell)
        ]);

        if (isMounted) {
          setTelemetry(tel);
          setDynoData(dyno);
          setFailureData(fail);
          setServiceError(null);
        }
      } catch (err) {
        if (isMounted) setServiceError(err instanceof Error ? err.message : 'Unable to load well data.');
      }
    };

    const loadInitial = async () => {
      await fetchData();
      try {
        const [historyResponse, wellResponse] = await Promise.all([
          api.getProductionHistory(selectedWell),
          api.getWells()
        ]);
        if (isMounted) {
          setHistory(historyResponse.history as any[]);
          setWells(wellResponse.wells);
        }
      } catch (err) {
        if (isMounted) setServiceError(err instanceof Error ? err.message : 'Unable to load analysis results.');
      }
    };
    loadInitial();
    const interval = setInterval(fetchData, 10000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [selectedWell, dataMode, initialized]);

  useEffect(() => {
    if (!initialized || !selectedWell || dataMode === 'SIMULATION') return;
    let isMounted = true;
    api.getProductionHistory(selectedWell).then((response) => {
      if (isMounted) setHistory(response.history);
    }).catch(() => { if (isMounted) setHistory([]); });
    return () => { isMounted = false; };
  }, [selectedWell, dataMode, initialized]);

  const runOptimization = async () => {
    setOptimizationRunning(true);
    setOptData(null);
    try {
      setOptData(await api.runOptimization(selectedWell));
      setServiceError(null);
    } catch (err) {
      setServiceError(err instanceof Error ? err.message : 'Optimization failed.');
    } finally {
      setOptimizationRunning(false);
    }
  };

  const requestForecast = async () => {
    setForecastLoading(true);
    try {
      setForecast(await api.getProductionForecast(selectedWell));
      setServiceError(null);
    } catch (err) {
      setServiceError(err instanceof Error ? err.message : 'Production forecast failed.');
    } finally {
      setForecastLoading(false);
    }
  };

  const handleApplyPlan = (plan: any) => {
    alert(`Decision-support recommendation only. No setpoint was dispatched or saved.\nSPM: ${plan.spm} | Stroke: ${plan.stroke_m}m | Steam: ${plan.steam_tons} T`);
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-primary)' }}>
      {/* Top Navigation */}
      <Navbar
        selectedWell={selectedWell}
        onSelectWell={(w) => setSelectedWell(w)}
        wells={wells}
        activeTab={activeTab}
        onSelectTab={(t) => setActiveTab(t)}
        onOpenJuryDemo={() => setIsJuryModalOpen(true)}
        onOpenCopilot={() => setIsCopilotOpen(true)}
        dataMode={dataMode}
      />

      {/* Main Dynamic Viewport */}
      {serviceError && (
        <div role="alert" style={{ padding: '12px 20px', color: '#991b1b', background: '#fef2f2', borderBottom: '1px solid #fecaca', fontWeight: 700 }}>
          Request unavailable: {serviceError}. Values are not being replaced with mock data.
        </div>
      )}
      <main style={{ flex: 1, maxWidth: '1680px', width: '100%', margin: '0 auto' }}>
        <Suspense fallback={<section role="status" style={{ margin: 24, padding: 20 }}>Loading workspace…</section>}>
        {activeTab === 'dashboard' && dataMode !== 'SIMULATION' && (
          <section style={{ padding: 24 }}>
            <div className="glass-panel" style={{ padding: 20 }} role="status">
              <h1 style={{ marginTop: 0 }}>Field mode — measured data only</h1>
              {!initialized ? 'Connecting to backend…' : wells.length === 0
                ? 'No wells are registered. Open Field Data to register a well and import measured records.'
                : !telemetry
                  ? `Selected well ${selectedWell} is registered. The synthetic digital twin is disabled in field mode; measured history is shown only when records exist.`
                  : `Measured well ${selectedWell} is available.`}
              {history.length > 0 && <p>{history.length} measured history records loaded. They are observational records, not a synthesized live telemetry frame.</p>}
            </div>
          </section>
        )}
        {activeTab === 'dashboard' && dataMode === 'SIMULATION' && (
          <OverviewDashboard
            telemetry={telemetry}
            history={history}
            onNavigateTab={(t) => setActiveTab(t)}
            forecast={forecast}
            onRequestForecast={requestForecast}
            forecastLoading={forecastLoading}
          />
        )}

        {activeTab === 'digital-twin' && (
          <DigitalTwinView
            currentTelemetry={telemetry}
            selectedWell={selectedWell}
          />
        )}

        {activeTab === 'live-ops' && (
          <DynamometerCard
            dynoData={dynoData}
            onRefresh={async () => {
              const d = await api.getDynoCard(selectedWell);
              setDynoData(d);
            }}
          />
        )}

        {activeTab === 'css-optimizer' && <CSSOptimizerView />}

        {activeTab === 'srp-optimizer' && <SRPOptimizerView />}

        {activeTab === 'failures' && (
          <FailureIntelligenceView failureData={failureData} />
        )}

        {activeTab === 'scenario-lab' && <ScenarioLabView selectedWell={selectedWell} />}

        {activeTab === 'pareto' && (
          <ParetoOptimizationView
            optimizationData={optData}
            onRunOptimization={runOptimization}
            isRunning={optimizationRunning}
            onApplyPlan={handleApplyPlan}
          />
        )}
        {activeTab === 'saved-runs' && (selectedWell
          ? <SavedRunsView wellId={selectedWell} />
          : <section className="glass-panel" style={{ margin: 24, padding: 20 }} role="status">Register or select a well to view saved runs.</section>)}
        {activeTab === 'data-workspace' && <DataWorkspaceView wellId={selectedWell} onWellCreated={(well) => {
          setWells((existing) => [...existing.filter((item) => item.well_id !== well.well_id), well]);
          if (dataMode !== 'SIMULATION') setSelectedWell(well.well_id);
        }} />}
        {activeTab === 'field-models' && <FieldModelsView selectedWell={selectedWell} dataMode={dataMode} />}
        </Suspense>
      </main>

      {/* AI Copilot Side Drawer */}
      <AICopilotDrawer
        isOpen={isCopilotOpen}
        onClose={() => setIsCopilotOpen(false)}
        selectedWell={selectedWell}
      />

      {/* 5-Minute Guided System Walkthrough */}
      <JuryDemoModal
        isOpen={isJuryModalOpen}
        onClose={() => setIsJuryModalOpen(false)}
        onNavigateTab={(t) => setActiveTab(t)}
      />

      {/* Industrial Footer */}
      <footer style={{
        padding: '16px 24px',
        borderTop: '1px solid var(--border)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontSize: '0.74rem',
        color: 'var(--text-muted)',
        background: '#ffffff'
      }}>
          <div style={{ fontWeight: 600 }}>
          PETRO-TWIN AI • SIH26120 Synthetic Decision-Support Prototype
        </div>
        <div style={{ display: 'flex', gap: '16px', fontWeight: 600 }}>
          <span>Physics-Informed Hybrid Digital Twin</span>
          <span>Marx-Langenheim / ASTM D341 / API RP 11L</span>
          <span style={{ color: 'var(--accent-amber)', fontWeight: 800 }}>{dataMode} MODE</span>
        </div>
      </footer>
    </div>
  );
}

export function App() {
  return <AuthGate><MainApp /></AuthGate>;
}

export default App;
