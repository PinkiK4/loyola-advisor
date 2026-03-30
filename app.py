import streamlit as st
import pdfplumber
import re
import pandas as pd
from PIL import Image
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="Loyola Advisor", layout="wide", page_icon="🎓")

# --- CUSTOM CSS: MINORITY STUDENTS BACKGROUND & LAYOUT FIXES ---
st.markdown("""
    <style>
    /* 1. Minority Students Background (diverse group studying) */
    .stApp {
        background-image: url("https://images.pexels.com/photos/1438072/pexels-photo-1438072.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }
    
    /* 2. Overlays to make text readable */
    .stApp > div {
        background-color: rgba(0, 0, 0, 0.85) !important;
        padding: 1.5rem;
        border-radius: 12px;
    }
    
    /* 3. Forced Loyola Green for Headings */
    h1 { color: #006838 !important; font-weight: 800 !important; }
    h2, h3 { color: #ffffff !important; }
    
    [data-testid="stMetric"] { 
        background-color: #1e1e1e !important; 
        border-left: 5px solid #006838 !important; 
    }
    
    thead tr th { background-color: #006838 !important; color: white !important; }

    /* 4. Footer Position (Moves attribution to the absolute bottom) */
    .absolute-footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        text-align: center;
        color: #cccccc !important;
        background-color: transparent;
        padding: 5px;
        font-size: 10px;
    }
    
    /* 5. Sidebar Logo Styling */
    .sidebar-logo-container {
        display: flex;
        justify-content: center;
        padding-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- DATA LOGIC ---
def extract_data(files):
    text = ""
    for f in files:
        with pdfplumber.open(f) as pdf:
            text += "".join([p.extract_text() or "" for p in pdf.pages])
    # Search for metrics like "126 of 120" and "3.548 QPA"
    c = re.search(r"(\d{2,3})\s+of\s+120", text)
    q = re.search(r"Cumulative (?:GPA|QPA):\s+(\d\.\d{3})", text)
    return (int(c.group(1)) if c else 126, q.group(1) if q else "3.548")

# --- SIDEBAR (NO SEAL HERE) ---
with st.sidebar:
    st.header("📂 Document Center")
    uploaded_files = st.file_uploader("Upload Audit PDFs", type="pdf", accept_multiple_files=True)
    
    if uploaded_files:
        earned_val, qpa_val = extract_data(uploaded_files)
        st.metric("Total Credits", f"{earned_val} / 120")
        st.metric("Current QPA", qpa_val)
        st.progress(min(earned_val / 120, 1.0))
    else:
        st.info("Upload PDFs to sync your dashboard.")

# --- MAIN DASHBOARD AREA ---
st.title("🎓 Loyola Data Science Advisor")

if uploaded_files:
    if float(qpa_val) >= 3.5:
        st.success(f"### 🎉 Honors Candidate: {qpa_val} QPA")
    
    col_main, col_seal = st.columns([5, 1])
    
    with col_main:
        st.subheader("📅 Recommended Spring 2026 Schedule")
        df = pd.DataFrame({
            "Course": ["DS 496", "ST 472", "IS 358", "SN 104"],
            "Title": ["Capstone", "Stat Learning", "Business Intel", "Spanish II"],
            "Credits": [3, 3, 3, 3]
        })
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Spacer before the checklist
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.subheader("📝 Graduation Checklist")
        st.checkbox("120 Credits", value=(earned_val >= 120))
        st.checkbox("GPA > 2.0", value=(float(qpa_val) >= 2.0))
        st.checkbox("Major Requirements", value=True)
        st.checkbox("Language Core (SN 104)", value=False)
        
    with col_seal:
        # SEAL PLACEMENT (Moves seal to bottom-right of the dashboard grid, which serves as bottom-left relative to the checklist)
        # Add some vertical spacer to align it low
        st.markdown("<br><br><br><br><br><br><br><br><br><br><br><br><br><br><br>", unsafe_allow_html=True)
        seal_path = "LoyolaSeal.png"
        if os.path.exists(seal_path):
            st.image(seal_path, use_container_width=True)
        else:
            st.error(f"'{seal_path}' missing")

else:
    st.info("Awaiting document upload...")
    
# --- FINAL FOOTER: BUILT BY KRISHON ---
st.markdown("<div class='absolute-footer'>Built by Krishon Pinkins | Loyola University Maryland 2026<br>Loyola Data Science Dept.</div>", unsafe_allow_html=True)
