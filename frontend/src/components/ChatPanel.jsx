import React, { useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { streamChat } from '../services/api';

const ChatPanel = () => {
  const [inputValue, setInputValue] = useState('');
  const messages = useSelector(state => state.chat.messages);
  const formState = useSelector(state => state.form);
  const dispatch = useDispatch();

  const handleSend = (e) => {
    e.preventDefault();
    if (!inputValue.trim()) return;
    
    // Dispatch network request
    streamChat(inputValue, formState, dispatch);
    setInputValue(''); // Clear input instantly
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', fontFamily: 'Inter, sans-serif' }}>
      
      {/* Messages Render Area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', backgroundColor: '#f8f9fa' }}>
        {messages.map((msg, idx) => (
          <div key={idx} style={{ marginBottom: '1rem', textAlign: msg.role === 'user' ? 'right' : 'left' }}>
            <div style={{ 
              display: 'inline-block', 
              padding: '0.85rem 1rem', 
              borderRadius: '12px',
              maxWidth: '80%',
              lineHeight: '1.4',
              backgroundColor: msg.role === 'user' ? '#0066ff' : '#ffffff',
              color: msg.role === 'user' ? 'white' : '#333',
              boxShadow: '0 2px 5px rgba(0,0,0,0.05)',
              border: msg.role === 'assistant' ? '1px solid #eaeaea' : 'none',
              whiteSpace: 'pre-wrap'
            }}>
              {msg.content || <span style={{ color: '#aaa' }}>Thinking...</span>}
            </div>
          </div>
        ))}
      </div>
      
      {/* Chat Input */}
      <form onSubmit={handleSend} style={{ display: 'flex', padding: '1rem', borderTop: '1px solid #e0e0e0', backgroundColor: '#fff' }}>
        <input 
          type="text" 
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Type notes or request a correction..."
          style={{ flex: 1, padding: '0.85rem', borderRadius: '8px', border: '1px solid #ccc', fontSize: '1rem' }}
        />
        <button type="submit" style={{ 
          marginLeft: '0.5rem', 
          padding: '0 1.5rem', 
          backgroundColor: '#0066ff', 
          color: 'white', 
          border: 'none', 
          borderRadius: '8px', 
          cursor: 'pointer',
          fontWeight: '600'
        }}>
          Send
        </button>
      </form>
    </div>
  );
};

export default ChatPanel;
