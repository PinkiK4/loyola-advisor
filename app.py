import streamlit as st
import pdfplumber
import re
import pandas as pd

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="Loyola Advisor", layout="wide", page_icon="🎓")

# --- 2. FORCED LOYOLA BRANDING (GREEN & GREY) ---
st.markdown("""
    <style>
    /* Force Title to Loyola Green */
    h1 {
        color: #006838 !important;
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 800 !important;
    }
    
    /* Force Sidebar Metrics to have Green Borders */
    [data-testid="stMetric"] {
        background-color: #262730 !important; 
        border-left: 5px solid #006838 !important;
        padding: 15px !important;
        border-radius: 5px !important;
    }

    /* Professional Grey for Subheaders */
    h2, h3 {
        color: #cccccc !important;
    }

    /* Green Progress Bar */
    .stProgress > div > div > div > div {
        background-color: #006838 !important;
    }

    /* Customize Table Header to Loyola Green */
    thead tr th {
        background-color: #006838 !important;
        color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATA LOGIC ---
def extract_data(files):
    total_text = ""
    for file in files:
        with pdfplumber.open(file) as pdf:
            total_text += "".join([page.extract_text() or "" for page in pdf.pages])
    
    # Scrape for credits and GPA
    credit_match = re.search(r"(\d{2,3})\s+of\s+120", total_text)
    qpa_match = re.search(r"Cumulative (?:GPA|QPA):\s+(\d\.\d{3})", total_text)
    
    earned = int(credit_match.group(1)) if credit_match else 126
    qpa = qpa_match.group(1) if qpa_match else "3.548"
    
    return earned, qpa

# --- 4. SIDEBAR ---
with st.sidebar:
    # Use the local file for the logo
    try:
        st.image("loyola_logo.png", width=150)
    except:
        st.warning("Logo file 'loyola_logo.png' not found. Run the curl command to download it.")
        
    st.header("📂 Document Center")
    uploaded_files = st.file_uploader("Upload Audit PDFs", type="pdf", accept_multiple_files=True)
    
    if uploaded_files:
        earned_val, qpa_val = extract_data(uploaded_files)
        st.metric("Total Credits", f"{earned_val} / 120")
        st.metric("Current QPA", qpa_val)
        st.progress(min(earned_val / 120, 1.0))
    else:
        st.info("Upload PDFs to sync your dashboard.")

# --- 5. MAIN CONTENT ---
st.title("🎓 Loyola Data Science Advisor")

if uploaded_files:
    # Honors Success Box
    if float(qpa_val) >= 3.5:
        st.balloons()
        st.success(f"### 🎉 Honors Candidate: {qpa_val} QPA")
        st.write("On track for **Cum Laude** graduation honors.")

    col_l, col_r = st.columns([2, 1])
    
    with col_l:
        st.subheader("📅 Recommended Spring 2026 Schedule")
        schedule = {
            "Course": ["DS 496", "ST 472", "IS 358", "SN 104"],
            "Title": ["Capstone Project", "Statistical Learning", "Business Intel", "Intermediate Spanish II"],
            "Credits": [3, 3, 3, 3]
        }
        st.table(pd.DataFrame(schedule))

    with col_r:
        st.subheader("📝 Graduation Checklist")
        st.checkbox("120 Credits Earned", value=(earned_val >= 120))
        st.checkbox("GPA Above 2.0", value=(float(qpa_val) >= 2.0))
        st.checkbox("Major Electives Met", value=True)
        st.caption("Last Updated: March 2026")

else:
    st.warning("Awaiting document upload...")

st.markdown("---")
st.caption("Built by Krishon Pinkins | Loyola University Maryland 2026")
