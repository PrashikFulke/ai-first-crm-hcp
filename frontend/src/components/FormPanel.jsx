import React, { useState, useEffect, useRef } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { submitInteraction } from '../services/api';
import { updateFormState, resetForm } from '../store/formSlice';

// Helper component for animated inputs
const AnimatedInput = ({ value, ...props }) => {
  const [isAnimating, setIsAnimating] = useState(false);
  const prevValue = useRef(value);

  useEffect(() => {
    if (value !== prevValue.current) {
      setIsAnimating(true);
      const timer = setTimeout(() => setIsAnimating(false), 1500);
      prevValue.current = value;
      return () => clearTimeout(timer);
    }
  }, [value]);

  return (
    <input 
      {...props} 
      value={value || ''} 
      className={`${props.className} ${isAnimating ? 'field-updated' : ''}`}
    />
  );
};

const AnimatedTextarea = ({ value, ...props }) => {
  const [isAnimating, setIsAnimating] = useState(false);
  const prevValue = useRef(value);

  useEffect(() => {
    if (value !== prevValue.current) {
      setIsAnimating(true);
      const timer = setTimeout(() => setIsAnimating(false), 1500);
      prevValue.current = value;
      return () => clearTimeout(timer);
    }
  }, [value]);

  return (
    <textarea 
      {...props} 
      value={value || ''} 
      className={`${props.className} ${isAnimating ? 'field-updated' : ''}`}
    />
  );
};

const AnimatedRadioGroup = ({ value, name, onChange, options }) => {
  const [isAnimating, setIsAnimating] = useState(false);
  const prevValue = useRef(value);

  useEffect(() => {
    if (value !== prevValue.current) {
      setIsAnimating(true);
      const timer = setTimeout(() => setIsAnimating(false), 1500);
      prevValue.current = value;
      return () => clearTimeout(timer);
    }
  }, [value]);

  return (
    <div 
      style={{ display: 'flex', gap: '1rem', marginTop: '0.25rem', padding: '0.5rem', borderRadius: '8px' }} 
      className={isAnimating ? 'field-updated' : ''}
    >
      {options.map(opt => (
        <label key={opt.value} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
          <input 
            type="radio" 
            name={name} 
            value={opt.value} 
            checked={value === opt.value || (!value && opt.value === 'Neutral')}
            onChange={onChange}
          />
          {opt.label}
        </label>
      ))}
    </div>
  );
};

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
      // Pass hcp_name (not a hardcoded UUID) so that submitInteraction in api.js
      // can auto-resolve the correct HCP UUID via /hcps/search, or let the backend
      // create a new HCP on the fly if no match is found.
      const payload = {
        hcp_name: formState.hcp_name,
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
    <div className="form-panel">
      <h2 className="form-title">Interaction Details</h2>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', marginBottom: '2.5rem' }}>
        <div className="form-group">
          <label className="form-label">HCP Name</label>
          <AnimatedInput 
            type="text" 
            name="hcp_name" 
            value={formState.hcp_name} 
            onChange={handleChange} 
            className="form-input"
          />
        </div>
        
        <div className="form-group">
          <label className="form-label">Topics Discussed</label>
          <AnimatedTextarea 
            name="topics_discussed" 
            value={formState.topics_discussed} 
            onChange={handleChange} 
            className="form-textarea"
          />
        </div>
        
        <div className="form-group">
          <label className="form-label">Sentiment</label>
          <AnimatedRadioGroup 
            name="sentiment" 
            value={formState.sentiment} 
            onChange={handleChange} 
            options={[
              { value: 'Positive', label: '😊 Positive' },
              { value: 'Neutral', label: '😐 Neutral' },
              { value: 'Negative', label: '🙁 Negative' }
            ]}
          />
        </div>

        {/* Arrays for Materials & Samples read-only views for demo purposes */}
        <div className="form-readonly-box">
          <div className="form-readonly-item">
            <strong>Materials Shared:</strong> {formState.materials_shared?.length > 0 ? formState.materials_shared.join(', ') : 'None'}
          </div>
          <div className="form-readonly-item">
            <strong>Samples Distributed:</strong> {formState.samples_distributed?.length > 0 ? formState.samples_distributed.join(', ') : 'None'}
          </div>
        </div>
      </div>
      
      {/* Validation errors from the agent's state_synchronizer node */}
      {formState.validation_errors?.length > 0 && (
        <div style={{
          marginBottom: '1rem',
          padding: '0.75rem 1rem',
          borderRadius: 'var(--radius-md)',
          backgroundColor: '#fff7ed',
          border: '1px solid #fed7aa',
          color: '#9a3412',
          fontSize: '0.875rem'
        }}>
          <strong style={{ display: 'block', marginBottom: '0.35rem' }}>⚠ Missing required fields:</strong>
          <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
            {formState.validation_errors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      <button 
        onClick={handleLog} 
        className="btn-primary"
      >
        {formState.interaction_id ? 'Update Interaction' : 'Log Interaction'}
      </button>
      
      {feedback.message && (
        <div className={`feedback-msg feedback-${feedback.type}`}>
          {feedback.message}
        </div>
      )}
    </div>
  );
};

export default FormPanel;
