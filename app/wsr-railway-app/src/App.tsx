import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import './styles/global.css';
import './App.css';
import { Header } from './components/Layout/Header';
import { Footer } from './components/Layout/Footer';
import { Home } from './pages/Home/Home';
import { LiveTrains } from './pages/LiveTrains/LiveTrains';

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
          </Routes>
        </main>

        <Footer />
      </div>
    </Router>
  );
}

export default App;