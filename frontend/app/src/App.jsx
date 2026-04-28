import { Routes, Route } from 'react-router-dom';
import AppShell from './layout/AppShell.jsx';
import Overview from './routes/Overview.jsx';
import MachinesIndex from './routes/MachinesIndex.jsx';
import MachineDetail from './routes/MachineDetail.jsx';
import Alerts from './routes/Alerts.jsx';
import DemandForecast from './routes/DemandForecast.jsx';
import ROI from './routes/ROI.jsx';
import NotFound from './routes/NotFound.jsx';

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Overview />} />
        <Route path="machines" element={<MachinesIndex />} />
        <Route path="machines/:machine_id" element={<MachineDetail />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="demand" element={<DemandForecast />} />
        <Route path="roi" element={<ROI />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
