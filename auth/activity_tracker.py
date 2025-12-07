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

    @staticmethod
    def watch_value(key, value):
        """
        Detect state change in radio/buttons/selectbox etc.
        """
        hash_value = hash(str(value))
        prev = st.session_state.get(f"_prev_{key}")

        if prev != hash_value:
            st.session_state[f"_prev_{key}"] = hash_value
            ActivityTracker.update()

    @staticmethod
    def watch_tab(key, current_tab):
        """
        Detect tab switching.
        """
        prev_tab = st.session_state.get(f"_prev_tab_{key}")

        if prev_tab != current_tab:
            st.session_state[f"_prev_tab_{key}"] = current_tab
            ActivityTracker.update()

    @staticmethod
    def watch_form(submitted):
        """Detect form submit."""
        if submitted:
            ActivityTracker.update()
