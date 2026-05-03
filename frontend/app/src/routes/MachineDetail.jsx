import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getMachine, getComponents, getPredictions, getSensors,
  getAlarms, getMaintenanceLog, getSensorHistory,
} from '../lib/api.js';
import MachineHeader from '../components/MachineHeader.jsx';
import ComponentHealthRow from '../components/ComponentHealthRow.jsx';
import SensorGrid from '../components/SensorGrid.jsx';
import SensorHistoryChart from '../components/SensorHistoryChart.jsx';
import AlarmsTable from '../components/AlarmsTable.jsx';
import MaintenanceLog from '../components/MaintenanceLog.jsx';

export default function MachineDetail() {
  const { machine_id } = useParams();

  // 6 independent fetches per machine. Each tracked separately so partial
  // failures (e.g. maintenance-log down) don't blank the whole page.
  const [machine, setMachine] = useState({ status: 'loading', data: null, error: null });
  const [components, setComponents] = useState({ status: 'loading', data: null, error: null });
  const [predictions, setPredictions] = useState({ status: 'loading', data: null, error: null });
  const [sensors, setSensors] = useState({ status: 'loading', data: null, error: null });
  const [alarms, setAlarms] = useState({ status: 'loading', data: null, error: null });
  const [maintenance, setMaintenance] = useState({ status: 'loading', data: null, error: null });

  // Sensor history is keyed on (machine_id, selectedSensor) so it refetches
  // when the user clicks a different sensor cell.
  const [history, setHistory] = useState({ status: 'idle', data: null, error: null });
  const [selectedSensor, setSelectedSensor] = useState(null);

  // Fire all 6 main fetches when the machine_id in the URL changes.
  useEffect(() => {
    if (!machine_id) return;
    let cancelled = false;

    setMachine({ status: 'loading', data: null, error: null });
    setComponents({ status: 'loading', data: null, error: null });
    setPredictions({ status: 'loading', data: null, error: null });
    setSensors({ status: 'loading', data: null, error: null });
    setAlarms({ status: 'loading', data: null, error: null });
    setMaintenance({ status: 'loading', data: null, error: null });
    setSelectedSensor(null);
    setHistory({ status: 'idle', data: null, error: null });

    const guard = (setter) => ({
      ok: (data) => { if (!cancelled) setter({ status: 'ok', data, error: null }); },
      err: (error) => { if (!cancelled) setter({ status: 'error', data: null, error }); },
    });

    const m = guard(setMachine);
    const c = guard(setComponents);
    const p = guard(setPredictions);
    const s = guard(setSensors);
    const a = guard(setAlarms);
    const ml = guard(setMaintenance);

    getMachine(machine_id).then(m.ok).catch(m.err);
    getComponents(machine_id).then(c.ok).catch(c.err);
    getPredictions(machine_id).then(p.ok).catch(p.err);
    getSensors(machine_id).then(s.ok).catch(s.err);
    getAlarms(machine_id).then(a.ok).catch(a.err);
    getMaintenanceLog(machine_id).then(ml.ok).catch(ml.err);

    return () => { cancelled = true; };
  }, [machine_id]);

  // Once sensors load and nothing is selected yet, pick the default. Mirrors
  // mockData.getDefaultSensorType: highest-anomaly-score, else yankee_surface_temp.
  useEffect(() => {
    if (sensors.status !== 'ok' || selectedSensor) return;
    const list = sensors.data;
    const anomalies = list.filter((s) => s.is_anomaly);
    if (anomalies.length > 0) {
      setSelectedSensor(
        anomalies.sort((a, b) => b.anomaly_score - a.anomaly_score)[0].sensor_type
      );
    } else {
      setSelectedSensor('yankee_surface_temp');
    }
  }, [sensors, selectedSensor]);

  // Refetch sensor history whenever (machine, sensor) changes.
  useEffect(() => {
    if (!selectedSensor || !machine_id) return;
    let cancelled = false;
    setHistory({ status: 'loading', data: null, error: null });
    getSensorHistory(machine_id, selectedSensor)
      .then((data) => { if (!cancelled) setHistory({ status: 'ok', data, error: null }); })
      .catch((error) => { if (!cancelled) setHistory({ status: 'error', data: null, error }); });
    return () => { cancelled = true; };
  }, [machine_id, selectedSensor]);

  // Full-page error: machine itself failed to load (likely 404).
  if (machine.status === 'error') {
    return (
      <div className="px-8 py-7 max-w-[1200px]">
        <div className="bg-white rounded-xl shadow-card p-8 text-center">
          <h1 className="text-lg font-semibold text-navy mb-1">Machine not available</h1>
          <p className="text-sm text-slate-500 mb-4">Couldn't load data for "{machine_id}".</p>
          <Link to="/" className="text-sm text-navy underline">Back to fleet</Link>
        </div>
      </div>
    );
  }

  const isMaintenance = machine.data?.status === 'maintenance';
  const sensorList = sensors.data || [];
  const activeSensor = sensorList.find((s) => s.sensor_type === selectedSensor);
  const anomalyCount = sensorList.filter((s) => s.is_anomaly && !isMaintenance).length;

  return (
    <div className="px-8 py-7 max-w-[1400px] flex flex-col gap-5">
      {machine.status === 'ok' ? (
        <MachineHeader machine={machine.data} />
      ) : (
        <div className="h-[120px] rounded-xl bg-slate-100 animate-pulse" />
      )}

      {components.status === 'ok' && predictions.status === 'ok' ? (
        <ComponentHealthRow
          components={components.data}
          predictions={predictions.data}
          isMaintenance={isMaintenance}
        />
      ) : (components.status === 'error' || predictions.status === 'error') ? (
        <SectionError label="component health" />
      ) : (
        <div className="h-[140px] rounded-xl bg-slate-100 animate-pulse" />
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,3fr)_minmax(320px,2fr)] gap-5">
        <div className="flex flex-col gap-5 min-w-0">
          <section className="bg-white rounded-xl shadow-card overflow-hidden">
            <header className="px-5 py-4 border-b border-slate-100 flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-navy">Live sensors</div>
                <div className="text-[11px] text-slate-500">
                  {sensors.status === 'ok'
                    ? `${sensorList.length} cells · click any to plot history`
                    : 'Loading sensors…'}
                </div>
              </div>
              {sensors.status === 'ok' && (
                <div className="text-[11px] text-slate-400 font-mono">
                  {anomalyCount} anomal{anomalyCount === 1 ? 'y' : 'ies'} detected
                </div>
              )}
            </header>
            <div className="p-4">
              {sensors.status === 'ok' ? (
                <SensorGrid
                  sensors={sensorList}
                  selected={selectedSensor}
                  onSelect={setSelectedSensor}
                  isMaintenance={isMaintenance}
                />
              ) : sensors.status === 'error' ? (
                <SectionError label="sensors" />
              ) : (
                <div className="h-[200px] rounded-lg bg-slate-100 animate-pulse" />
              )}
            </div>
          </section>

          <section className="bg-white rounded-xl shadow-card overflow-hidden">
            <header className="px-5 py-4 border-b border-slate-100 flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-navy">
                  {activeSensor ? prettySensorName(selectedSensor) : 'Sensor history'}
                </div>
                <div className="text-[11px] text-slate-500">Last 48 h · normal range shown as green band</div>
              </div>
              {activeSensor && !isMaintenance && (
                <div className="flex items-center gap-3">
                  <Stat
                   label="Current"
                   value={activeSensor.value}
                   unit={activeSensor.unit}
                   tone={
                    !activeSensor.is_anomaly
                       ? 'normal'
                       : activeSensor.value >= activeSensor.normal_range[0] &&
                        activeSensor.value <= activeSensor.normal_range[1]
                        ? 'watch'
                        : 'critical'
                    }
                 />
                  <Stat label="Normal" value={`${activeSensor.normal_range[0]}–${activeSensor.normal_range[1]}`} unit={activeSensor.unit} />
                </div>
              )}
            </header>
            <div className="p-4">
              {history.status === 'ok' ? (
                <SensorHistoryChart data={history.data} sensor={activeSensor} isMaintenance={isMaintenance} />
              ) : history.status === 'error' ? (
                <SectionError label="sensor history" />
              ) : (
                <div className="h-[260px] rounded-lg bg-slate-100 animate-pulse" />
              )}
            </div>
          </section>
        </div>

        <div className="flex flex-col gap-5 min-w-0">
          {alarms.status === 'ok' ? (
            <AlarmsTable alarms={alarms.data} />
          ) : alarms.status === 'error' ? (
            <SectionError label="alarms" />
          ) : (
            <div className="h-[300px] rounded-xl bg-slate-100 animate-pulse" />
          )}

          {maintenance.status === 'ok' ? (
            <MaintenanceLog entries={maintenance.data} />
          ) : maintenance.status === 'error' ? (
            <SectionError label="maintenance log" />
          ) : (
            <div className="h-[300px] rounded-xl bg-slate-100 animate-pulse" />
          )}
        </div>
      </div>
    </div>
  );
}

function SectionError({ label }) {
  return (
    <div className="rounded-lg bg-red-50 ring-1 ring-red-200 p-3 text-[12px] text-red-800">
      Couldn't load {label}.
    </div>
  );
}

function Stat({ label, value, unit, tone = 'normal' }) {
  // tone: 'critical' (red), 'watch' (amber), 'normal' (navy)
  const valueColor =
    tone === 'critical' ? 'text-risk-critical' : tone === 'watch' ? 'text-amber-600' : 'text-navy';
  return (
    <div className="text-right">
      <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">{label}</div>
      <div className={`font-mono text-sm font-semibold tabular-nums ${valueColor}`}>
        {value}<span className="text-slate-400 ml-1 text-[10px]">{unit}</span>
      </div>
    </div>
  );
}

function prettySensorName(t) {
  if (!t) return '';
  return t.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}