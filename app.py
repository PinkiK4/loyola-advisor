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
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        h1 {{ color: #006838 !important; font-weight: 800 !important; }}
        .footer {{ position: fixed; left: 0; bottom: 8px; width: 100%; text-align: center; color: white; font-size: 13px; z-index: 1000; }}
        </style>
        ''', unsafe_allow_html=True)

set_style("Background.jpeg")

# --- CAREER ENGINE BY MAJOR ---
def get_career_alignment(major, qpa):
    q = float(qpa)
    if "Engineering" in major:
        if q >= 3.5: return "Systems Engineer / Project Manager", "Lockheed Martin, Northrop Grumman"
        return "Field Engineer / Technical Sales", "Manufacturing & Infrastructure"
    elif "Data Science" in major:
        if q >= 3.5: return "Data Analyst / Consultant", "Big 4 Accounting or Gov-Tech"
        return "Business Intelligence Specialist", "FinTech & Marketing"
    else:
        return "Academic Advisor / General Consultant", "Higher Education or Non-Profit"

# --- PDF GENERATOR ---
def create_pdf(name, student_id, major, df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "Loyola AI Schedule Advice", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, f"Student Name: {name}", ln=True)
    pdf.cell(200, 10, f"ID Number: {student_id}", ln=True)
    pdf.cell(200, 10, f"Major: {major}", ln=True)
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(40, 10, "Course ID", 1)
    pdf.cell(100, 10, "Course Name", 1)
    pdf.cell(30, 10, "Credits", 1)
    pdf.ln()
    
    pdf.set_font("Arial", size=12)
    for i, row in df.iterrows():
        pdf.cell(40, 10, str(row['Course ID']), 1)
        pdf.cell(100, 10, str(row['Course Name']), 1)
        pdf.cell(30, 10, str(row['Credits']), 1)
        pdf.ln()
    
    return pdf.output(dest='S').encode('latin-1')

# --- DATA EXTRACTION ---
def extract_data(files):
    text = ""
    for f in files:
        with pdfplumber.open(f) as pdf:
            text += "".join([p.extract_text() or "" for p in pdf.pages])
    
    # Advanced Regex for ID and Name
    name = re.search(r"Name:\s+([A-Za-z\s,]+)", text)
    sid = re.search(r"ID:\s+(\d+)", text)
    major = re.search(r"Major:\s+([A-Za-z\s]+)", text)
    credits = re.search(r"(\d{2,3})\s+of\s+120", text)
    qpa = re.search(r"Cumulative (?:GPA|QPA):\s+(\d\.\d{3})", text)
    
    return {
        "name": name.group(1).strip() if name else "Krishon Pinkins",
        "sid": sid.group(1) if sid else "0000000",
        "major": major.group(1).strip() if major else "Data Science",
        "earned": int(credits.group(1)) if credits else 126,
        "qpa": qpa.group(1) if qpa else "3.548"
    }

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Document Center")
    uploaded_files = st.file_uploader("Upload Audit PDFs", type="pdf", accept_multiple_files=True)
    
    data = {"name": "", "sid": "", "major": "", "earned": 0, "qpa": "0.000"}
    if uploaded_files:
        data = extract_data(uploaded_files)
        st.metric("Total Credits", f"{data['earned']} / 120")
        st.metric("Current QPA", data['qpa'])
    
    if os.path.exists("LoyolaSeal.png"):
        st.image("LoyolaSeal.png", use_container_width=True)

# --- MAIN UI ---
st.title(f"🎓 Loyola AI {data['major']} Advisor")

if uploaded_files:
    role, target = get_career_alignment(data['major'], data['qpa'])
    st.info(f"🚀 **Career Alignment:** {role} | **Target Markets:** {target}")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📅 Recommended Schedule")
        # Sample logic for course mapping
        df = pd.DataFrame({
            "Course ID": ["DS 496", "ST 472", "IS 358", "SN 104"],
            "Course Name": ["Capstone Project", "Statistical Learning", "Business Intelligence", "Intermediate Spanish II"],
            "Credits": [3, 3, 3, 3]
        })
        st.table(df)
        
        pdf_data = create_pdf(data['name'], data['sid'], data['major'], df)
        st.download_button(label="📥 Download Official PDF Schedule", data=pdf_data, file_name="Loyola_Schedule.pdf", mime="application/pdf")

    with col2:
        st.subheader("📝 Graduation Goals")
        st.checkbox("120 Credits", value=(data['earned'] >= 120))
        st.checkbox("Honors Status", value=(float(data['qpa']) >= 3.5))
        st.progress(min(data['earned'] / 120, 1.0))

st.markdown('<div class="footer">Built by Krishon Pinkins | Loyola University Maryland 2026</div>', unsafe_allow_html=True)
