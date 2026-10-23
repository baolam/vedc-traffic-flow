import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import NetworkOverview from './pages/NetworkOverview';
import IntersectionDetail from './pages/IntersectionDetail';
import ControlPanel from './pages/ControlPanel';
import BenchmarkSummary from './pages/BenchmarkSummary';
import HcmCameraMap from './pages/HcmCameraMap';
import './App.css';

function App() {
  return (
    <BrowserRouter>
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
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;
