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
        {messages.map((msg, idx) => (
          <div key={idx} className={`chat-message-row ${msg.role === 'user' ? 'user' : 'ai'}`}>
            <div className={`chat-bubble ${msg.role === 'user' ? 'user' : 'ai'}`}>
              {msg.content || <span style={{ opacity: 0.6 }}>Thinking...</span>}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      
      {/* Chat Input */}
      <form onSubmit={handleSend} className="chat-input-container">
        <input 
          type="text" 
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Type notes or request a correction..."
          className="chat-input"
        />
        <button type="submit" className="chat-send-btn">
          Send
        </button>
      </form>
    </div>
  );
};

export default ChatPanel;
