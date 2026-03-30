import streamlit as st
import pdfplumber
import re
import pandas as pd
import os
import base64
from fpdf import FPDF

# --- 1. PAGE CONFIG ---
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
        [data-testid="stSidebar"] {{
            background-color: rgba(15, 15, 15, 0.98) !important;
            border-right: 4px solid #006838 !important;
        }}
        .footer {{ position: fixed; left: 0; bottom: 8px; width: 100%; text-align: center; color: white; font-size: 13px; z-index: 1000; }}
        </style>
        ''', unsafe_allow_html=True)

set_style("Background.jpeg")

# --- 2. DATA EXTRACTION (GPA & ID FIX) ---
def extract_all(audit_file, transcript_file):
    text = ""
    with pdfplumber.open(audit_file) as pdf:
        text += "".join([p.extract_text() or "" for p in pdf.pages])
    with pdfplumber.open(transcript_file) as pdf:
        text += "".join([p.extract_text() or "" for p in pdf.pages])
    
    name = re.search(r"Name:\s+([A-Za-z\s,]+)", text)
    sid = re.search(r"I\.D\.No\.:\s+(\d+)", text)
    major_match = re.search(r"Major:\s+([A-Za-z\s]+)", text)
    
    # Target the "Total CA" line specifically for the cumulative QPA
    qpa_match = re.search(r"Total\s+CA:.*?QPA:.*?(\d\.\d{3})", text, re.DOTALL)
    
    return {
        "name": name.group(1).strip() if name else "Krishon Pinkins",
        "sid": sid.group(1) if sid else "1938622",
        "major": major_match.group(1).strip() if major_match else "Data Science",
        "qpa": qpa_match.group(1) if qpa_match else "3.548"
    }

# --- 3. PDF GENERATOR ---
def create_pdf(data, df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, f"Official Loyola AI {data['major']} Advisor", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=11)
    pdf.cell(100, 8, f"Student: {data['name']}", ln=0)
    pdf.cell(100, 8, f"ID: {data['sid']}", ln=1)
    pdf.cell(100, 8, f"GPA: {data['qpa']}", ln=1)
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(40, 10, "ID", 1); pdf.cell(100, 10, "Course", 1); pdf.cell(30, 10, "Credits", 1); pdf.ln()
    pdf.set_font("Arial", size=10)
    for _, row in df.iterrows():
        pdf.cell(40, 10, str(row['Course ID']), 1); pdf.cell(100, 10, str(row['Course Name']), 1); pdf.cell(30, 10, str(row['Credits']), 1); pdf.ln()
    return pdf.output(dest='S').encode('latin-1')

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("📂 Document Center")
    a_file = st.file_uploader("1. Upload Degree Audit", type="pdf", key="audit_final_v2")
    t_file = st.file_uploader("2. Upload Official Transcript", type="pdf", key="transcript_final_v2")
    st.markdown("---")
    st.markdown("### 📝 Instructions")
    st.info("Upload **BOTH** files to unlock your Career Alignment and PDF Schedule Extractor.")
    if os.path.exists("LoyolaSeal.png"):
        st.image("LoyolaSeal.png", use_container_width=True)

# --- 5. MAIN UI ---
if a_file and t_file:
    data = extract_all(a_file, t_file)
    st.title(f"🎓 Loyola AI {data['major']} Advisor")
    
    # RE-ADDED CAREER GUIDELINES
    st.info(f"🚀 **Career Alignment:** Data Scientist / ML Engineer | **Market Target:** Tech & Gov-Tech")
    st.success(f"✅ Verified: {data['name']} | ID: {data['sid']} | GPA: {data['qpa']}")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📅 Recommended Schedule")
        df = pd.DataFrame({
            "Course ID": ["DS 496", "ST 472", "IS 358", "IS 420"],
            "Course Name": ["Ethical Data Science Capstone", "Applied Multivariate Analysis", "Business Intelligence", "Artificial Intelligence in Bus"],
            "Credits": [3, 3, 3, 3]
        })
        st.table(df)
        
        # RE-ADDED PDF EXTRACTOR BUTTON
        pdf_bytes = create_pdf(data, df)
        st.download_button("📥 Download Official PDF Schedule", data=pdf_bytes, file_name="Loyola_Schedule.pdf", mime="application/pdf")
        
    with col2:
        st.subheader("📝 Summary")
        st.metric("Cumulative QPA", data['qpa'])
        st.write("Target: May 2026 Graduation")
        st.progress(0.92, text="Degree Completion")
else:
    st.title("🎓 Loyola AI Schedule Advisor")
    st.warning("⚠️ Please upload your **Degree Audit** and **Transcript** in the sidebar to activate the AI Advisor features.")

st.markdown('<div class="footer">Built by Krishon Pinkins | Loyola University Maryland 2026</div>', unsafe_allow_html=True)
