import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MessageCircle } from 'lucide-react';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import ChatPanel from './components/ChatPanel';

import LandingPage from './components/marketing/LandingPage';
import Blog from './components/marketing/Blog';
import BlogPost from './components/marketing/BlogPost';

const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('auth_token');
  if (!token) return <Navigate to="/login" />;
  return children;
};

const Layout = ({ children }) => {
  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('username');
    window.location.href = '/login';
  };

  return (
    <div className="app-container">
      <div className="background-effect"></div>
      <header className="top-nav glass-panel">
        <div className="logo">Scientific Discovery OS</div>
        <div className="user-info">
          <span>{localStorage.getItem('username')}</span>
          <button onClick={handleLogout} className="logout-btn">Logout</button>
        </div>
      </header>
      {children}
    </div>
  );
};

function App() {
  const [isChatOpen, setIsChatOpen] = useState(false);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/blog" element={<Blog />} />
        <Route path="/blog/:id" element={<BlogPost />} />
        <Route path="/login" element={
          <div className="app-container">
            <div className="background-effect"></div>
            <Login />
          </div>
        } />
        <Route path="/app" element={
          <ProtectedRoute>
            <Layout>
              <div className="dashboard-layout">
                <Dashboard />
                {isChatOpen && <ChatPanel onClose={() => setIsChatOpen(false)} />}
                <button 
                  className="chat-fab" 
                  onClick={() => setIsChatOpen(!isChatOpen)}
                  title="Toggle OS Chat"
                >
                  <MessageCircle size={28} />
                </button>
              </div>
            </Layout>
          </ProtectedRoute>
        } />
        {/* Redirect unknown routes to landing page */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
