# util/paginators.py

import streamlit as st
import math
import logging
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder


logger = logging.getLogger(__name__)

def streamlit_paginator(data, table_name):

    # Pagination settings
    items_per_page = 20
    total_items = len(data)
    total_pages = math.ceil(total_items / items_per_page)

    # Page selector
    page = st.number_input(
        "Page", min_value=1, max_value=total_pages, step=1, value=1, key=f"page_selector_{table_name}"
    )

    # Slice data
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_data = data[start_idx:end_idx]

    # Display current page
    st.dataframe(page_data, width="stretch")

    st.caption(f"Showing {start_idx + 1} – {min(end_idx, total_items)} of {total_items} entries")


def st_aggrid_paginator(data, table_name):

    # Convert to DataFrame
    df = pd.DataFrame(data)

    # --- User-selectable pagination size ---
    page_size = st.selectbox(
        "Rows per page",
        options=[10, 20, 30, 50, 100],
        index=0,
        key=f"page_size_select_{table_name}"
    )

    # --- Build grid options ---
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_pagination(paginationAutoPageSize=True, paginationPageSize=page_size)
    gb.configure_default_column(min_column_width=20, resizable=False, filter=True, sortable=True)
    gridOptions = gb.build()

    # --- Custom CSS styling ---
    st.markdown("""
        <style>
            .ag-root-wrapper {
                border: 2px solid #dcdcdc !important;
                border-radius: 10px !important;
                overflow: hidden;
            }
            .ag-cell {
                padding: 2px !important;
                font-size: 12px;
            }
        </style>
    """, unsafe_allow_html=True)

    # --- Dynamic height based on pagination size ---
    row_height = 50  # pixels per row
    header_height = 15

    # Height = (row height × rows per page) + header
    table_height = row_height * page_size + header_height

    # --- Render grid ---
    AgGrid(
        df,
        gridOptions=gridOptions,
        theme='material',
        fit_columns_on_grid_load=False,
        height=table_height,
        # show_toolbar=True
    )

