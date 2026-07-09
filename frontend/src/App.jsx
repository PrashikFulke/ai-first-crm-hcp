import React, { useState, useEffect, useCallback } from 'react';
import FormPanel from './components/FormPanel';
import ChatPanel from './components/ChatPanel';

function App() {
  const [leftWidth, setLeftWidth] = useState(40);
  const [isDragging, setIsDragging] = useState(false);

  const handleMouseDown = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleMouseMove = useCallback((e) => {
    if (!isDragging) return;
    const newLeftWidth = (e.clientX / window.innerWidth) * 100;
    if (newLeftWidth > 20 && newLeftWidth < 80) {
      setLeftWidth(newLeftWidth);
    }
  }, [isDragging]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    } else {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

  return (
    <div className="app-container" style={{ cursor: isDragging ? 'col-resize' : 'auto' }}>
      {/* Left side: Structured Form Panel */}
      <div className="form-panel-container" style={{ width: `${leftWidth}%`, flexShrink: 0 }}>
        <FormPanel />
      </div>
      
      {/* Resizer Divider */}
      <div 
        className="resizer" 
        onMouseDown={handleMouseDown} 
        title="Drag to resize"
      />
      
      {/* Right side: Conversational AI Chat Panel */}
      <div className="chat-panel-container" style={{ width: `calc(${100 - leftWidth}% - 6px)`, flexGrow: 1 }}>
        <ChatPanel />
      </div>
    </div>
  );
}

export default App;
