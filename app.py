import streamlit as st
import pdfplumber
import re
import pandas as pd
import os
import base64
from fpdf import FPDF

# --- PAGE CONFIG ---
st.set_page_config(page_title="Loyola AI Advisor", layout="wide", page_icon="🎓")

def get_base64(bin_file):
    with open(bin_file, 'rb') as f:
        return base64.b64encode(f.read()).decode()

def set_style(img_file):
    bin_str = get_base64(img_file) if os.path.exists(img_file) else ""
    st.markdown(f'''
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{bin_str}");
            background-size: cover; background-position: center; background-attachment: fixed;
        }}
        .stApp > div {{
            background-color: rgba(10, 10, 10, 0.88) !important;
            backdrop-filter: blur(12px); padding: 2rem; border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.15);
        }}
        h1 {{ color: #006838 !important; font-weight: 800 !important; }}
        
        /* THE GREEN LINE: Sidebar Divider */
        [data-testid="stSidebar"] {{
            background-color: rgba(15, 15, 15, 0.98) !important;
            border-right: 4px solid #006838 !important;
            min-width: 350px !important;
        }}

        [data-testid="stMetric"] {{ 
            background-color: rgba(255, 255, 255, 0.07) !important; 
            border-left: 6px solid #006838 !important; border-radius: 10px !important;
        }}
        .footer {{ position: fixed; left: 0; bottom: 8px; width: 100%; text-align: center; color: white; font-size: 13px; z-index: 1000; }}
        </style>
        ''', unsafe_allow_html=True)

set_style("Background.jpeg")

# --- DATA EXTRACTION ---
def extract_all(audit_file, transcript_file):
    text = ""
    if audit_file:
        with pdfplumber.open(audit_file) as pdf:
            text += "".join([p.extract_text() or "" for p in pdf.pages])
    if transcript_file:
        with pdfplumber.open(transcript_file) as pdf:
            text += "".join([p.extract_text() or "" for p in pdf.pages])
    
    name = re.search(r"Name:\s+([A-Za-z\s,]+)", text)
    sid = re.search(r"ID:\s+(\d+)", text)
    major = re.search(r"Major:\s+([A-Za-z\s]+)", text)
    advisor = re.search(r"Advisor:\s+([A-Za-z\s,]+)", text)
    credits = re.search(r"(\d{2,3})\s+of\s+120", text)
    qpa = re.search(r"Cumulative (?:GPA|QPA):\s+(\d\.\d{3})", text)
    
    return {
        "name": name.group(1).strip() if name else "Krishon Pinkins",
        "sid": sid.group(1) if sid else "0000000",
        "major": major.group(1).strip() if major else "Data Science",
        "advisor": advisor.group(1).strip() if advisor else "Search Transcript...",
        "earned": int(credits.group(1)) if credits else 126,
        "qpa": qpa.group(1) if qpa else "3.548"
    }

# --- SIDEBAR: ORGANIZED WITH GREEN DIVIDER ---
with st.sidebar:
    st.header("📂 Document Center")
    
    st.markdown("### 1. Degree Audit")
    a_file = st.file_uploader("Upload Audit PDF", type="pdf", key="audit_v3")
    
    st.markdown("### 2. Official Transcript")
    t_file = st.file_uploader("Upload Transcript PDF", type="pdf", key="transcript_v3")
    
    st.markdown("---")
    
    st.markdown("### 📝 Instructions")
    st.info("**Audit:** Scans for degree progress.\n\n**Transcript:** Scans for ID, Advisor, and GPA.")
    
    data = extract_all(a_file, t_file)
    
    if a_file or t_file:
        st.metric("Total Credits", f"{data['earned']} / 120")
        st.metric("Current QPA", data['qpa'])
    
    if os.path.exists("LoyolaSeal.png"):
        st.image("LoyolaSeal.png", use_container_width=True)

# --- MAIN UI ---
st.title(f"🎓 Loyola AI {data['major']} Advisor")

if a_file or t_file:
    st.success(f"**Syncing Profile:** {data['name']} | **ID:** {data['sid']} | **Advisor:** {data['advisor']}")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📅 Recommended Schedule")
        df = pd.DataFrame({
            "Course ID": ["DS 496", "ST 472", "IS 358", "SN 104"],
            "Course Name": ["Capstone Project", "Statistical Learning", "Business Intelligence", "Intermediate Spanish II"],
            "Credits": [3, 3, 3, 3]
        })
        st.table(df)
        
    with col2:
        st.subheader("📝 Summary")
        st.write(f"**GPA:** {data['qpa']}")
        st.progress(min(data['earned'] / 120, 1.0), text="Progress to Degree")
else:
    st.warning("Upload documents in the sidebar to activate advisor logic.")

st.markdown('<div class="footer">Built by Krishon Pinkins | Loyola University Maryland 2026</div>', unsafe_allow_html=True)
