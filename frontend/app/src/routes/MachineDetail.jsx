import { useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getMachineById, componentsByMachine, predictionsByMachine, sensorsByMachine,
  alarmsByMachine, maintenanceLogByMachine, getSensorHistory, getDefaultSensorType,
} from '../mockData.js';
import MachineHeader from '../components/MachineHeader.jsx';
import ComponentHealthRow from '../components/ComponentHealthRow.jsx';
import SensorGrid from '../components/SensorGrid.jsx';
import SensorHistoryChart from '../components/SensorHistoryChart.jsx';
import AlarmsTable from '../components/AlarmsTable.jsx';
import MaintenanceLog from '../components/MaintenanceLog.jsx';

export default function MachineDetail() {
  const { machine_id } = useParams();
  const machine = getMachineById(machine_id);

  const initialSensor = useMemo(
    () => (machine ? getDefaultSensorType(machine.machine_id) : null),
    [machine]
  );
  const [selectedSensor, setSelectedSensor] = useState(initialSensor);

  if (!machine) {
    return (
      <div className="px-8 py-7 max-w-[1200px]">
        <div className="bg-white rounded-xl shadow-card p-8 text-center">
          <h1 className="text-lg font-semibold text-navy mb-1">Machine not found</h1>
          <p className="text-sm text-slate-500 mb-4">No machine matches “{machine_id}”.</p>
          <Link to="/" className="text-sm text-navy underline">Back to fleet</Link>
        </div>
      </div>
    );
  }

  const isMaintenance = machine.status === 'maintenance';
  const components  = componentsByMachine[machine.machine_id]  || [];
  const predictions = predictionsByMachine[machine.machine_id] || [];
  const sensors     = sensorsByMachine[machine.machine_id]     || [];
  const alarms      = alarmsByMachine[machine.machine_id]      || [];
  const maintenance = maintenanceLogByMachine[machine.machine_id] || [];

  const activeSensorType = selectedSensor || initialSensor;
  const activeSensor = sensors.find((s) => s.sensor_type === activeSensorType);
  const history = getSensorHistory(machine.machine_id, activeSensorType);

  const anomalyCount = sensors.filter((s) => s.is_anomaly && !isMaintenance).length;

  return (
    <div className="px-8 py-7 max-w-[1400px] flex flex-col gap-5">
      <MachineHeader machine={machine} />
      <ComponentHealthRow components={components} predictions={predictions} isMaintenance={isMaintenance} />

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,3fr)_minmax(320px,2fr)] gap-5">
        <div className="flex flex-col gap-5 min-w-0">
          <section className="bg-white rounded-xl shadow-card overflow-hidden">
            <header className="px-5 py-4 border-b border-slate-100 flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-navy">Live sensors</div>
                <div className="text-[11px] text-slate-500">{sensors.length} cells · click any to plot history</div>
              </div>
              <div className="text-[11px] text-slate-400 font-mono">
                {anomalyCount} anomal{anomalyCount === 1 ? 'y' : 'ies'} detected
              </div>
            </header>
            <div className="p-4">
              <SensorGrid sensors={sensors} selected={activeSensorType} onSelect={setSelectedSensor} isMaintenance={isMaintenance} />
            </div>
          </section>

          <section className="bg-white rounded-xl shadow-card overflow-hidden">
            <header className="px-5 py-4 border-b border-slate-100 flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-navy">{activeSensor ? prettySensorName(activeSensorType) : 'Sensor history'}</div>
                <div className="text-[11px] text-slate-500">Last 48 h · normal range shown as green band</div>
              </div>
              {activeSensor && !isMaintenance && (
                <div className="flex items-center gap-3">
                  <Stat label="Current" value={activeSensor.value} unit={activeSensor.unit} highlight={activeSensor.is_anomaly} />
                  <Stat label="Normal" value={`${activeSensor.normal_range[0]}–${activeSensor.normal_range[1]}`} unit={activeSensor.unit} />
                </div>
              )}
            </header>
            <div className="p-4">
              <SensorHistoryChart data={history} sensor={activeSensor} isMaintenance={isMaintenance} />
            </div>
          </section>
        </div>

        <div className="flex flex-col gap-5 min-w-0">
          <AlarmsTable alarms={alarms} />
          <MaintenanceLog entries={maintenance} />
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, unit, highlight }) {
  return (
    <div className="text-right">
      <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">{label}</div>
      <div className={`font-mono text-sm font-semibold tabular-nums ${highlight ? 'text-risk-critical' : 'text-navy'}`}>
        {value}<span className="text-slate-400 ml-1 text-[10px]">{unit}</span>
      </div>
    </div>
  );
}

function prettySensorName(t) {
  if (!t) return '';
  return t.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}