import React from 'react';

const HypothesisCard = ({ hypothesis, onSelect }) => {
  return (
    <div className="hypothesis-card glass-panel" style={{ marginBottom: '1rem', padding: '1.5rem', borderLeft: '4px solid var(--accent-color)', background: 'rgba(0,0,0,0.4)' }}>
      <h3 style={{ marginTop: 0, color: 'var(--accent-color)' }}>{hypothesis.title}</h3>
      
      <div style={{ marginBottom: '1rem' }}>
        <strong style={{ color: 'var(--text-muted)' }}>Cross-Domain Inspiration:</strong> 
        <span className="tag" style={{ marginLeft: '0.5rem', background: 'var(--bg-card)' }}>
          {hypothesis.cross_domain_inspiration}
        </span>
      </div>
      
      <div style={{ marginBottom: '1rem' }}>
        <strong style={{ color: 'var(--text-muted)' }}>Theoretical Basis:</strong>
        <p style={{ margin: '0.5rem 0', fontSize: '0.95rem', lineHeight: '1.5', color: '#e2e8f0' }}>
          {hypothesis.theoretical_basis}
        </p>
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <strong style={{ color: 'var(--text-muted)' }}>Proposed Simulation:</strong>
        <p style={{ margin: '0.5rem 0', fontSize: '0.95rem', lineHeight: '1.5', color: '#cbd5e1' }}>
          {hypothesis.proposed_simulation}
        </p>
      </div>

      <button className="glow-btn" onClick={() => onSelect(hypothesis)} style={{ width: '100%', display: 'block', textAlign: 'center', background: 'var(--accent-color)' }}>
        Pursue this Line of Research
      </button>
    </div>
  );
};

export default HypothesisCard;
