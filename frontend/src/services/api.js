import { appendStreamText, addMessage } from '../store/chatSlice';
import { updateFormState, setValidationErrors } from '../store/formSlice';

const BASE_URL = 'http://localhost:8000/api/v1';

export const submitInteraction = async (formState) => {
  let resolvedHcpId = formState.hcp_id;

  // 1. Auto-Resolve HCP ID
  if (!resolvedHcpId && formState.hcp_name) {
    try {
      const searchRes = await fetch(`${BASE_URL}/hcps/search?q=${encodeURIComponent(formState.hcp_name)}`);
      if (searchRes.ok) {
        const hcps = await searchRes.json();
        if (hcps && hcps.length > 0) {
          resolvedHcpId = hcps[0].id;
        }
      }
    } catch (e) {
      console.warn("Failed to auto-resolve HCP ID", e);
    }
  }

  // Fallback to a valid UUID if nothing is found (prevents null constraint error for UUID type)
  if (!resolvedHcpId) {
    resolvedHcpId = "00000000-0000-0000-0000-000000000000";
  }

  // 2. Build the Strict Payload
  const payload = {
    hcp_id: resolvedHcpId,
    hcp_name: formState.hcp_name || "",
    interaction_type: formState.interaction_type || "In-Person",
    interaction_date: new Date().toISOString().split('T')[0],
    interaction_time: new Date().toTimeString().split(' ')[0],
    topics_discussed: formState.topics_discussed || "",
    sentiment: formState.sentiment || "Neutral",
    outcomes: formState.outcomes || "Pending",
    // Field names are now consistent: formSlice, InteractionPatch, and InteractionExtraction
    // all use materials_shared / samples_distributed, so no alias fallback needed.
    attendee_names: formState.attendee_names || [],
    materials_shared: formState.materials_shared || [],
    samples_distributed: formState.samples_distributed || [],
    follow_up_actions: formState.follow_up_actions || []
  };

  // 3. Execute the Request (POST for new, PATCH for overwrite)
  const isUpdate = !!formState.interaction_id;
  const endpoint = isUpdate ? `${BASE_URL}/interactions/${formState.interaction_id}` : `${BASE_URL}/interactions`;
  const method = isUpdate ? 'PATCH' : 'POST';

  const response = await fetch(endpoint, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  
  if (!response.ok) {
    throw new Error('Failed to submit interaction');
  }
  return response.json();
};

export const streamChat = async (message, currentFormState, dispatch, signal) => {
  try {
    // 1. Add user message to chat immediately
    dispatch(addMessage({ role: 'user', content: message }));
    
    // 2. Add an empty assistant message placeholder to receive streaming text
    dispatch(addMessage({ role: 'assistant', content: '' }));

    const response = await fetch(`${BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, current_form_state: currentFormState }),
      signal
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
            } else if (event === 'validation_errors') {
              // Dispatch the errors array returned by the state_synchronizer node.
              dispatch(setValidationErrors(data));
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
    if (error.name === 'AbortError') {
      console.log('Stream aborted by user');
    } else {
      console.error('Chat stream error:', error);
      dispatch(appendStreamText('\n\n[Error: Connection failed]'));
    }
  }
};
