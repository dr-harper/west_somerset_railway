import { BrowserRouter as Router, Navigate, Routes, Route } from 'react-router-dom';
import './styles/global.css';
import './App.css';
import { Header } from './components/Layout/Header';
import { Footer } from './components/Layout/Footer';
import { Home } from './pages/Home/Home';
import { LiveTrains } from './pages/LiveTrains/LiveTrains';
import { JourneyPlanner } from './pages/JourneyPlanner/JourneyPlanner';
import { VerifyPage } from './pages/Verify/VerifyPage';
import { AdminLayout } from './pages/Admin/AdminLayout';
import { AdminOverview } from './pages/Admin/AdminOverview';
import { AdminEvents } from './pages/Admin/AdminEvents';
import { AdminTrains } from './pages/Admin/AdminTrains';
import { AdminCameras } from './pages/Admin/AdminCameras';
import { AdminSettings } from './pages/Admin/AdminSettings';

function App() {
  // Get the base path from Vite's configuration
  const basename = import.meta.env.BASE_URL;
  
  return (
    <Router basename={basename}>
      <div className="app">
        <Header />
        
        <main className="main">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/live-trains" element={<LiveTrains />} />
            <Route path="/journey-planner" element={<JourneyPlanner />} />
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<AdminOverview />} />
              <Route path="verify" element={<VerifyPage />} />
              <Route path="events" element={<AdminEvents />} />
              <Route path="trains" element={<AdminTrains />} />
              <Route path="episodes" element={<Navigate to="/admin/events" replace />} />
              <Route path="cameras" element={<AdminCameras />} />
              <Route path="settings" element={<AdminSettings />} />
            </Route>
            {/* the verify page moved under /admin; keep old links working */}
            <Route path="/verify" element={<Navigate to="/admin/verify" replace />} />
          </Routes>
        </main>

        <Footer />
      </div>
    </Router>
  );
}

export default App;