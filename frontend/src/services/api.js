import { appendStreamText, addMessage } from '../store/chatSlice';
import { updateFormState } from '../store/formSlice';

const BASE_URL = 'http://localhost:8000/api/v1';

export const submitInteraction = async (formState) => {
  const response = await fetch(`${BASE_URL}/interactions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(formState)
  });
  
  if (!response.ok) {
    throw new Error('Failed to submit interaction');
  }
  return response.json();
};

export const streamChat = async (message, currentFormState, dispatch) => {
  try {
    // 1. Add user message to chat immediately
    dispatch(addMessage({ role: 'user', content: message }));
    
    // 2. Add an empty assistant message placeholder to receive streaming text
    dispatch(addMessage({ role: 'assistant', content: '' }));

    const response = await fetch(`${BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, current_form_state: currentFormState })
    });

    if (!response.body) throw new Error('ReadableStream not supported.');

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    // 3. Decode the SSE stream
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      
      // SSE messages are separated by double newlines
      const parts = buffer.split('\n\n');
      
      // The last part might be incomplete, keep it in the buffer
      buffer = parts.pop(); 

      for (const part of parts) {
        if (!part.trim()) continue;
        
        const lines = part.split('\n');
        const eventLine = lines.find(l => l.startsWith('event:'));
        const dataLine = lines.find(l => l.startsWith('data:'));
        
        if (eventLine && dataLine) {
          const event = eventLine.replace('event:', '').trim();
          const dataStr = dataLine.replace('data:', '').trim();
          
          if (!dataStr) continue;
          
          try {
            const data = JSON.parse(dataStr);
            
            // Dispatch accordingly based on event type
            if (event === 'form_update') {
              dispatch(updateFormState(data));
            } else if (event === 'text_chunk') {
              dispatch(appendStreamText(data.text));
            }
          } catch (e) {
            console.error('Failed to parse SSE JSON chunk:', e);
          }
        }
      }
    }
  } catch (error) {
    console.error('Chat stream error:', error);
    dispatch(appendStreamText('\n\n[Error: Connection failed]'));
  }
};
