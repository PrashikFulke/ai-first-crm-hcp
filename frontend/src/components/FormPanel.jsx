import React, { useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { submitInteraction } from '../services/api';
import { updateFormState, resetForm } from '../store/formSlice';

const FormPanel = () => {
  const formState = useSelector(state => state.form);
  const dispatch = useDispatch();
  const [feedback, setFeedback] = useState({ type: '', message: '' });

  const handleChange = (e) => {
    const { name, value } = e.target;
    dispatch(updateFormState({ [name]: value }));
  };

  const handleLog = async () => {
    setFeedback({ type: 'info', message: 'Submitting...' });
    try {
      // In a real application, you would match the HCP Name string to an actual UUID via typeahead.
      // We pass a dummy UUID here for demonstration since the API expects one.
      const payload = {
        hcp_id: "00000000-0000-0000-0000-000000000000",
        interaction_type: formState.interaction_type,
        interaction_date: formState.interaction_date,
        interaction_time: formState.interaction_time,
        topics_discussed: formState.topics_discussed,
        sentiment: formState.sentiment,
        outcomes: formState.outcomes,
        attendee_names: formState.attendee_names,
        materials_shared: formState.materials_shared,
        samples_distributed: formState.samples_distributed,
        follow_up_actions: formState.follow_up_actions
      };
      
      await submitInteraction(payload);
      setFeedback({ type: 'success', message: 'Interaction logged successfully!' });
      
      // Clear form after success
      setTimeout(() => {
        setFeedback({ type: '', message: '' });
        dispatch(resetForm());
      }, 3000);
      
    } catch (err) {
      setFeedback({ type: 'error', message: 'Failed to log interaction. Please check the backend.' });
      console.error(err);
    }
  };

  return (
    <div style={{ padding: '1.5rem', height: '100%', overflowY: 'auto', fontFamily: 'Inter, sans-serif' }}>
      <h2 style={{ marginBottom: '1.5rem', color: '#111' }}>Interaction Details</h2>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', marginBottom: '2.5rem' }}>
        <label style={{ display: 'flex', flexDirection: 'column', fontWeight: '500', color: '#444' }}>
          HCP Name
          <input 
            type="text" 
            name="hcp_name" 
            value={formState.hcp_name || ''} 
            onChange={handleChange} 
            style={{ marginTop: '0.25rem', padding: '0.75rem', borderRadius: '6px', border: '1px solid #ccc' }} 
          />
        </label>
        
        <label style={{ display: 'flex', flexDirection: 'column', fontWeight: '500', color: '#444' }}>
          Topics Discussed
          <textarea 
            name="topics_discussed" 
            value={formState.topics_discussed || ''} 
            onChange={handleChange} 
            style={{ marginTop: '0.25rem', padding: '0.75rem', borderRadius: '6px', border: '1px solid #ccc', minHeight: '100px' }} 
          />
        </label>
        
        <label style={{ display: 'flex', flexDirection: 'column', fontWeight: '500', color: '#444' }}>
          Sentiment
          <select 
            name="sentiment" 
            value={formState.sentiment || 'Neutral'} 
            onChange={handleChange} 
            style={{ marginTop: '0.25rem', padding: '0.75rem', borderRadius: '6px', border: '1px solid #ccc' }}
          >
            <option value="Positive">Positive</option>
            <option value="Neutral">Neutral</option>
            <option value="Negative">Negative</option>
          </select>
        </label>

        {/* Arrays for Materials & Samples read-only views for demo purposes */}
        <div style={{ backgroundColor: '#f4f6f8', padding: '1rem', borderRadius: '6px' }}>
          <div style={{ marginBottom: '0.5rem' }}>
            <strong style={{ color: '#333' }}>Materials Shared:</strong> {formState.materials_shared?.length > 0 ? formState.materials_shared.join(', ') : 'None'}
          </div>
          <div>
            <strong style={{ color: '#333' }}>Samples Distributed:</strong> {formState.samples_distributed?.length > 0 ? formState.samples_distributed.join(', ') : 'None'}
          </div>
        </div>
      </div>
      
      <button 
        onClick={handleLog} 
        style={{ 
          width: '100%', 
          padding: '1rem', 
          backgroundColor: '#00c853', 
          color: 'white', 
          border: 'none', 
          borderRadius: '8px', 
          cursor: 'pointer', 
          fontSize: '1rem',
          fontWeight: 'bold',
          transition: 'background-color 0.2s'
        }}
      >
        Log Interaction
      </button>
      
      {feedback.message && (
        <div style={{ 
          marginTop: '1rem', 
          padding: '1rem', 
          borderRadius: '6px',
          backgroundColor: feedback.type === 'success' ? '#e8f5e9' : feedback.type === 'error' ? '#ffebee' : '#e3f2fd',
          color: feedback.type === 'success' ? '#2e7d32' : feedback.type === 'error' ? '#c62828' : '#1565c0'
        }}>
          {feedback.message}
        </div>
      )}
    </div>
  );
};

export default FormPanel;
