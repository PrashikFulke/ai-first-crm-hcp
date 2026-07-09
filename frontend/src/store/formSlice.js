import { createSlice } from '@reduxjs/toolkit';

const initialState = {
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
  follow_up_actions: []
};

const formSlice = createSlice({
  name: 'form',
  initialState,
  reducers: {
    updateFormState: (state, action) => {
      // Merge new fields from the agent over the current state incrementally
      return { ...state, ...action.payload };
    },
    resetForm: () => initialState
  }
});

export const { updateFormState, resetForm } = formSlice.actions;
export default formSlice.reducer;
