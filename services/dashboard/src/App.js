import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import SafeStopOverlay from './components/SafeStopOverlay';
import HardwareFaultOverlay from './components/HardwareFaultOverlay';
import NetworkOverview from './pages/NetworkOverview';
import IntersectionDetail from './pages/IntersectionDetail';
import ControlPanel from './pages/ControlPanel';
import BenchmarkSummary from './pages/BenchmarkSummary';
import HcmCameraMap from './pages/HcmCameraMap';
import RaspberryPiDemo from './pages/RaspberryPiDemo';
import RlBenchmarkReport from './pages/RlBenchmarkReport';
import Stations from './pages/Stations';
import AdminConsole from './pages/admin/AdminConsole';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <SafeStopOverlay />
      <HardwareFaultOverlay />
      <div className="app-container">
        <Sidebar />
        <div className="main-content">
          <Header />
          <Routes>
            <Route path="/" element={<NetworkOverview />} />
            <Route path="/intersections/:nodeId" element={<IntersectionDetail />} />
            <Route path="/benchmark" element={<BenchmarkSummary />} />
            <Route path="/experiments" element={<ControlPanel />} />
            <Route path="/cameras" element={<HcmCameraMap />} />
            <Route path="/raspberry-pi-demo" element={<RaspberryPiDemo />} />
            <Route path="/rl-benchmark" element={<RlBenchmarkReport />} />
            <Route path="/stations" element={<Stations />} />
            <Route path="/admin" element={<AdminConsole />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;
