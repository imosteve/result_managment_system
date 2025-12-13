# util/paginators.py

import streamlit as st
import math
import logging
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder


logger = logging.getLogger(__name__)

def streamlit_paginator(data, table_name):
    """
    Paginator with search and filter functionality for streamlit dataframes
    """
    # Convert to DataFrame if not already
    df = pd.DataFrame(data) if not isinstance(data, pd.DataFrame) else data.copy()
    
    # Initialize session state for search and filter
    if f"search_{table_name}" not in st.session_state:
        st.session_state[f"search_{table_name}"] = ""
    if f"filter_col_{table_name}" not in st.session_state:
        st.session_state[f"filter_col_{table_name}"] = "All Columns"
    if f"filter_value_{table_name}" not in st.session_state:
        st.session_state[f"filter_value_{table_name}"] = ""
    
    with st.container(border=True):
        # Search bar
        col1, col2, col3 = st.columns([5, 3, 1], vertical_alignment="bottom")
        
        with col2:
            search_term = st.text_input(
                "Search across all columns",
                key=f"search_input_{table_name}",
                placeholder="Type to search...",
                value=st.session_state[f"search_{table_name}"]
            )
            st.session_state[f"search_{table_name}"] = search_term
        
        with col3:
            if st.button("Clear", key=f"clear_{table_name}"):
                st.session_state[f"search_{table_name}"] = ""
                st.session_state[f"filter_col_{table_name}"] = "All Columns"
                st.session_state[f"filter_value_{table_name}"] = ""
                st.session_state[f"page_{table_name}"] = 1
                st.rerun()
        
        # Column-specific filter
        with col1:
            col_fil_col, col_fil_val = st.columns(2)
            if len(df.columns) > 0:
                with col_fil_col:
                    # Determine the correct index for the selectbox
                    all_options = ["All Columns"] + list(df.columns)
                    current_filter = st.session_state[f"filter_col_{table_name}"]
                    default_index = all_options.index(current_filter) if current_filter in all_options else 0
                    
                    filter_col = st.selectbox(
                        "Filter by column",
                        options=all_options,
                        key=f"filter_col_input_{table_name}",
                        index=default_index
                    )
                    st.session_state[f"filter_col_{table_name}"] = filter_col
                    
                with col_fil_val:
                    filter_value = st.text_input(
                        "Filter value",
                        key=f"filter_value_input_{table_name}",
                        placeholder="Enter value to filter...",
                        value=st.session_state[f"filter_value_{table_name}"]
                    )
                    st.session_state[f"filter_value_{table_name}"] = filter_value
        
        # Apply search filter
        filtered_df = df.copy()
        
        if search_term:
            # Search across all columns
            mask = filtered_df.astype(str).apply(
                lambda row: row.str.contains(search_term, case=False, na=False).any(),
                axis=1
            )
            filtered_df = filtered_df[mask]
        
        # Apply column-specific filter
        if filter_value and filter_col != "All Columns":
            mask = filtered_df[filter_col].astype(str).str.contains(
                filter_value, case=False, na=False
            )
            filtered_df = filtered_df[mask]
        
        # Display filter results
        if len(filtered_df) < len(df):
            st.info(f"Found {len(filtered_df)} matching results out of {len(df)} total entries")
        
        col_page, col_items = st.columns([1, 3], vertical_alignment="bottom", gap="large")
        # Pagination settings
        with col_page:
            items_per_page = st.selectbox(
                "Items per page",
                options=[10, 20, 50, 100],
                index=1,
                key=f"items_per_page_{table_name}"
            )
        
        total_items = len(filtered_df)
        total_pages = math.ceil(total_items / items_per_page) if total_items > 0 else 1

        # Pagination controls in one compact row
        with col_items:
            col1, col2, col3 = st.columns([0.8, 3, 0.6])
            
            with col1:
                if st.button("◀ Previous", key=f"prev_{table_name}", disabled=(st.session_state.get(f"page_{table_name}", 1) <= 1)):
                    st.session_state[f"page_{table_name}"] = max(1, st.session_state.get(f"page_{table_name}", 1) - 1)
                    st.rerun()
            
            with col2:
                if f"page_{table_name}" not in st.session_state:
                    st.session_state[f"page_{table_name}"] = 1
                
                page = st.number_input(
                    "Page", 
                    min_value=1, 
                    max_value=total_pages, 
                    step=1, 
                    value=st.session_state[f"page_{table_name}"],
                    key=f"page_selector_{table_name}",
                    label_visibility="collapsed"
                )
                st.session_state[f"page_{table_name}"] = page
            
            with col3:
                if st.button("Next ▶", key=f"next_{table_name}", disabled=(page >= total_pages)):
                    st.session_state[f"page_{table_name}"] = min(total_pages, page + 1)
                    st.rerun()

    # Slice data
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_data = filtered_df.iloc[start_idx:end_idx]

    table_height = len(page_data)-5 if len(page_data) > 40 else len(page_data)-1 if len(page_data) > 10 else len(page_data)+1

    # Display current page
    if len(page_data) > 0:
        st.dataframe(
            page_data, 
            width="stretch", 
            hide_index=True,
            height=40*table_height
            )
        st.caption(f"Showing {start_idx + 1} – {min(end_idx, total_items)} of {total_items} entries")
    else:
        st.warning("No results found matching your search criteria.")


def streamlit_filter(data, table_name):
    """
    Filter functionality for streamlit dataframes - returns filtered DataFrame
    """
    # Convert to DataFrame if not already
    df = pd.DataFrame(data) if not isinstance(data, pd.DataFrame) else data.copy()
    
    # Initialize session state for search and filter
    if f"search_{table_name}" not in st.session_state:
        st.session_state[f"search_{table_name}"] = ""
    if f"filter_col_{table_name}" not in st.session_state:
        st.session_state[f"filter_col_{table_name}"] = "All Columns"
    if f"filter_value_{table_name}" not in st.session_state:
        st.session_state[f"filter_value_{table_name}"] = ""
    
    with st.container(border=True):
        # Search bar
        col1, col2, col3 = st.columns([5, 3, 1], vertical_alignment="bottom")
        
        with col2:
            search_term = st.text_input(
                "Search across all columns",
                key=f"search_input_{table_name}",
                placeholder="Type to search...",
                value=st.session_state[f"search_{table_name}"]
            )
            st.session_state[f"search_{table_name}"] = search_term
        
        with col3:
            if st.button("Clear", key=f"clear_{table_name}"):
                st.session_state[f"search_{table_name}"] = ""
                st.session_state[f"filter_col_{table_name}"] = "All Columns"
                st.session_state[f"filter_value_{table_name}"] = ""
                st.rerun()
        
        # Column-specific filter
        with col1:
            col_fil_col, col_fil_val = st.columns(2)
            if len(df.columns) > 0:
                with col_fil_col:
                    # Determine the correct index for the selectbox
                    all_options = ["All Columns"] + list(df.columns)
                    current_filter = st.session_state[f"filter_col_{table_name}"]
                    default_index = all_options.index(current_filter) if current_filter in all_options else 0
                    
                    filter_col = st.selectbox(
                        "Filter by column",
                        options=all_options,
                        key=f"filter_col_input_{table_name}",
                        index=default_index
                    )
                    st.session_state[f"filter_col_{table_name}"] = filter_col
                    
                with col_fil_val:
                    filter_value = st.text_input(
                        "Filter value",
                        key=f"filter_value_input_{table_name}",
                        placeholder="Enter value to filter...",
                        value=st.session_state[f"filter_value_{table_name}"]
                    )
                    st.session_state[f"filter_value_{table_name}"] = filter_value
        
        # Apply search filter
        filtered_df = df.copy()
        
        if search_term:
            # Search across all columns
            mask = filtered_df.astype(str).apply(
                lambda row: row.str.contains(search_term, case=False, na=False).any(),
                axis=1
            )
            filtered_df = filtered_df[mask]
        
        # Apply column-specific filter
        if filter_value and filter_col != "All Columns":
            mask = filtered_df[filter_col].astype(str).str.contains(
                filter_value, case=False, na=False
            )
            filtered_df = filtered_df[mask]
        
        # Display filter results
        if len(filtered_df) < len(df):
            st.info(f"Found {len(filtered_df)} matching results out of {len(df)} total entries")

    # Return the filtered DataFrame
    if len(filtered_df) > 0:
        return filtered_df
    else:
        return pd.DataFrame()  # Return empty DataFrame if no results