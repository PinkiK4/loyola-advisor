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
        [data-testid="stMetric"] {{ 
            background-color: rgba(255, 255, 255, 0.07) !important; 
            border-left: 6px solid #006838 !important; border-radius: 10px !important;
        }}
        .footer {{ position: fixed; left: 0; bottom: 8px; width: 100%; text-align: center; color: white; font-size: 13px; z-index: 1000; }}
        </style>
        ''', unsafe_allow_html=True)

set_style("Background.jpeg")

# --- 2. UNIVERSAL CAREER ENGINE (DYNAMIC BY MAJOR) ---
def get_career_alignment(major, qpa):
    q = float(qpa)
    # Logic switches based on keywords found in the "Major" field of the PDF
    if "Engineering" in major:
        return ("Systems/Project Engineer", "Aerospace & Defense") if q >= 3.5 else ("Operations Engineer", "Industrial Tech")
    elif "Business" in major or "Marketing" in major:
        return ("Management Consultant", "Global Finance") if q >= 3.5 else ("Account Manager", "Corporate Services")
    elif "Science" in major or "Data" in major:
        return ("Research Lead / Data Scientist", "Tech & Innovation") if q >= 3.5 else ("Technical Analyst", "Regional Hubs")
    else:
        # Fallback for any other major (History, Arts, etc.)
        return ("Professional Consultant", "Specialized Industries") if q >= 3.5 else ("Associate Coordinator", "Public Sector")

# --- 3. PDF GENERATOR ---
def create_pdf(data, df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, f"Official Loyola AI {data['major']} Advice", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=11)
    pdf.cell(100, 8, f"Name: {data['name']}", ln=0); pdf.cell(100, 8, f"ID: {data['sid']}", ln=1)
    pdf.cell(100, 8, f"Major: {data['major']}", ln=0); pdf.cell(100, 8, f"Cumulative GPA: {data['qpa']}", ln=1)
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(40, 10, "Course ID", 1); pdf.cell(100, 10, "Course Name", 1); pdf.cell(30, 10, "Credits", 1); pdf.ln()
    pdf.set_font("Arial", size=10)
    for _, row in df.iterrows():
        pdf.cell(40, 10, str(row['Course ID']), 1); pdf.cell(100, 10, str(row['Course Name']), 1); pdf.cell(30, 10, str(row['Credits']), 1); pdf.ln()
    return pdf.output(dest='S').encode('latin-1')

# --- 4. UNIVERSAL DATA EXTRACTION ---
def extract_all(audit_file, transcript_file):
    text = ""
    if audit_file:
        with pdfplumber.open(audit_file) as pdf:
            text += "".join([p.extract_text() or "" for p in pdf.pages])
    if transcript_file:
        with pdfplumber.open(transcript_file) as pdf:
            text += "".join([p.extract_text() or "" for p in pdf.pages])
    
    # Generic scrapers that look for keywords regardless of the major
    name = re.search(r"Name:\s+([A-Za-z\s,]+)", text)
    sid = re.search(r"ID(?:\.No\.)?:\s+(\d+)", text)
    major_match = re.search(r"Major:\s+([A-Za-z\s]+)", text)
    credits = re.search(r"Total\s+CA:\s+\d+\.\d\s+CE:\s+(\d+\.\d+)", text)
    qpa = re.search(r"(?:Cumulative\s+)?QPA:\s+(\d\.\d{3})", text)
    
    return {
        "name": name.group(1).strip() if name else "Student Name",
        "sid": sid.group(1) if sid else "0000000",
        "major": major_match.group(1).strip() if major_match else "Selected Major",
        "earned": float(credits.group(1)) if credits else 0.0,
        "qpa": qpa.group(1) if qpa else "0.000"
    }

# --- 5. SIDEBAR ---
with st.sidebar:
    st.header("📂 Document Center")
    a_file = st.file_uploader("1. Upload Degree Audit", type="pdf", key="audit_univ")
    t_file = st.file_uploader("2. Upload Official Transcript", type="pdf", key="transcript_univ")
    st.markdown("---")
    st.markdown("### 📝 Instructions")
    st.info("Upload your **Loyola Degree Audit** and **Transcript** to automatically detect your major and sync your career path.")
    
    data = extract_all(a_file, t_file)
    
    if a_file or t_file:
        st.metric("Earned Credits", f"{data['earned']} / 120")
        st.metric("Cumulative QPA", data['qpa'])
    
    if os.path.exists("LoyolaSeal.png"):
        st.image("LoyolaSeal.png", use_container_width=True)

# --- 6. MAIN UI ---
st.title(f"🎓 Loyola AI {data['major']} Advisor")

if a_file or t_file:
    role, market = get_career_alignment(data['major'], data['qpa'])
    st.info(f"🚀 **Career Alignment:** {role} | **Market Target:** {market}")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📅 Recommended Schedule")
        # In a real app, this would be a lookup table based on 'data["major"]'
        st.write(f"Displaying core requirements for **{data['major']}**.")
        df = pd.DataFrame({
            "Course ID": ["CORE 101", "MAJ 200", "MAJ 300", "ELEC 400"],
            "Course Name": ["Foundational Seminar", "Intermediate Requirement", "Advanced Theory", "Capstone/Elective"],
            "Credits": [3, 3, 3, 3]
        })
        st.table(df)
        
        pdf_bytes = create_pdf(data, df)
        st.download_button("📥 Download Official PDF Schedule", data=pdf_bytes, file_name=f"Loyola_{data['major']}_Advisor.pdf", mime="application/pdf")

    with col2:
        st.subheader("📝 Summary")
        st.write(f"**Student:** {data['name']} ({data['sid']})")
        st.progress(min(data['earned'] / 120, 1.0), text="Degree Completion")
else:
    st.warning("Awaiting document upload to identify major and sync profile.")

st.markdown('<div class="footer">Built by Krishon Pinkins | Loyola University Maryland 2026</div>', unsafe_allow_html=True)
