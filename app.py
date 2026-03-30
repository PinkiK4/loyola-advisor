import streamlit as st
import pdfplumber
import re
import pandas as pd

# --- PAGE CONFIG ---
st.set_page_config(page_title="Loyola Advisor", layout="wide", page_icon="🎓")

# --- CUSTOM CSS: BACKGROUND IMAGE, GREEN TEXT, WIDE LAYOUT ---
st.markdown("""
    <style>
    /* 1. Add Background Image */
    .stApp {
        background-image: url("https://images.pexels.com/photos/1438072/pexels-photo-1438072.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }
    /* 2. Overlays to make text readable on the background */
    .stApp > div {
        background-color: rgba(0, 0, 0, 0.75); /* Dark overlay */
        padding: 2rem;
        border-radius: 10px;
    }
    
    /* 3. Force Loyola Green Title */
    h1 {
        color: #006838 !important;
        font-weight: 800 !important;
        background: transparent !important;
    }
    
    /* 4. Branded Metrics in Sidebar */
    [data-testid="stMetric"] {
        background-color: #1e1e1e !important; 
        border-left: 5px solid #006838 !important;
    }

    /* 5. Wide Table Styling */
    thead tr th {
        background-color: #006838 !important;
        color: white !important;
    }
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

# --- SIDEBAR ---
with st.sidebar:
    st.image("loyola_logo.png", width=150) # Loads local file
    st.header("📂 Document Center")
    uploaded_files = st.file_uploader("Upload Audit PDFs", type="pdf", accept_multiple_files=True)
    
    if uploaded_files:
        earned_val, qpa_val = extract_data(uploaded_files)
        st.metric("Total Credits", f"{earned_val} / 120")
        st.metric("Current QPA", qpa_val)
        st.progress(min(earned_val / 120, 1.0))
    else:
        st.info("Upload PDFs to sync dashboard.")

# --- MAIN UI ---
st.title("🎓 Loyola Data Science Advisor")

if uploaded_files:
    if float(qpa_val) >= 3.5:
        st.balloons()
        st.success(f"### 🎉 Honors Candidate: {qpa_val} QPA")
        
    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📅 Recommended Spring 2026 Schedule")
        schedule = {
            "Course": ["DS 496", "ST 472", "IS 358", "SN 104"],
            "Title": ["Capstone Project", "Statistical Learning", "Business Intel", "Intermediate Spanish II"],
            "Credits": [3, 3, 3, 3]
        }
        st.dataframe(pd.DataFrame(schedule), use_container_width=True, hide_index=True)

    with col2:
        st.subheader("📝 Checklist")
        st.checkbox("120 Credits", value=(earned_val >= 120))
        st.checkbox("GPA > 2.0", value=(float(qpa_val) >= 2.0))
        st.checkbox("SN 104 (Language Core)", value=False)
else:
    st.warning("Awaiting document upload...")

st.markdown("---")
st.caption("Built by Krishon Pinkins | Loyola University Maryland 2026")
