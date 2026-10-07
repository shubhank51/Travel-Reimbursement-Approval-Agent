import json

import pandas as pd
import streamlit as st

from travel_reimbursement_agent import CLAIMS, evaluate_claim, run_demo


st.set_page_config(page_title="Travel Reimbursement Agent", page_icon="✈️", layout="wide")
st.title("Travel Reimbursement Approval Agent")
st.caption("Policy-grounded GenAI workflow for travel claim evaluation")

if "results" not in st.session_state:
    st.session_state.results = run_demo()

with st.sidebar:
    st.header("Controls")
    st.write("This prototype uses deterministic policy guardrails and an optional OpenAI planner when configured.")
    if st.button("Re-run demo claims"):
        st.session_state.results = run_demo()

results_df = pd.DataFrame(st.session_state.results)

col1, col2, col3 = st.columns(3)
col1.metric("Claims", len(results_df))
col2.metric("Approved", round(float(results_df["approved_amount"].sum()), 2))
col3.metric("Deducted", round(float(results_df["deducted_amount"].sum()), 2))

st.subheader("Decision summary")
summary = results_df["decision"].value_counts().rename_axis("decision").reset_index(name="count")
st.bar_chart(summary.set_index("decision")["count"])

st.subheader("Audit table")
st.dataframe(results_df[["claim_id", "decision", "approved_amount", "deducted_amount", "missing_docs", "policy_refs", "confidence", "tools_used", "explanation"]], use_container_width=True)

st.subheader("Claim viewer")
selected = st.selectbox("Choose a claim", [c["claim_id"] for c in CLAIMS])
for claim in CLAIMS:
    if claim["claim_id"] == selected:
        st.json(claim)
        break

st.subheader("Structured JSON output")
st.code(json.dumps(st.session_state.results, indent=2), language="json")
