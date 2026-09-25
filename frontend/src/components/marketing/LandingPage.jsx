import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, Search, Zap, ArrowRight, Activity, Beaker } from 'lucide-react';
import scienceHero from '../../assets/science_hero.jpg';
import neuroscienceHero from '../../assets/neuroscience_hero.jpg';
import chemistryHero from '../../assets/chemistry_hero.jpg';
import mathHero from '../../assets/math_hero.jpg';
import physicsHero from '../../assets/physics_hero.jpg';
import energyHero from '../../assets/energy_hero.jpg';
import quantumHero from '../../assets/quantum_hero.jpg';

const images = [scienceHero, neuroscienceHero, chemistryHero, mathHero, physicsHero, energyHero, quantumHero];

const LandingPage = () => {
  const [currentImageIndex, setCurrentImageIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentImageIndex((prevIndex) => (prevIndex + 1) % images.length);
    }, 5000);
    return () => clearInterval(interval);
  }, []);
  return (
    <div className="landing-page">
      {/* Navigation */}
      <nav className="landing-nav">
        <div className="landing-logo">
          <Beaker size={24} color="#2563eb" />
          <span>SynaptoLab</span>
        </div>
        <div className="nav-links">
          <Link to="/blog">Blog</Link>
          <Link to="/login" className="login-link">Sign In</Link>
          <Link to="/login" className="btn-primary">Get Started</Link>
        </div>
      </nav>

      {/* Hero Section */}
      <header className="hero-section">
        <div className="hero-content">
          <div className="badge">Scientific Discovery OS</div>
          <h1>Accelerate Your Scientific Research with AI.</h1>
          <p>
            Designed for PhDs, grad students, and independent researchers. 
            Synthesize hundreds of papers from PubMed and OpenAlex in minutes, 
            not months. Build hypotheses backed by verifiable data.
          </p>
          <div className="hero-actions">
            <Link to="/login" className="btn-primary large">
              Start Free Trial <ArrowRight size={20} />
            </Link>
            <Link to="/blog" className="btn-secondary large">
              Read our Research
            </Link>
          </div>
        </div>
        <div className="hero-visual" style={{ position: 'relative', overflow: 'hidden', borderRadius: '1rem', border: '1px solid #e2e8f0', minHeight: '500px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {images.map((img, index) => (
            <img
              key={index}
              src={img}
              alt={`AI accelerating scientific research - ${index + 1}`}
              style={{
                width: '100%',
                maxWidth: '500px',
                position: 'absolute',
                top: 0,
                left: 0,
                opacity: index === currentImageIndex ? 1 : 0,
                transition: 'opacity 1s ease-in-out',
                display: 'block',
                margin: '0 auto'
              }}
            />
          ))}
        </div>
      </header>

      {/* Features Section */}
      <section className="features-section">
        <div className="section-header">
          <h2>Clinical Precision. Infinite Scale.</h2>
          <p>Stop drowning in PDFs. SynaptoLab extracts the exact methodologies, results, and hypotheses you need.</p>
        </div>
        
        <div className="feature-grid">
          <div className="feature-card">
            <div className="feature-icon"><Search size={32} /></div>
            <h3>Deep Academic Search</h3>
            <p>Direct integration with PubMed and OpenAlex databases. Query millions of open-access papers instantly.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon"><Zap size={32} /></div>
            <h3>Automated Synthesis</h3>
            <p>Our agentic AI reads the full text of relevant papers, cross-references claims, and generates systematic reviews.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon"><Activity size={32} /></div>
            <h3>Hypothesis Generation</h3>
            <p>Identify gaps in current literature and map out novel research pathways based on empirical data.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon"><BookOpen size={32} /></div>
            <h3>Transparent Citations</h3>
            <p>Every claim made by the AI is strictly mapped to a source DOI. No hallucinations, just hard science.</p>
          </div>
        </div>
      </section>

      {/* Social Proof / Target Audience */}
      <section className="audience-section">
        <div className="audience-content">
          <h2>Built for Modern Science</h2>
          <ul className="checklist">
            <li><strong>Grad Students & PhDs:</strong> Finish your thesis background research in record time.</li>
            <li><strong>Independent Researchers:</strong> Access powerful tools without institutional lab funding.</li>
            <li><strong>Science Enthusiasts:</strong> Explore deep biomedical literature with an AI guide.</li>
          </ul>
        </div>
      </section>

      {/* CTA Footer */}
      <footer className="landing-footer">
        <h2>Ready to advance your research?</h2>
        <p>Join researchers worldwide using SynaptoLab to uncover new scientific paradigms.</p>
        <Link to="/login" className="btn-primary large">Create Your Account</Link>
        
        <div className="footer-links">
          <Link to="/">Home</Link>
          <Link to="/blog">Blog</Link>
          <a href="#">Terms</a>
          <a href="#">Privacy</a>
        </div>
        <p className="copyright">© {new Date().getFullYear()} SynaptoLab. All rights reserved.</p>
      </footer>
    </div>
  );
};

export default LandingPage;
