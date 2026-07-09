import { createSlice } from '@reduxjs/toolkit';

const initialState = {
  messages: [], // array of { role: 'user' | 'assistant', content: string }
};

const chatSlice = createSlice({
  name: 'chat',
  initialState,
  reducers: {
    addMessage: (state, action) => {
      state.messages.push(action.payload);
    },
    appendStreamText: (state, action) => {
      if (state.messages.length > 0) {
        const lastMsg = state.messages[state.messages.length - 1];
        if (lastMsg.role === 'assistant') {
          lastMsg.content += action.payload;
        }
      }
    }
  }
});

export const { addMessage, appendStreamText } = chatSlice.actions;
export default chatSlice.reducer;
