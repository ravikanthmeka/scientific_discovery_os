import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import HypothesisCard from './HypothesisCard';
import SimulationCanvas from './SimulationCanvas';
import Billing from './Billing';

const Dashboard = () => {
  const [domain, setDomain] = useState('Nuclear');
  const [customDomain, setCustomDomain] = useState('');
  const [query, setQuery] = useState('Design a safer fusion reactor containment field');
  const [artifacts, setArtifacts] = useState([]);
  const [agents, setAgents] = useState({
    literature: { status: 'Idle', log: 'Waiting for mission...', active: false, completed: false, label: 'Literature Intelligence', icon: '📚', tokens: null },
    cross_domain: { status: 'Idle', log: 'Waiting for literature...', active: false, completed: false, label: 'Cross-Domain Innovator', icon: '🌐', tokens: null },
    structured_reasoner: { status: 'Idle', log: 'Waiting for query...', active: false, completed: false, label: 'Structured Reasoner', icon: '🕵️', tokens: null },
    domain_expert: { status: 'Idle', log: 'Waiting for data...', active: false, completed: false, label: 'Domain Expert', icon: '🧠', tokens: null },
    simulation: { status: 'Idle', log: 'Waiting for models...', active: false, completed: false, label: 'Simulation Orchestrator', icon: '💻', tokens: null },
    hypothesis: { status: 'Idle', log: 'Waiting for results...', active: false, completed: false, label: 'Hypothesis Generator', icon: '💡', tokens: null },
    experiment: { status: 'Idle', log: 'Waiting for hypothesis...', active: false, completed: false, label: 'Experiment Planner', icon: '🔬', tokens: null },
    validation: { status: 'Idle', log: 'Waiting for plans...', active: false, completed: false, label: 'Result Validator', icon: '✅', tokens: null }
  });
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [socket, setSocket] = useState(null);
  const [pipelineState, setPipelineState] = useState('idle'); // idle, running, paused
  const [refinementText, setRefinementText] = useState('');
  
  const [showHistory, setShowHistory] = useState(false);
  const [queryHistory, setQueryHistory] = useState([]);
  
  const [showStats, setShowStats] = useState(false);
  const [stats, setStats] = useState([]);
  
  const [showPapers, setShowPapers] = useState(false);
  const [papers, setPapers] = useState({});
  const [showBilling, setShowBilling] = useState(false);

  const domains = ['Nuclear', 'Quantum', 'Materials', 'Biology', 'Climate', 'Mathematics', 'Healthcare', 'Energy', 'Other'];
  const navigate = useNavigate();

  const userEmail = localStorage.getItem('email') || '';
  const isAdmin = userEmail.endsWith('@synaptolab.com') || userEmail === 'admin@admin.com';

  const handleDomainChange = (newDomain) => {
    setDomain(newDomain);
    const queries = {
      'Nuclear': 'Design a safer fusion reactor containment field',
      'Quantum': 'Discover a new quantum error correction code',
      'Materials': 'Discover room-temperature superconductors',
      'Biology': 'Synthesize a protein to bind with microplastics',
      'Climate': 'Model optimal carbon capture array placement',
      'Mathematics': 'Find novel patterns in prime distribution',
      'Healthcare': 'Personalized mRNA vaccine sequence generation',
      'Energy': 'Optimize solid-state battery electrolyte',
      'Other': 'Explore novel cross-domain discovery patterns'
    };
    setQuery(queries[newDomain]);
  };

  const fetchHistory = async () => {
    const token = localStorage.getItem('auth_token');
    if (!token) return;
    try {
      const res = await fetch(`${import.meta.env.VITE_BACKEND_URL}/history?token=${token}`);
      if (res.ok) {
        const data = await res.json();
        setQueryHistory(data);
      } else if (res.status === 401) {
        // Token invalid or expired
        navigate('/login');
      }
    } catch (err) {
      console.error("Failed to fetch history", err);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_BACKEND_URL}/stats/ingestion`);
      if (res.ok) {
        const data = await res.json();
        setStats(data.stats || []);
      }
    } catch (err) {
      console.error("Failed to fetch stats", err);
    }
  };

  const fetchPapers = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_BACKEND_URL}/stats/papers`);
      if (res.ok) {
        const data = await res.json();
        setPapers(data.papers || {});
      }
    } catch (err) {
      console.error("Failed to fetch papers", err);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('email');
    navigate('/login');
  };

  const startDiscovery = () => {
    setIsDiscovering(true);
    setArtifacts([]);
    // Reset agent state
    setAgents(prev => {
      let reset = { ...prev };
      for (let key in reset) {
        reset[key] = { ...reset[key], status: 'Idle', log: 'Waiting...', active: false, completed: false };
      }
      return reset;
    });
    setPipelineState('running');

    const ws = new WebSocket(`${import.meta.env.VITE_BACKEND_URL.replace("http", "ws")}/ws/discovery`);
    
    ws.onopen = () => {
      ws.send(JSON.stringify({ 
        domain: domain === 'Other' && customDomain.trim() ? customDomain : domain, 
        query,
        token: localStorage.getItem('auth_token')
      }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const { agent_id, status, log, artifact, agent_name, tokens } = data;

      if (agent_id === "SYSTEM") {
        if (status === "Completed" || status === "Error") {
          setIsDiscovering(false);
          setPipelineState('idle');
          setArtifacts(prev => [...prev, { name: status === "Error" ? "SYSTEM ERROR" : "SYSTEM", content: log }]);
          ws.close();
        }
        return;
      }

      if (agents[agent_id]) {
        setAgents(prev => {
          let updated = { ...prev };
          if (status === "Processing") {
            updated[agent_id].active = true;
            updated[agent_id].completed = false;
            updated[agent_id].status = "Processing";
            updated[agent_id].log = log;
            if (agent_name) updated[agent_id].label = agent_name;
            if (tokens) updated[agent_id].tokens = tokens;
          } else if (status === "Paused") {
            updated[agent_id].active = true;
            updated[agent_id].status = "Waiting for User";
            updated[agent_id].log = log;
            setPipelineState('paused');
          } else if (status === "Completed") {
            updated[agent_id].active = false;
            updated[agent_id].completed = true;
            updated[agent_id].status = "Completed";
            updated[agent_id].log = log;
            if (tokens) updated[agent_id].tokens = tokens;
          }
          return updated;
        });

        if (status === "Completed" && artifact) {
          const nameToUse = agent_name || agents[agent_id].label;
          setArtifacts(prev => [...prev, { name: nameToUse, content: artifact }]);
        }
      }
    };

    ws.onerror = () => {
      setIsDiscovering(false);
      setArtifacts(prev => [...prev, { name: "SYSTEM ERROR", content: "WebSocket connection failed." }]);
    };

    setSocket(ws);
  };

  const sendRefinement = () => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ action: "refine", feedback: refinementText }));
      setPipelineState('running');
      setRefinementText('');
    }
  };

  const goBackToHypotheses = () => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ action: "go_back" }));
      setPipelineState('running');
      setRefinementText('');
    }
  };

  const proceedToNext = () => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ action: "proceed" }));
      setPipelineState('running');
    }
  };

  useEffect(() => {
    return () => {
      if (socket) socket.close();
    };
  }, [socket]);

  return (
    <div className="main-content">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>Initialize Discovery Mission</h2>
        <div>
          <span style={{ marginRight: '1rem', color: 'var(--text-secondary)' }}>
            User: {localStorage.getItem('email') || 'Guest'} {isAdmin && '(Admin)'}
          </span>

          {isAdmin && (
            <button className="glow-btn" style={{ marginRight: '0.5rem', background: 'var(--accent-color)' }} onClick={() => {
              setShowStats(true);
              fetchStats();
            }}>
              Database Stats
            </button>
          )}

          <button className="glow-btn" style={{ marginRight: '0.5rem', background: 'var(--bg-card)' }} onClick={() => setShowBilling(true)}>
            Billing & Usage
          </button>
          <button className="glow-btn" style={{ marginRight: '0.5rem', background: 'var(--bg-card)' }} onClick={() => {
            setShowHistory(true);
            fetchHistory();
          }}>
            Query History
          </button>
          <button className="glow-btn" style={{ background: '#ef4444' }} onClick={handleLogout}>
            Logout
          </button>
        </div>
      </div>

      {showBilling && <Billing onClose={() => setShowBilling(false)} />}

      {showHistory && (
        <div className="history-modal" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.8)', zIndex: 1000, display: 'flex',
          justifyContent: 'center', alignItems: 'center'
        }}>
          <div className="glass-panel" style={{ width: '80%', maxWidth: '800px', maxHeight: '80vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <h3>My Query History</h3>
              <button onClick={() => setShowHistory(false)} style={{ background: 'transparent', border: 'none', color: '#fff', fontSize: '1.5rem', cursor: 'pointer' }}>&times;</button>
            </div>
            {queryHistory.length === 0 ? <p>No history found.</p> : (
              <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <th style={{ padding: '0.5rem' }}>Date</th>
                    <th style={{ padding: '0.5rem' }}>Domain</th>
                    <th style={{ padding: '0.5rem' }}>Query</th>
                    <th style={{ padding: '0.5rem' }}>Status</th>
                    <th style={{ padding: '0.5rem' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {queryHistory.map(h => (
                    <tr key={h.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                      <td style={{ padding: '0.5rem', fontSize: '0.85rem' }}>{new Date(h.created_at).toLocaleString()}</td>
                      <td style={{ padding: '0.5rem' }}>{h.domain}</td>
                      <td style={{ padding: '0.5rem', fontStyle: 'italic' }}>{h.query}</td>
                      <td style={{ padding: '0.5rem', color: h.status === 'Completed' ? 'var(--accent-green)' : 'var(--text-secondary)' }}>{h.status}</td>
                      <td style={{ padding: '0.5rem' }}>
                        <button 
                          className="glow-btn" 
                          style={{ fontSize: '0.8rem', padding: '0.3rem 0.6rem', background: 'var(--accent-blue)' }}
                          onClick={async () => {
                            try {
                              const token = localStorage.getItem('auth_token');
                              const res = await fetch(`${import.meta.env.VITE_BACKEND_URL}/history/${h.id}/artifacts?token=${token}`);
                              if (res.ok) {
                                const data = await res.json();
                                setArtifacts(data.artifacts.map(a => ({
                                  name: a.agent_name,
                                  content: a.content
                                })));
                                setDomain(h.domain);
                                setQuery(h.query);
                                setPipelineState('completed');
                                setShowHistory(false);
                              } else {
                                alert("Failed to load artifacts for this query.");
                              }
                            } catch(e) {
                              console.error(e);
                            }
                          }}
                        >
                          Load
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {showStats && (
        <div className="stats-modal" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.8)', zIndex: 1000, display: 'flex',
          justifyContent: 'center', alignItems: 'center'
        }}>
          <div className="glass-panel" style={{ width: '80%', maxWidth: '600px', maxHeight: '80vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <h3>Ingested Papers by Field</h3>
              <button onClick={() => setShowStats(false)} style={{ background: 'transparent', border: 'none', color: '#fff', fontSize: '1.5rem', cursor: 'pointer' }}>&times;</button>
            </div>
            <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', marginBottom: '1rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <th style={{ padding: '0.5rem' }}>Field / Category</th>
                  <th style={{ padding: '0.5rem' }}>Papers Ingested</th>
                </tr>
              </thead>
              <tbody>
                {stats.length === 0 ? (
                  <tr><td colSpan="2" style={{ padding: '0.5rem' }}>No data available.</td></tr>
                ) : (
                  stats.map((s, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                      <td style={{ padding: '0.5rem' }}>{s.category}</td>
                      <td style={{ padding: '0.5rem' }}>{s.count}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            <button 
              className="glow-btn" 
              onClick={() => {
                setShowStats(false);
                setShowPapers(true);
                fetchPapers();
              }}
            >
              View all papers grouped by field
            </button>
          </div>
        </div>
      )}

      {showPapers && (
        <div className="papers-modal" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.8)', zIndex: 1000, display: 'flex',
          justifyContent: 'center', alignItems: 'center'
        }}>
          <div className="glass-panel" style={{ width: '90%', maxWidth: '1000px', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem', position: 'sticky', top: 0, background: 'var(--bg-card)', padding: '10px 0', zIndex: 10 }}>
              <h3>All Ingested Papers</h3>
              <button onClick={() => setShowPapers(false)} style={{ background: 'transparent', border: 'none', color: '#fff', fontSize: '1.5rem', cursor: 'pointer' }}>&times;</button>
            </div>
            {Object.keys(papers).length === 0 ? <p>No papers found.</p> : (
              Object.keys(papers).map((cat) => (
                <div key={cat} style={{ marginBottom: '2rem' }}>
                  <h4 style={{ color: 'var(--accent-blue)', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>{cat} ({papers[cat].length} papers)</h4>
                  <ul style={{ listStyleType: 'none', padding: 0 }}>
                    {papers[cat].map((p) => (
                      <li key={p.id} style={{ padding: '0.5rem', background: 'rgba(255,255,255,0.05)', margin: '0.5rem 0', borderRadius: '4px' }}>
                        <div style={{ fontWeight: 'bold' }}>{p.title}</div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{p.authors}</div>
                      </li>
                    ))}
                  </ul>
                </div>
              ))
            )}
            <button 
              className="glow-btn" 
              style={{ marginTop: '1rem', background: 'var(--bg-card)' }}
              onClick={() => {
                setShowPapers(false);
                setShowStats(true);
              }}
            >
              Back to Stats
            </button>
          </div>
        </div>
      )}

      <section className="control-panel glass-panel">
        <div className="domain-selector">
          <label>Select Domain:</label>
          <div className="domain-tags">
            {domains.map(d => (
              <span 
                key={d} 
                className={`tag ${domain === d ? 'active' : ''}`}
                onClick={() => handleDomainChange(d)}
              >
                {d}
              </span>
            ))}
          </div>
          {domain === 'Other' && (
            <div className="custom-domain-input" style={{ marginTop: '1rem' }}>
              <input 
                type="text" 
                placeholder="Enter custom domain name" 
                value={customDomain}
                onChange={(e) => setCustomDomain(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !isDiscovering && customDomain.trim()) {
                    startDiscovery();
                  }
                }}
                disabled={isDiscovering}
                style={{ 
                  background: 'rgba(0, 0, 0, 0.2)', 
                  border: '1px solid var(--border-color)', 
                  color: 'white', 
                  padding: '0.75rem 1rem', 
                  borderRadius: '8px', 
                  fontFamily: 'Outfit, sans-serif',
                  width: '100%',
                  maxWidth: '300px'
                }}
              />
            </div>
          )}
        </div>
        <div className="query-input">
          <input 
            type="text" 
            placeholder="Enter research objective" 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !isDiscovering) {
                startDiscovery();
              }
            }}
            disabled={isDiscovering}
          />
          <button 
            className="glow-btn" 
            onClick={startDiscovery} 
            disabled={isDiscovering}
          >
            {isDiscovering ? 'Mission in Progress...' : 'Start Discovery'}
          </button>
        </div>
      </section>

      <section className="orchestration-canvas" style={{ display: 'flex', flexDirection: 'row', height: '100%', overflow: 'hidden' }}>
        <div style={{ flex: '4', minWidth: '30%', height: '100%', overflow: 'hidden' }}>
            <div className="agent-pipeline" style={{ height: '100%', overflowY: 'auto' }}>
          {Object.entries(agents).map(([id, state], index, array) => (
            <React.Fragment key={id}>
              <div className={`agent-node ${state.active ? 'active' : ''} ${state.completed ? 'completed' : ''}`}>
                <div className="agent-icon">{state.icon}</div>
                <div className="agent-info">
                  <h3>{state.label}</h3>
                  <span className="status">{state.status}</span>
                  <div className="log-output">{state.log}</div>
                  {state.tokens && (
                    <div className="token-usage" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '5px' }}>
                      <span title="Prompt Tokens">⬆️ {state.tokens.prompt_tokens}</span> | 
                      <span title="Completion Tokens" style={{ marginLeft: '5px' }}>⬇️ {state.tokens.completion_tokens}</span> | 
                      <span title="Total Tokens" style={{ marginLeft: '5px', fontWeight: 'bold' }}>Total: {state.tokens.total_tokens}</span>
                    </div>
                  )}
                </div>
              </div>
              {index < array.length - 1 && (
                <div className={`connector ${state.completed ? 'active' : ''}`}>↓</div>
              )}
            </React.Fragment>
          ))}
            </div>
          </div>
          <div className="ResizeHandleOuter" style={{ width: '10px', background: 'transparent', cursor: 'col-resize', flexShrink: 0 }}>
            <div className="ResizeHandleInner" style={{ width: '2px', height: '100%', background: 'var(--border-color)', margin: '0 auto' }} />
          </div>
          <div style={{ flex: '6', minWidth: '40%', height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div className="knowledge-graph glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflowY: 'hidden', margin: '0' }}>
          <h2>Discovery Artifacts</h2>
          <div className="artifact-container" style={{ flex: 1, overflowY: 'auto', paddingRight: '10px' }}>
            {artifacts.length === 0 ? (
              <p className="empty-text">No artifacts generated yet.</p>
            ) : (
              artifacts.map((art, idx) => {
                let parsedContent = null;
                let isHypotheses = false;
                let isGraphData = false;
                let isSimulation = false;
                
                try {
                  let rawContent = art.content;
                  
                  // Try to find a JSON array or object using regex to ignore conversational filler
                  const arrayMatch = rawContent.match(/\[[\s\S]*\]/);
                  const objectMatch = rawContent.match(/\{[\s\S]*\}/);
                  
                  if (arrayMatch) {
                      parsedContent = JSON.parse(arrayMatch[0]);
                  } else if (objectMatch) {
                      parsedContent = JSON.parse(objectMatch[0]);
                      // If it wrapped it in {"hypotheses": [...]}, extract it
                      if (parsedContent.hypotheses && Array.isArray(parsedContent.hypotheses)) {
                          parsedContent = parsedContent.hypotheses;
                      }
                  } else {
                      // Fallback to basic string manipulation if no match but it's pure json
                      if (rawContent.startsWith("```json")) {
                        rawContent = rawContent.replace(/^```json\n?/, '').replace(/```$/, '').trim();
                      }
                      parsedContent = JSON.parse(rawContent);
                  }

                  if (Array.isArray(parsedContent) && parsedContent.length > 0) {
                    // Check if it looks like a list of objects
                    if (typeof parsedContent[0] === 'object') {
                        isHypotheses = true;
                        // Normalize keys in case the LLM capitalized them differently
                        parsedContent = parsedContent.map(item => ({
                            title: item.title || item.Title || item.name || item.hypothesis || "Proposed Hypothesis",
                            cross_domain_inspiration: item.cross_domain_inspiration || item.Cross_Domain_Inspiration || item.inspiration || "Unknown Inspiration",
                            theoretical_basis: item.theoretical_basis || item.Theoretical_Basis || item.basis || "No theoretical basis provided",
                            proposed_simulation: item.proposed_simulation || item.Proposed_Simulation || item.simulation || "No simulation provided"
                        }));
                    }
                  } else if (parsedContent && typeof parsedContent === 'object' && !Array.isArray(parsedContent)) {
                    isGraphData = true;
                  }
                } catch (e) {
                  // Fallback if parsing completely fails
                }

                if (!isHypotheses && !isGraphData && art.content.includes("```python")) {
                  isSimulation = true;
                }

                return (
                  <div key={idx} className="artifact-card" style={{ marginBottom: '2rem' }}>
                    <h4>{art.name} Artifact</h4>
                    {isHypotheses ? (
                      <div style={{ marginTop: '1rem' }}>
                        {parsedContent.map((hyp, hIdx) => (
                          <HypothesisCard 
                            key={hIdx} 
                            hypothesis={hyp} 
                            onSelect={async (selectedHyp) => {
                              console.log("Selected", selectedHyp);
                              if (pipelineState === 'completed' || pipelineState === 'idle') {
                                setPipelineState('running');
                                try {
                                  const token = localStorage.getItem('auth_token');
                                  const res = await fetch(`${import.meta.env.VITE_BACKEND_URL}/api/branch`, {
                                    method: "POST",
                                    headers: {"Content-Type": "application/json"},
                                    body: JSON.stringify({ domain, query, hypothesis: selectedHyp, token })
                                  });
                                  if (res.ok) {
                                    const data = await res.json();
                                    setArtifacts(prev => [...prev, { name: "Branch Simulation", content: data.artifact }]);
                                    setPipelineState('completed');
                                  } else {
                                    alert("Failed to branch simulation");
                                    setPipelineState('completed');
                                  }
                                } catch(e) {
                                  console.error(e);
                                  setPipelineState('completed');
                                }
                              } else if (socket && socket.readyState === WebSocket.OPEN) {
                                socket.send(JSON.stringify({ action: "select_hypothesis", hypothesis: selectedHyp }));
                                setPipelineState('running');
                              }
                            }} 
                          />
                        ))}
                      </div>
                    ) : isGraphData ? (
                      <div style={{ marginTop: '1rem', background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '8px' }}>
                        <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
                          {JSON.stringify(parsedContent, null, 2)}
                        </pre>
                      </div>
                    ) : isSimulation ? (
                      <SimulationCanvas artifactContent={art.content} />
                    ) : (
                      <div className="markdown-preview" style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: '1.6' }}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{art.content}</ReactMarkdown>
                        {art.name === "SYSTEM ERROR" && art.content.includes("upgrade to PRO") && (
                          <button 
                            className="glow-btn" 
                            style={{ marginTop: '1rem', background: 'var(--accent-color)', fontWeight: 'bold' }} 
                            onClick={() => setShowBilling(true)}
                          >
                            Upgrade to PRO
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
            </div>
            {pipelineState === 'paused' && (
              <div className="refinement-panel glass-panel" style={{ marginTop: '10px', animation: 'fadeIn 0.5s ease', flexShrink: 0 }}>
                <h3>Human-in-the-Loop Refinement</h3>
                <p>Review the artifacts generated. You can guide the agent to fine-tune the results before moving to the next step.</p>
                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                  <input 
                    type="text" 
                    placeholder="E.g., Focus more on the thermal properties..." 
                    value={refinementText}
                    onChange={(e) => setRefinementText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && refinementText) {
                        sendRefinement();
                      }
                    }}
                    style={{ flex: 1 }}
                  />
                  <button className="glow-btn" onClick={sendRefinement} disabled={!refinementText}>
                    Refine Current Step
                  </button>
                  <button className="glow-btn" style={{ background: 'var(--accent-color)' }} onClick={proceedToNext}>
                    Proceed to Next Step
                  </button>
                  {(agents.domain_expert?.status === 'Waiting for User' || agents.simulation?.status === 'Waiting for User' || agents.validation?.status === 'Waiting for User') && (
                    <button className="glow-btn" style={{ background: '#e74c3c' }} onClick={goBackToHypotheses}>
                      Go Back to Hypotheses
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
      </section>
    </div>
  );
};

export default Dashboard;
