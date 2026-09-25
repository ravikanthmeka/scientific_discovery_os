import React, { useState, useEffect } from 'react';
import { CreditCard, Zap, Shield, Loader } from 'lucide-react';

const Billing = ({ onClose }) => {
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchUsage();
  }, []);

  const fetchUsage = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_BACKEND_URL}/api/billing/usage`, {
        headers: {
          'token': localStorage.getItem('auth_token') || ''
        }
      });
      if (res.ok) {
        const data = await res.json();
        setUsage(data);
      } else {
        setError("Failed to load usage data.");
      }
    } catch (err) {
      setError("Network error fetching usage.");
    } finally {
      setLoading(false);
    }
  };

  const handleUpgrade = async () => {
    setCheckoutLoading(true);
    try {
      const res = await fetch(`${import.meta.env.VITE_BACKEND_URL}/api/billing/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: localStorage.getItem('auth_token') || '',
          success_url: window.location.href,
          cancel_url: window.location.href
        })
      });
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        setError(data.detail || "Failed to initiate checkout");
        setCheckoutLoading(false);
      }
    } catch (err) {
      setError("Error connecting to billing service.");
      setCheckoutLoading(false);
    }
  };

  return (
    <div className="billing-modal-overlay" style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.8)', zIndex: 1000,
      display: 'flex', alignItems: 'center', justifyContent: 'center'
    }}>
      <div className="billing-modal floating" style={{
        width: '400px', background: 'var(--bg-color)', padding: '2rem',
        borderRadius: '12px', border: '1px solid var(--border-color)',
        color: '#fff'
      }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <CreditCard color="var(--accent-blue)" /> Billing & Usage
        </h2>
        <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#fff', fontSize: '1.5rem', cursor: 'pointer' }}>&times;</button>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '2rem' }}><Loader className="spin" /></div>
      ) : usage ? (
        <div>
          <div style={{ background: 'rgba(255,255,255,0.05)', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem' }}>
            <h3 style={{ margin: '0 0 0.5rem 0', color: 'var(--text-secondary)' }}>Current Plan</h3>
            <div style={{ fontSize: '1.5rem', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              {usage.tier === 'PRO' ? <><Zap color="var(--accent-purple)" /> PRO</> : <><Shield color="var(--text-secondary)" /> FREE</>}
            </div>
          </div>

          <div style={{ marginBottom: '2rem' }}>
            <h3 style={{ margin: '0 0 0.5rem 0', color: 'var(--text-secondary)' }}>Token Usage</h3>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span>{usage.tokens_used.toLocaleString()}</span>
              <span>{usage.limit === 'Unlimited' ? '∞' : Number(usage.limit).toLocaleString()}</span>
            </div>
            {usage.tier === 'FREE' && (
              <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ 
                  height: '100%', 
                  width: `${Math.min((usage.tokens_used / usage.limit) * 100, 100)}%`,
                  background: usage.tokens_used >= usage.limit ? 'var(--accent-red)' : 'var(--accent-blue)'
                }} />
              </div>
            )}
          </div>

          {usage.tier === 'FREE' && (
            <button 
              onClick={handleUpgrade}
              disabled={checkoutLoading}
              style={{
                width: '100%', padding: '1rem', background: 'var(--accent-purple)', 
                color: '#fff', border: 'none', borderRadius: '8px', fontWeight: 'bold',
                cursor: checkoutLoading ? 'not-allowed' : 'pointer', fontSize: '1.1rem'
              }}
            >
              {checkoutLoading ? 'Processing...' : 'Upgrade to PRO'}
            </button>
          )}

          {error && <div style={{ color: 'var(--accent-red)', marginTop: '1rem', textAlign: 'center' }}>{error}</div>}
        </div>
      ) : (
        <div style={{ color: 'var(--accent-red)' }}>{error}</div>
      )}
      </div>
    </div>
  );
};

export default Billing;
