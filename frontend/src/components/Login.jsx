import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const Login = () => {
  const [isLoginMode, setIsLoginMode] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [dob, setDob] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    
    const endpoint = isLoginMode ? '/login' : '/register';
    
    try {
      const bodyData = isLoginMode 
        ? { email, password } 
        : { email, password, name, dob: dob || null };

      const response = await fetch(`${import.meta.env.VITE_BACKEND_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(bodyData)
      });
      
      const data = await response.json();
      
      if (response.ok) {
        if (isLoginMode) {
          localStorage.setItem('auth_token', data.token);
          localStorage.setItem('email', email);
          navigate('/app');
        } else {
          setMessage('Account created successfully! You can now log in.');
          setIsLoginMode(true);
          setPassword('');
        }
      } else {
        setError(data.detail || (isLoginMode ? 'Invalid credentials' : 'Registration failed'));
      }
    } catch (err) {
      console.error(`Backend auth failed on ${endpoint}:`, err);
      setError('Cannot connect to the server. Please try again later.');
    }
  };

  return (
    <div className="login-container">
      <div className="login-card glass-panel">
        <h2>{isLoginMode ? 'Scientific Discovery OS' : 'Create Account'}</h2>
        <p style={{color: 'var(--text-secondary)'}}>
          {isLoginMode ? 'Login to access the research portal' : 'Join the Scientific Discovery OS'}
        </p>
        
        {message && <p style={{color: 'var(--accent-green)', fontSize: '0.9rem', marginTop: '1rem'}}>{message}</p>}
        
        <form onSubmit={handleSubmit}>
          {!isLoginMode && (
            <>
              <input 
                type="text" 
                placeholder="Full Name" 
                value={name}
                required
                onChange={(e) => setName(e.target.value)}
              />
              <input 
                type="date" 
                placeholder="Date of Birth (Optional)" 
                value={dob}
                onChange={(e) => setDob(e.target.value)}
              />
            </>
          )}
          <input 
            type="email" 
            placeholder="Email Address" 
            value={email}
            required
            onChange={(e) => setEmail(e.target.value)}
          />
          <input 
            type="password" 
            placeholder="Password" 
            value={password}
            required
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && <p style={{color: '#ef4444', fontSize: '0.9rem'}}>{error}</p>}
          <button type="submit" className="glow-btn">
            {isLoginMode ? 'Access System' : 'Sign Up'}
          </button>
        </form>
        
        <div style={{marginTop: '1.5rem', fontSize: '0.9rem', color: 'var(--text-secondary)'}}>
          {isLoginMode ? "Don't have an account? " : "Already have an account? "}
          <span 
            style={{color: 'var(--accent-blue)', cursor: 'pointer', textDecoration: 'underline'}}
            onClick={() => {
              setIsLoginMode(!isLoginMode);
              setError('');
              setMessage('');
            }}
          >
            {isLoginMode ? 'Create one' : 'Log in'}
          </span>
        </div>
      </div>
    </div>
  );
};

export default Login;
