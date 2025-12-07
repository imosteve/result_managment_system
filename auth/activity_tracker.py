# auth/activity_tracker.py

import streamlit as st
from datetime import datetime

class ActivityTracker:

    @staticmethod
    def init():
        """Initialize last_activity only once."""
        if "last_activity" not in st.session_state:
            st.session_state.last_activity = datetime.now()
        if "last_interaction_hash" not in st.session_state:
            st.session_state.last_interaction_hash = None

    @staticmethod
    def update():
        """Mark last_activity as user activity."""
        st.session_state.last_activity = datetime.now()
        # st.rerun()

    @staticmethod
    def watch_value(key, value):
        """
        Detect state change in radio/buttons/selectbox etc.
        Only updates if the value actually changed.
        """
        # Skip if value is None or empty string (initial state)
        if value is None or value == "":
            return
            
        hash_value = hash(str(value))
        prev = st.session_state.get(f"_prev_{key}")

        # Only update if this is a NEW value (not just re-rendering)
        if prev is not None and prev != hash_value:
            st.session_state[f"_prev_{key}"] = hash_value
            ActivityTracker.update()
        elif prev is None:
            # First time seeing this widget, just store the value without updating
            st.session_state[f"_prev_{key}"] = hash_value

    @staticmethod
    def watch_tab(key, current_tab):
        """
        Detect tab switching.
        """
        prev_tab = st.session_state.get(f"_prev_tab_{key}")

        if prev_tab is not None and prev_tab != current_tab:
            st.session_state[f"_prev_tab_{key}"] = current_tab
            ActivityTracker.update()
        elif prev_tab is None:
            # First time, just store without updating
            st.session_state[f"_prev_tab_{key}"] = current_tab

    @staticmethod
    def watch_form(submitted):
        """Detect form submit."""
        if submitted:
            ActivityTracker.update()