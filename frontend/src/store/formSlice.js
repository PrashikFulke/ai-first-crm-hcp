import { createSlice } from '@reduxjs/toolkit';

const initialState = {
  interaction_id: null,
  hcp_name: '',
  interaction_type: 'Virtual', // Default interaction type
  interaction_date: new Date().toISOString().split('T')[0], // Today
  interaction_time: '12:00',
  topics_discussed: '',
  sentiment: 'Neutral',
  outcomes: '',
  attendee_names: [],
  materials_shared: [],
  samples_distributed: [],
  follow_up_actions: [],
  // Populated by the agent's state_synchronizer node when mandatory fields are missing.
  validation_errors: []
};

const formSlice = createSlice({
  name: 'form',
  initialState,
  reducers: {
    updateFormState: (state, action) => {
      // Merge new fields from the agent over the current state incrementally.
      // validation_errors is excluded from this merge — it has its own dedicated reducer.
      const { validation_errors, ...formFields } = action.payload;
      return { ...state, ...formFields };
    },
    setValidationErrors: (state, action) => {
      // Receives the validation_errors array from the state_synchronizer SSE event.
      state.validation_errors = action.payload;
    },
    resetForm: () => initialState
  }
});

export const { updateFormState, setValidationErrors, resetForm } = formSlice.actions;
export default formSlice.reducer;
