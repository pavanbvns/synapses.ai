# frontend/components/job_result.py

import streamlit as st
import json


def render_job_result_panel():
    result = st.session_state.get("last_job_result")
    if not result:
        st.info("No result available.")
        return

    st.markdown("### Job Result")
    st.markdown(f"**Job ID:** `{result.get('job_id')}`")

    if "summary" in result:
        st.subheader("Generated Summary")
        st.markdown(result["summary"], unsafe_allow_html=True)
    elif "qa_pairs" in result:
        st.subheader("Q&A Pairs")
        for pair in result["qa_pairs"]:
            st.markdown(f"- **Q:** {pair['question']}  \n  **A:** {pair['answer']}")
    elif "obligations" in result:
        st.subheader("Obligations")
        obligations = json.loads(result["obligations"])
        for item in obligations:
            for k, v in item.items():
                st.markdown(f"- **{k}**: {v}")
            st.markdown("---")
    elif "risks" in result:
        st.subheader("Risks")
        risks = json.loads(result["risks"])
        for item in risks:
            for k, v in item.items():
                st.markdown(f"- **{k}**: {v}")
            st.markdown("---")
    elif "ingested_count" in result:
        st.subheader("Ingestion Result")
        st.success(f"Documents Ingested: {result['ingested_count']}")
        st.json(result.get("details"))
    elif "response" in result:
        st.subheader("Chat Response")
        st.markdown(result["response"])

    if st.button("Back to Home"):
        st.session_state.pop("last_job_result", None)
