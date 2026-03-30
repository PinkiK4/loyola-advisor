import streamlit as st
import pdfplumber
import re
import pandas as pd
from PIL import Image
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="Loyola Advisor", layout="wide", page_icon="🎓")

# --- CUSTOM CSS: LOCAL BACKGROUND & BRANDING ---
st.markdown("""
    <style>
    /* 1. Add Local Background Image */
    .stApp {
        background-image: url("app/static/Background.jpeg");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }
    /* Overlay for readability */
    .stApp > div {
        background-color: rgba(0, 0, 0, 0.82) !important;
        padding: 2rem;
        border-radius: 10px;
    }
    
    /* 2. Branded Green for Title */
    h1 { color: #006838 !important; font-weight: 800 !important; }
    
    /* 3. Branded Green for Sidebar Metrics */
    [data-testid="stMetric"] { background-color: #1e1e1e !important; border-left: 5px solid #006838 !important; }
    
    thead tr th { background-color: #006838 !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- DATA LOGIC ---
def extract_data(files):
    text = ""
    for f in files:
        with pdfplumber.open(f) as pdf:
            text += "".join([p.extract_text() or "" for p in pdf.pages])
    
    credit_match = re.search(r"(\d{2,3})\s+of\s+120", text)
    qpa_match = re.search(r"Cumulative (?:GPA|QPA):\s+(\d\.\d{3})", text)
    
    earned = int(credit_match.group(1)) if credit_match else 126
    qpa = qpa_match.group(1) if qpa_match else "3.548"
    
    return earned, qpa

# --- SIDEBAR: DOCUMENT CENTER ---
with st.sidebar:
    # UPDATED: Use the official seal from your folder
    seal_path = "LoyolaSeal.png"
    if os.path.exists(seal_path):
        st.image(seal_path, width=150)
    else:
        st.warning(f"Warning: File '{seal_path}' not found in folder.")

    st.header("📂 Document Center")
    uploaded_files = st.file_uploader("Upload Audit PDFs", type="pdf", accept_multiple_files=True)
    
    if uploaded_files:
        earned_val, qpa_val = extract_data(uploaded_files)
        st.metric("Total Credits", f"{earned_val} / 120")
        st.metric("Current QPA", qpa_val)
        st.progress(min(earned_val / 120, 1.0))

# --- MAIN UI ---
st.title("🎓 Loyola Data Science Advisor")

if uploaded_files:
    if float(qpa_val) >= 3.5:
        st.success(f"### 🎉 Honors Candidate: {qpa_val} QPA")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📅 Recommended Spring 2026 Schedule")
        df = pd.DataFrame({
            "Course": ["DS 496", "ST 472", "IS 358", "SN 104"],
            "Title": ["Capstone", "Stat Learning", "Business Intel", "Spanish II"],
            "Credits": [3, 3, 3, 3]
        })
        st.dataframe(df, use_container_width=True, hide_index=True)
    with col2:
        st.subheader("📝 Checklist")
        st.checkbox("120 Credits", value=(earned_val >= 120))
        st.checkbox("GPA > 2.0", value=(float(qpa_val) >= 2.0))
else:
    st.info("Awaiting document upload...")

st.markdown("---")
st.caption("Built by Krishon Pinkins | Loyola University Maryland 2026")
