import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User } from 'lucide-react';

const ChatPanel = ({ onClose }) => {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hello! I am the OS Assistant. How can I help you query the knowledge base today?' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch(`${import.meta.env.VITE_BACKEND_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          message: userMessage.content,
          token: localStorage.getItem('auth_token')
        })
      });
      
      const data = await response.json();
      
      if (response.status === 402) {
        setMessages(prev => [...prev, { role: 'assistant', content: '🚫 ' + data.detail }]);
      } else if (!response.ok) {
        setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${data.detail || 'Unknown error'}` }]);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, the chat endpoint is currently unavailable. Please make sure the backend is running.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-panel glass-panel floating">
      <div className="chat-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2><Bot size={24} color="var(--accent-purple)" /> OS Chat</h2>
        {onClose && (
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#fff', fontSize: '1.2rem', cursor: 'pointer' }}>
            &times;
          </button>
        )}
      </div>
      
      <div className="chat-messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            {msg.content}
          </div>
        ))}
        {isLoading && (
          <div className="message assistant">
            <span style={{opacity: 0.7}}>Analyzing...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input">
        <input 
          type="text" 
          placeholder="Ask about papers, experiments, or system status..." 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          disabled={isLoading}
        />
        <button onClick={handleSend} disabled={isLoading || !input.trim()}>
          <Send size={18} />
        </button>
      </div>
    </div>
  );
};

export default ChatPanel;
