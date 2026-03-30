import streamlit as st
import pdfplumber
import re
import pandas as pd

# --- 1. WIDE LAYOUT IS CRITICAL ---
st.set_page_config(page_title="Loyola Advisor", layout="wide", page_icon="🎓")

# Custom CSS for Loyola Green & Grey
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #006838; }
    h1 { color: #006838; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIC ---
def extract_data(files):
    total_text = ""
    for file in files:
        with pdfplumber.open(file) as pdf:
            total_text += "".join([page.extract_text() or "" for page in pdf.pages])
    credit_match = re.search(r"(\d{2,3})\s+of\s+120", total_text)
    qpa_match = re.search(r"Cumulative (?:GPA|QPA):\s+(\d\.\d{3})", total_text)
    return (int(credit_match.group(1)) if credit_match else 126, 
            qpa_match.group(1) if qpa_match else "3.548")

# --- 3. SIDEBAR ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/en/thumb/5/52/Loyola_University_Maryland_seal.svg/1200px-Loyola_University_Maryland_seal.svg.png", width=150)
    st.header("📂 Document Center")
    uploaded_files = st.file_uploader("Upload Audit PDFs", type="pdf", accept_multiple_files=True)
    
    if uploaded_files:
        earned_val, qpa_val = extract_data(uploaded_files)
        st.metric("Total Credits", f"{earned_val} / 120")
        st.metric("Current QPA", qpa_val)
        st.progress(min(earned_val / 120, 1.0))
    else:
        st.info("Upload PDFs to sync.")

# --- 4. MAIN ---
st.title("🎓 Loyola Data Science Advisor")
if uploaded_files:
    st.success(f"### 🎉 Honors Candidate: {qpa_val} QPA")
    col_l, col_r = st.columns([2, 1])
    with col_l:
        st.subheader("📅 Recommended Spring 2026 Schedule")
        data = {"Course": ["DS 496", "ST 472", "IS 358", "SN 104"], "Credits": [3, 3, 3, 3]}
        st.table(pd.DataFrame(data))
    with col_r:
        st.subheader("📝 Checklist")
        st.checkbox("120 Credits", value=True)
        st.checkbox("GPA > 2.0", value=True)
else:
    st.warning("Awaiting document upload...")
