import React, { useState } from 'react';

const SimulationCanvas = ({ artifactContent }) => {
  const [output, setOutput] = useState(null);
  const [image, setImage] = useState(null);
  const [isRunning, setIsRunning] = useState(false);

  // Extract python code
  const codeMatch = artifactContent.match(/```python([\s\S]*?)```/);
  const code = codeMatch ? codeMatch[1].trim() : "print('No executable Python code found in artifact.')";

  const runSimulation = async () => {
    setIsRunning(true);
    try {
      const response = await fetch(`${import.meta.env.VITE_BACKEND_URL}/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code })
      });
      const data = await response.json();
      setOutput(data.output);
      setImage(data.image);
    } catch (e) {
      setOutput("Failed to run simulation: " + e.message);
    }
    setIsRunning(false);
  };

  return (
    <div className="simulation-canvas glass-panel" style={{ marginTop: '1rem', borderTop: '2px solid var(--accent-green)' }}>
      <h3 style={{ color: 'var(--accent-green)' }}>Simulation Sandbox</h3>
      <div style={{ background: '#1e1e1e', padding: '1rem', borderRadius: '4px', overflowX: 'auto', marginBottom: '1rem', fontSize: '0.9rem', color: '#d4d4d4', fontFamily: 'monospace' }}>
        <pre style={{ margin: 0 }}>{code}</pre>
      </div>

      <button className="glow-btn" onClick={runSimulation} disabled={isRunning} style={{ background: 'var(--accent-green)' }}>
        {isRunning ? 'Running PyTorch Simulation...' : 'Run Simulation'}
      </button>

      {output && (
        <div style={{ marginTop: '1rem', background: 'rgba(0,0,0,0.5)', padding: '1rem', borderRadius: '4px' }}>
          <h4>Standard Output / Errors:</h4>
          <pre style={{ color: '#e2e8f0', whiteSpace: 'pre-wrap', fontSize: '0.85rem' }}>{output}</pre>
        </div>
      )}

      {image && (
        <div style={{ marginTop: '1rem', textAlign: 'center' }}>
          <h4>Generated Plot:</h4>
          <img src={`data:image/png;base64,${image}`} alt="Simulation Output Plot" style={{ maxWidth: '100%', borderRadius: '4px', border: '1px solid var(--border-color)' }} />
        </div>
      )}
    </div>
  );
};

export default SimulationCanvas;
