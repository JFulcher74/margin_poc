import streamlit as st
import pandas as pd
import plotly.express as px
import random
from src.normalise import normalise_dispensing, normalise_invoices, normalise_tariff
from src.match import match_records
from src.calc import calculate_metrics

def fetch_mock_historical_data(current_margin, current_opportunity):
    history = []
    history.append({'Month': 'Feb 2026', 'Realised Margin': current_margin * random.uniform(0.85, 0.95), 'Unrealised Opportunity': current_opportunity * random.uniform(1.2, 1.4)})
    history.append({'Month': 'Mar 2026', 'Realised Margin': current_margin * random.uniform(0.90, 1.00), 'Unrealised Opportunity': current_opportunity * random.uniform(1.1, 1.25)})
    history.append({'Month': 'Apr 2026', 'Realised Margin': current_margin, 'Unrealised Opportunity': current_opportunity})
    return pd.DataFrame(history)

st.set_page_config(page_title="MarginGuard AI | Practice Analytics", layout="wide", page_icon="🏦")
st.markdown("<style>.metric-container { background-color: #f0f2f6; padding: 1.5rem; border-radius: 0.5rem; } .stDataFrame [data-testid='stTable'] td:nth-child(n+3) { text-align: right; }</style>", unsafe_allow_html=True)

st.title("🏦 MarginGuard AI")
st.caption("Commercial Intelligence for Dispensing GP Practices")

def reset_data():
    if 'master_data' in st.session_state:
        del st.session_state['master_data']

with st.sidebar:
    st.header("Input Data")
    disp_file = st.file_uploader("Monthly Dispensing Export", type="csv", on_change=reset_data)
    inv_file = st.file_uploader("Supplier Invoice Export", type="csv", on_change=reset_data)
    
    rebate_dict = {}
    if inv_file:
        inv_file.seek(0)
        inv_df_preview = pd.read_csv(inv_file)
        inv_file.seek(0)
        
        supp_col = next((col for col in inv_df_preview.columns if col.lower() in ['supplier', 'wholesaler', 'supplier_name', 'vendor']), None)
        
        st.divider()
        st.subheader("Wholesaler Rebates (%)")
        if supp_col:
            suppliers = sorted([str(s) for s in inv_df_preview[supp_col].dropna().unique() if str(s).strip()])
            for s in suppliers:
                rebate_dict[s] = st.number_input(f"{s} Rebate (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.5, on_change=reset_data)
        else:
            rebate_dict['ALL'] = st.number_input("Standard Rebate (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.5, on_change=reset_data)

    st.divider()
    st.write("Current Tariff: **April 2026**")
    
    st.divider()
    st.subheader("Financial Settings")
    mds_active = st.toggle("MDS / Rebate Schemes Active", value=False)
    manual_override = st.toggle("Override PPA Claim Value", value=False, help="Use this if uploading partial month data to prevent inaccurate clawback scaling.")
    
    if manual_override:
        override_price = st.number_input("Expected Full Month Claim (£)", value=25000.0, step=1000.0, on_change=reset_data)
    else:
        override_price = None

    if st.button("Reset Dashboard"):
        st.session_state.clear()
        st.rerun()

if disp_file and inv_file:
    if 'master_data' not in st.session_state:
        with st.spinner("Calculating NHS Reimbursement & Leakage..."):
            disp_df = pd.read_csv(disp_file, dtype={'dm_d_code': str})
            inv_df = pd.read_csv(inv_file, dtype={'dm_d_code': str})
            tariff_raw = pd.read_csv("Part VIIIA April 2026.csv", dtype=str)
            if 'VMPP Snomed Code' not in tariff_raw.columns:
                tariff_raw = pd.read_csv("Part VIIIA April 2026.csv", skiprows=2, dtype=str)
            dnd_df = pd.read_csv("dnd_mock.csv", dtype={'dm_d_code': str})

            matched = match_records(normalise_dispensing(disp_df), normalise_invoices(inv_df))
            st.session_state.master_data = calculate_metrics(matched, normalise_tariff(tariff_raw), dnd_df, override_price, rebate_dict)

    df = st.session_state.master_data.copy()
    
    applied_price = df['applied_basic_price'].iloc[0] if not df.empty else 0.0
    applied_rate = df['applied_clawback_rate'].iloc[0] if not df.empty else 0.1118
    applied_fee = df['applied_dispensing_fee'].iloc[0] if not df.empty else 2.11
    
    st.sidebar.divider()
    st.sidebar.metric("Basic Price (PPA Claim)", f"£{applied_price:,.2f}")
    st.sidebar.metric("Applied NHS Clawback", f"{applied_rate * 100:.2f}%")
    st.sidebar.metric("Applied Dispensing Fee", f"£{applied_fee:.2f}")
    
    incomplete_mask = (df['acquisition_cost_gbp'] == 0.0) | (df['acquisition_cost_gbp'].isna())
    incomplete_data = df[incomplete_mask].copy()
    st.divider()

    if not incomplete_data.empty:
        st.subheader("⚠️ Action Required: Missing Invoice Data")
        st.write("The following lines lack an acquisition cost. Please enter the missing costs below to instantly update your P&L.")
        edited_incomplete = st.data_editor(
            incomplete_data, use_container_width=True,
            disabled=["key_drug", "example_drug_description", "total_quantity_packs", "net_income_gbp"],
            column_order=["example_drug_description", "total_quantity_packs", "net_income_gbp", "acquisition_cost_gbp"],
            num_rows="dynamic", key="data_editor"
        )
        edited_incomplete['acquisition_cost_gbp'] = pd.to_numeric(edited_incomplete['acquisition_cost_gbp'], errors='coerce').fillna(0.0)
        resolved_mask = edited_incomplete['acquisition_cost_gbp'] > 0.0
        
        if resolved_mask.any():
            resolved_rows = edited_incomplete[resolved_mask]
            for index, row in resolved_rows.iterrows():
                st.session_state.master_data.loc[index, 'acquisition_cost_gbp'] = row['acquisition_cost_gbp']
                st.session_state.master_data.loc[index, 'margin_gbp'] = row['net_income_gbp'] - row['acquisition_cost_gbp']
            st.rerun()

    final_data = st.session_state.master_data[st.session_state.master_data['acquisition_cost_gbp'] > 0.0].copy()

    if not final_data.empty:
        gbp_cols = [col for col in final_data.columns if 'gbp' in col]
        final_data[gbp_cols] = final_data[gbp_cols].round(2)

        current_margin = final_data['margin_gbp'].sum()
        REALISATION_FACTOR = 0.85
        monthly_opp = final_data.get('potential_savings_gbp', pd.Series([0])).sum() + final_data.get('maverick_leakage_gbp', pd.Series([0])).sum() + final_data.get('concession_uplift_gbp', pd.Series([0])).sum()
        annual_run_rate = monthly_opp * 12
        realised_annual_projection = annual_run_rate * REALISATION_FACTOR

        st.subheader("Financial Impact Projection")
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("Monthly Identified Opportunity", f"£{monthly_opp:,.2f}")
        with col2: st.metric("Projected Annualised Savings", f"£{realised_annual_projection:,.2f}")
        with col3: st.metric("Full Potential (100% Implementation)", f"£{annual_run_rate:,.2f}")
        with col4: st.metric("Retrospective Rebate Value", f"£{final_data.get('wholesaler_rebate_gbp', pd.Series([0])).sum():,.2f}")
        
        st.caption(f"**Note on Methodology:** Annual projections are based on a linear run-rate of the current month's data. An {REALISATION_FACTOR*100:.0f}% realisation factor has been applied.")
        st.divider()

        st.subheader("Margin Trajectory & Total Potential")
        historical_df = fetch_mock_historical_data(current_margin, monthly_opp)
        fig_trend = px.area(historical_df, x='Month', y=['Realised Margin', 'Unrealised Opportunity'], markers=True, color_discrete_map={"Realised Margin": "#2ca02c", "Unrealised Opportunity": "#ff7f0e"})
        fig_trend.update_traces(line_shape='spline')
        fig_trend.update_layout(height=280, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis_title="", yaxis_title="", legend_title_text="", legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5), margin=dict(l=0, r=0, t=20, b=0))
        fig_trend.update_yaxes(showgrid=True, gridcolor='rgba(0,0,0,0.05)', tickprefix="£")
        fig_trend.update_xaxes(showgrid=False)
        st.plotly_chart(fig_trend, use_container_width=True, config={'displayModeBar': False})
        st.divider()

        st.subheader("Operational Action Board")
        tab1, tab2, tab3, tab4 = st.tabs(["🚨 Critical Losses", "🔄 Clinical Switches", "🛒 Procurement Waste", "🛡️ Price Concessions"])
        
        with tab1:
            loss_makers = final_data[final_data['margin_gbp'] < 0].copy()
            if not loss_makers.empty:
                st.error(f"⚠️ {len(loss_makers)} product lines are currently dispensing at a net loss.")
                st.dataframe(loss_makers[['example_drug_description', 'total_quantity_packs', 'net_income_gbp', 'acquisition_cost_gbp', 'net_acquisition_cost_gbp', 'margin_gbp']].sort_values('margin_gbp', ascending=True).style.background_gradient(subset=['margin_gbp'], cmap='Reds_r').format(precision=2), use_container_width=True, hide_index=True)
            else: st.success("No loss-making items detected.")

        with tab2:
            if 'potential_savings_gbp' in final_data.columns and not final_data[final_data['potential_savings_gbp'] > 0.0].empty:
                switch_df = final_data[final_data['potential_savings_gbp'] > 0.0].copy()
                st.dataframe(switch_df[['example_drug_description', 'suggested_drug', 'switch_type', 'potential_savings_gbp']].sort_values('potential_savings_gbp', ascending=False), hide_index=True, use_container_width=True)
                for index, row in switch_df.sort_values('potential_savings_gbp', ascending=False).iterrows():
                    with st.expander(f"Review Switch: {row['example_drug_description']} to {row['suggested_drug']}"):
                        st.markdown(f"**Implementation:** {row.get('clinical_effort', 'Uncategorised')}")
                        st.markdown(f"**Clinical Justification:** {row.get('clinical_rationale', 'No rationale provided.')}")
                        if mds_active and row.get('mds_warning', False): st.warning("MDS Alert: Ensure this switch does not impact rebate thresholds.")
            else: st.success("No immediate switch opportunities identified.")

        with tab3:
            if 'maverick_leakage_gbp' in final_data.columns and not final_data[final_data['maverick_leakage_gbp'] > 0].empty:
                st.dataframe(final_data[final_data['maverick_leakage_gbp'] > 0][['example_drug_description', 'total_quantity_packs', 'acquisition_cost_gbp', 'cheapest_supplier', 'maverick_leakage_gbp']].sort_values('maverick_leakage_gbp', ascending=False).style.background_gradient(subset=['maverick_leakage_gbp'], cmap='Oranges').format(precision=2), use_container_width=True, hide_index=True)
            else: st.success("No procurement leakage detected.")

        with tab4:
            if 'concession_uplift_gbp' in final_data.columns and not final_data[final_data['concession_uplift_gbp'] > 0].empty:
                st.metric("Total Concession Uplift", f"£{final_data['concession_uplift_gbp'].sum():,.2f}")
                st.dataframe(final_data[final_data['concession_uplift_gbp'] > 0][['example_drug_description', 'total_quantity_packs', 'acquisition_cost_gbp', 'margin_gbp', 'concession_uplift_gbp']].sort_values('concession_uplift_gbp', ascending=False).style.background_gradient(subset=['concession_uplift_gbp'], cmap='Blues').format(precision=2), use_container_width=True, hide_index=True)
            else: st.info("No price concessions identified.")
else:
    st.write("---")
    st.info("👋 Welcome. Please upload the practice dispensing and invoice files to generate your margin report.")