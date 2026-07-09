import React, { useState, useEffect, useRef } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { streamChat } from '../services/api';

const ChatPanel = () => {
  const [inputValue, setInputValue] = useState('');
  const messages = useSelector(state => state.chat.messages);
  const formState = useSelector(state => state.form);
  const dispatch = useDispatch();
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = (e) => {
    e.preventDefault();
    if (!inputValue.trim()) return;
    
    // Dispatch network request
    streamChat(inputValue, formState, dispatch);
    setInputValue(''); // Clear input instantly
  };

  return (
    <div className="chat-panel">
      
      {/* Chat Header */}
      <div className="chat-header" style={{ padding: '1.5rem 2rem 0 2rem' }}>
        <h2 style={{ margin: '0 0 0.25rem 0', color: 'var(--color-text-main)', fontSize: '1.75rem' }}>Ai-Assistant 🛠️</h2>
        <p style={{ margin: 0, fontStyle: 'italic', color: 'var(--color-text-muted)', fontSize: '0.95rem' }}>
          Type the information you have and the form will be filled accordingly by me
        </p>
      </div>

      {/* Messages Render Area */}
      <div className="chat-messages">
        {messages.map((msg, idx) => {
          const isSuccess = msg.role === 'assistant' && (
            (msg.content || '').toLowerCase().includes('successfully logged') || 
            (msg.content || '').toLowerCase().includes('logged the interaction')
          );
          
          return (
            <div key={idx} className={`chat-message-row ${msg.role === 'user' ? 'user' : 'ai'}`}>
              <div className={`chat-bubble ${msg.role === 'user' ? 'user' : 'ai'} ${isSuccess ? 'success-bubble' : ''}`}>
                {msg.content || <span style={{ opacity: 0.6 }}>Thinking...</span>}
              </div>
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>
      
      {/* Chat Input */}
      <form onSubmit={handleSend} className="chat-input-container">
        <div className="chat-input-wrapper">
          <input 
            type="text" 
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Type notes or request a correction..."
            className="chat-input"
          />
          <button type="submit" className="chat-send-btn" title="Send message">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
        </div>
      </form>
    </div>
  );
};

export default ChatPanel;
