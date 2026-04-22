import streamlit as st
import pandas as pd
import plotly.express as px
import random
from src.normalise import normalise_dispensing, normalise_invoices, normalise_tariff
from src.match import match_records
from src.calc import calculate_metrics

# Mock Database Function
def fetch_mock_historical_data(current_margin, current_opportunity):
    history = []
    
    history.append({
        'Month': 'Feb 2026',
        'Realised Margin': current_margin * random.uniform(0.85, 0.95),
        'Unrealised Opportunity': current_opportunity * random.uniform(1.2, 1.4)
    })
    
    history.append({
        'Month': 'Mar 2026',
        'Realised Margin': current_margin * random.uniform(0.90, 1.00),
        'Unrealised Opportunity': current_opportunity * random.uniform(1.1, 1.25)
    })
    
    history.append({
        'Month': 'Apr 2026',
        'Realised Margin': current_margin,
        'Unrealised Opportunity': current_opportunity
    })
    
    df_history = pd.DataFrame(history)
    return df_history

# Page Configuration & Styling
st.set_page_config(page_title="MarginGuard AI | Practice Analytics", layout="wide", page_icon="🏦")

st.markdown("""
    <style>
    .metric-container { background-color: #f0f2f6; padding: 1.5rem; border-radius: 0.5rem; }
    .stDataFrame [data-testid="stTable"] td:nth-child(n+3) { text-align: right; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏦 MarginGuard AI")
st.caption("Commercial Intelligence for Dispensing GP Practices")

# Sidebar: Data Ingestion
with st.sidebar:
    st.header("Input Data")
    disp_file = st.file_uploader("Monthly Dispensing Export", type="csv")
    inv_file = st.file_uploader("Supplier Invoice Export", type="csv")
    st.divider()
    st.write("Current Tariff: **April 2026**")
    st.divider()
    mds_active = st.toggle("MDS / Rebate Schemes Active", value=False, help="Enable this if the practice receives overriding volume discounts from manufacturers.")

    if st.button("Reset Dashboard"):
        st.session_state.clear()
        st.rerun()

if disp_file and inv_file:
    # 1. Initialise & Process Master Data
    if 'master_data' not in st.session_state:
        with st.spinner("Calculating NHS Reimbursement & Leakage..."):
            disp_df = pd.read_csv(disp_file, dtype={'dm_d_code': str})
            inv_df = pd.read_csv(inv_file, dtype={'dm_d_code': str})
            tariff_raw = pd.read_csv("Part VIIIA April 2026.csv", dtype=str)
            
            if 'VMPP Snomed Code' not in tariff_raw.columns:
                tariff_raw = pd.read_csv("Part VIIIA April 2026.csv", skiprows=2, dtype=str)
            dnd_df = pd.read_csv("dnd_mock.csv", dtype={'dm_d_code': str})

            matched = match_records(normalise_dispensing(disp_df), normalise_invoices(inv_df))
            st.session_state.master_data = calculate_metrics(matched, normalise_tariff(tariff_raw), dnd_df)

    df = st.session_state.master_data.copy()

    # 2. Data Segregation
    incomplete_mask = (df['acquisition_cost_gbp'] == 0.0) | (df['acquisition_cost_gbp'].isna())
    incomplete_data = df[incomplete_mask].copy()

    st.divider()

    # 3. Action Required: Missing Data
    if not incomplete_data.empty:
        st.subheader("⚠️ Action Required: Missing Invoice Data")
        st.write("The following lines lack an acquisition cost. Please enter the missing costs below to instantly update your P&L.")
        
        edited_incomplete = st.data_editor(
            incomplete_data,
            use_container_width=True,
            disabled=["key_drug", "example_drug_description", "total_quantity_packs", "net_income_gbp"],
            column_order=["example_drug_description", "total_quantity_packs", "net_income_gbp", "acquisition_cost_gbp"],
            num_rows="dynamic",
            key="data_editor"
        )

        edited_incomplete['acquisition_cost_gbp'] = pd.to_numeric(edited_incomplete['acquisition_cost_gbp'], errors='coerce').fillna(0.0)
        resolved_mask = edited_incomplete['acquisition_cost_gbp'] > 0.0
        
        if resolved_mask.any():
            resolved_rows = edited_incomplete[resolved_mask]
            for index, row in resolved_rows.iterrows():
                st.session_state.master_data.loc[index, 'acquisition_cost_gbp'] = row['acquisition_cost_gbp']
                new_margin = row['net_income_gbp'] - row['acquisition_cost_gbp']
                st.session_state.master_data.loc[index, 'margin_gbp'] = new_margin
            
            st.rerun()

    # 4. Process Final Data
    final_data = st.session_state.master_data[st.session_state.master_data['acquisition_cost_gbp'] > 0.0].copy()

    if not final_data.empty:
        gbp_cols = [col for col in final_data.columns if 'gbp' in col]
        final_data[gbp_cols] = final_data[gbp_cols].round(2)

        current_margin = final_data['margin_gbp'].sum()
        current_income = final_data['net_income_gbp'].sum()

        # Executive KPI Header
        REALISATION_FACTOR = 0.85
        MONTHS_IN_YEAR = 12

        monthly_opp = (
            final_data.get('potential_savings_gbp', pd.Series([0])).sum() +
            final_data.get('maverick_leakage_gbp', pd.Series([0])).sum() +
            final_data.get('concession_uplift_gbp', pd.Series([0])).sum()
        )
        
        annual_run_rate = monthly_opp * MONTHS_IN_YEAR
        realised_annual_projection = annual_run_rate * REALISATION_FACTOR

        st.subheader("Financial Impact Projection")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                label="Monthly Identified Opportunity",
                value=f"£{monthly_opp:,.2f}",
                help="The total theoretical saving identified in this specific data upload (Switches + Leakage + Concessions)."
            )

        with col2:
            st.metric(
                label="Projected Annualised Savings",
                value=f"£{realised_annual_projection:,.2f}",
                help=f"Calculated as (Monthly Saving x 12) at an {REALISATION_FACTOR*100:.0f}% implementation rate."
            )

        with col3:
            st.metric(
                label="Full Potential (100% Implementation)",
                value=f"£{annual_run_rate:,.2f}",
                delta=f"£{annual_run_rate - realised_annual_projection:,.2f} variance",
                delta_color="normal",
                help="The maximum possible annual saving if every single suggestion is implemented."
            )

        st.caption(f"**Note on Methodology:** Annual projections are based on a linear run-rate of the current month's data. An {REALISATION_FACTOR*100:.0f}% realisation factor has been applied to account for clinical nuances and patient preferences.")

        st.divider()

        # Historical Trend
        st.subheader("Margin Trajectory & Total Potential")
        
        current_opportunity = monthly_opp
        historical_df = fetch_mock_historical_data(current_margin, current_opportunity)
        
        fig_trend = px.area(
            historical_df, 
            x='Month', 
            y=['Realised Margin', 'Unrealised Opportunity'],
            markers=True,
            color_discrete_map={
                "Realised Margin": "#2ca02c", 
                "Unrealised Opportunity": "#ff7f0e" 
            }
        )
        
        fig_trend.update_traces(line_shape='spline')
        fig_trend.update_layout(
            height=280, 
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis_title="",
            yaxis_title="",
            legend_title_text="",
            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5),
            margin=dict(l=0, r=0, t=20, b=0)
        )
        fig_trend.update_yaxes(showgrid=True, gridcolor='rgba(0,0,0,0.05)', tickprefix="£")
        fig_trend.update_xaxes(showgrid=False)
        st.plotly_chart(fig_trend, use_container_width=True, config={'displayModeBar': False})

        st.divider()

        # Operational Action Board
        st.subheader("Operational Action Board")
        
        tab1, tab2, tab3, tab4 = st.tabs([
            "🚨 Critical Losses",
            "🔄 Clinical Switches", 
            "🛒 Procurement Waste",
            "🛡️ Price Concessions"
        ])
        
        with tab1:
            loss_makers = final_data[final_data['margin_gbp'] < 0].copy()
            if not loss_makers.empty:
                st.error(f"⚠️ {len(loss_makers)} product lines are currently dispensing at a net loss.")
                display_cols = ['example_drug_description', 'total_quantity_packs', 'net_income_gbp', 'acquisition_cost_gbp', 'margin_gbp']
                st.dataframe(
                    loss_makers[display_cols].sort_values('margin_gbp', ascending=True)
                    .style.background_gradient(subset=['margin_gbp'], cmap='Reds_r')
                    .format(precision=2),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "example_drug_description": "Product",
                        "total_quantity_packs": "Packs Dispensed",
                        "net_income_gbp": "NHS Reimbursed (£)",
                        "acquisition_cost_gbp": "Actual Spend (£)",
                        "margin_gbp": "Net Loss (£)"
                    }
                )
                st.caption("Investigate these lines immediately. Check for missing NHS Part VIIIA concessions, excessive wholesaler pricing, or generic alternatives.")
            else:
                st.success("No loss-making items detected in the current dispensing period.")

        with tab2:
            if 'potential_savings_gbp' in final_data.columns:
                switch_df = final_data[final_data['potential_savings_gbp'] > 0.0].copy()
                
                if not switch_df.empty:
                    st.write("**Financial Summary**")
                    summary_cols = ['example_drug_description', 'suggested_drug', 'switch_type', 'potential_savings_gbp']
                    st.dataframe(
                        switch_df[summary_cols].sort_values('potential_savings_gbp', ascending=False),
                        column_config={
                            "example_drug_description": "Current Drug",
                            "suggested_drug": "Alternative",
                            "switch_type": "Switch Type",
                            "potential_savings_gbp": st.column_config.NumberColumn("Est. Monthly Saving", format="£%.2f")
                        },
                        hide_index=True, use_container_width=True
                    )
                    
                    st.write("<br>**Clinical Evidence & Rationale**", unsafe_allow_html=True)
                    for index, row in switch_df.sort_values('potential_savings_gbp', ascending=False).iterrows():
                        current_drug = row['example_drug_description']
                        new_drug = row['suggested_drug']
                        
                        with st.expander(f"Review Switch: {current_drug} to {new_drug}"):
                            st.markdown(f"**Implementation:** {row.get('clinical_effort', 'Uncategorised')}")
                            st.markdown(f"**Clinical Justification:** {row.get('clinical_rationale', 'No rationale provided.')}")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                source = row.get('reference_source', 'Unknown')
                                st.markdown(f"**Evidence Source:** {source}")
                            with col2:
                                link = row.get('clinical_link', '')
                                if pd.notna(link) and link != '' and link != '#':
                                    st.markdown(f"**Reference:** [View Guidelines]({link})")
                                else:
                                    st.markdown("**Reference:** Local document (Offline)")
                                    
                            if mds_active and row.get('mds_warning', False):
                                st.warning("MDS Alert: Ensure this brand-to-generic switch does not negatively impact your primary manufacturer rebate thresholds before proceeding.")
                            
                            st.caption("*Clinical Governance Disclaimer: Switch opportunities are algorithmically generated. The prescribing clinician retains ultimate clinical responsibility for assessing patient suitability before initiating any therapeutic or generic switch.*")
                else:
                    st.success("No immediate switch opportunities identified.")
            else:
                st.info("Switch opportunity logic has not been processed.")

        with tab3:
            if 'maverick_leakage_gbp' in final_data.columns:
                maverick_df = final_data[final_data['maverick_leakage_gbp'] > 0].copy()
                
                if not maverick_df.empty:
                    display_cols = [
                        'example_drug_description', 'total_quantity_packs', 
                        'acquisition_cost_gbp', 'cheapest_supplier', 'maverick_leakage_gbp'
                    ]
                    st.dataframe(
                        maverick_df[display_cols].sort_values('maverick_leakage_gbp', ascending=False)
                        .style.background_gradient(subset=['maverick_leakage_gbp'], cmap='Oranges')
                        .format(precision=2),
                        use_container_width=True, hide_index=True,
                        column_config={
                            "example_drug_description": "Product",
                            "acquisition_cost_gbp": "Actual Spend (£)",
                            "cheapest_supplier": "Cheapest Supplier",
                            "maverick_leakage_gbp": "Waste (Maverick Buying) (£)"
                        }
                    )
                else:
                    st.success("No procurement leakage detected. Supplier pricing is consistent.")
            else:
                st.info("Maverick leakage logic has not been processed.")

        with tab4:
            if 'concession_uplift_gbp' in final_data.columns:
                concession_df = final_data[final_data['concession_uplift_gbp'] > 0].copy()
                
                if not concession_df.empty:
                    st.metric(
                        "Total Concession Uplift", 
                        f"£{concession_df['concession_uplift_gbp'].sum():,.2f}", 
                        help="Additional NHS reimbursement automatically secured via monthly price concessions."
                    )
                    
                    display_cols = [
                        'example_drug_description', 'total_quantity_packs', 
                        'acquisition_cost_gbp', 'margin_gbp', 'concession_uplift_gbp'
                    ]
                    
                    st.dataframe(
                        concession_df[display_cols].sort_values('concession_uplift_gbp', ascending=False)
                        .style.background_gradient(subset=['concession_uplift_gbp'], cmap='Blues')
                        .format(precision=2),
                        use_container_width=True, hide_index=True,
                        column_config={
                            "example_drug_description": "Product",
                            "acquisition_cost_gbp": "Actual Spend (£)",
                            "margin_gbp": "Final Margin (£)",
                            "concession_uplift_gbp": "Concession Value Reclaimed (£)"
                        }
                    )
                else:
                    st.info("No price concessions were identified or required in this dataset.")
            else:
                st.info("Price concession logic has not been processed.")

else:
    st.write("---")
    st.info("👋 Welcome. Please upload the practice dispensing and invoice files to generate your margin report.")