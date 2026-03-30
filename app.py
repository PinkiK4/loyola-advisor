import streamlit as st
import pdfplumber
import re
import pandas as pd
import os
import base64

# --- PAGE CONFIG ---
st.set_page_config(page_title="Loyola Advisor", layout="wide", page_icon="🎓")

# --- CUSTOM CSS: SEAL OVERLAY & GLASSMORPHISM ---
def get_base64(bin_file):
    with open(bin_file, 'rb') as f:
        return base64.b64encode(f.read()).decode()

def set_style(img_file):
    bin_str = get_base64(img_file) if os.path.exists(img_file) else ""
    st.markdown(f'''
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{bin_str}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        .stApp > div {{
            background-color: rgba(10, 10, 10, 0.85) !important;
            backdrop-filter: blur(8px);
            padding: 2rem;
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        [data-testid="stSidebar"] {{
            background-color: rgba(15, 15, 15, 0.98) !important;
            border-right: 3px solid #006838 !important;
            z-index: 100; /* Keeps sidebar below the seal overlay */
        }}
        h1 {{ color: #006838 !important; font-weight: 800 !important; }}
        [data-testid="stMetric"] {{ 
            background-color: rgba(255, 255, 255, 0.07) !important; 
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            border-left: 6px solid #006838 !important; 
            border-radius: 10px !important;
        }}
        .footer {{
            position: fixed;
            left: 0;
            bottom: 8px;
            width: 100%;
            text-align: center;
            color: #ffffff;
            font-size: 13px;
            font-weight: 500;
            z-index: 1000;
        }}
        /* THE CRITICAL FIX: Higher Z-Index and Right-Offset */
        .bottom-left-seal {{
            position: fixed;
            left: 350px; /* Moves it out from behind the sidebar */
            bottom: 30px;
            z-index: 999999 !important; /* Forces it to the very top */
            filter: drop-shadow(0px 6px 12px rgba(0,0,0,0.9));
            pointer-events: none;
        }}
        </style>
        ''', unsafe_allow_html=True)

set_style("Background.jpeg")

# --- DATA LOGIC ---
def extract_data(files):
    text = ""
    for f in files:
        with pdfplumber.open(f) as pdf:
            text += "".join([p.extract_text() or "" for p in pdf.pages])
    c = re.search(r"(\d{2,3})\s+of\s+120", text)
    q = re.search(r"Cumulative (?:GPA|QPA):\s+(\d\.\d{3})", text)
    return (int(c.group(1)) if c else 126, q.group(1) if q else "3.548")

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Document Center")
    uploaded_files = st.file_uploader("Upload Audit PDFs", type="pdf", accept_multiple_files=True)
    if uploaded_files:
        earned_val, qpa_val = extract_data(uploaded_files)
        st.metric("Total Credits", f"{earned_val} / 120")
        st.metric("Current QPA", qpa_val)
        st.progress(min(earned_val / 120, 1.0))
    st.markdown("---")
    st.caption("Instructions: Drag and drop your Loyola Degree Audit to update your metrics.")

# --- MAIN UI ---
st.title("🎓 Loyola Data Science Advisor")
if uploaded_files:
    if float(qpa_val) >= 3.5:
        st.success(f"### 🎉 Honors Candidate: {qpa_val} QPA")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📅 Recommended Spring 2026 Schedule")
        df = pd.DataFrame({"Course": ["DS 496", "ST 472", "IS 358", "SN 104"], "Credits": [3, 3, 3, 3]})
        st.table(df)
    with col2:
        st.subheader("📝 Checklist")
        st.checkbox("120 Credits", value=(earned_val >= 120))
        st.checkbox("GPA > 2.0", value=(float(qpa_val) >= 2.0))
else:
    st.info("Awaiting document upload to sync your profile.")

# --- SEAL & FOOTER OVERLAYS ---
if os.path.exists("LoyolaSeal.png"):
    seal_base64 = get_base64("LoyolaSeal.png")
    st.markdown(f'<div class="bottom-left-seal"><img src="data:image/png;base64,{seal_base64}" width="150"></div>', unsafe_allow_html=True)

st.markdown('<div class="footer">Built by Krishon Pinkins | Loyola University Maryland 2026</div>', unsafe_allow_html=True)
