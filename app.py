import streamlit as st
import pdfplumber
import re
import pandas as pd
import os
import base64
from fpdf import FPDF

# --- 1. PAGE CONFIG & THEME ---
st.set_page_config(page_title="AI Schedule Advisor | Loyola 2026", layout="wide", page_icon="🎓")

def get_base64(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    return ""

def set_style(img_file):
    bin_str = get_base64(img_file)
    st.markdown(f'''
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{bin_str}");
            background-size: cover; background-position: center; background-attachment: fixed;
        }}
        .stApp > div {{
            background-color: rgba(10, 10, 10, 0.92) !important;
            backdrop-filter: blur(12px); padding: 2rem; border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.15);
        }}
        h1 {{ color: #006838 !important; font-weight: 800 !important; }}
        [data-testid="stSidebar"] {{
            background-color: rgba(15, 15, 15, 0.98) !important;
            border-right: 4px solid #006838 !important;
        }}
        .congrats-card {{
            background: linear-gradient(135deg, #006838 0%, #1a1a1a 100%);
            padding: 3rem; border-radius: 20px; text-align: center; border: 2px solid gold;
        }}
        .footer {{ position: fixed; left: 0; bottom: 8px; width: 100%; text-align: center; color: white; font-size: 13px; z-index: 1000; }}
        </style>
        ''', unsafe_allow_html=True)

set_style("Background.jpeg")

# --- 2. ENGINES ---
def create_pdf(data, schedule_df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, f"AI Automated Scheduling: {data['major']}", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=11)
    pdf.cell(100, 8, f"Student: {data['name']} | ID: {data['sid']}", ln=1)
    pdf.cell(100, 8, f"Cumulative GPA: {data['qpa']}", ln=1)
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(40, 10, "ID", 1); pdf.cell(100, 10, "Course", 1); pdf.cell(30, 10, "Credits", 1); pdf.ln()
    pdf.set_font("Arial", size=10)
    for _, row in schedule_df.iterrows():
        pdf.cell(40, 10, str(row['Course ID']), 1); pdf.cell(100, 10, str(row['Course Name']), 1); pdf.cell(30, 10, str(row['Credits']), 1); pdf.ln()
    return pdf.output(dest='S').encode('latin-1')

# --- 3. DYNAMIC ANALYSIS ENGINE ---
def analyze_data(audit_file, transcript_file):
    a_text, t_text = "", ""
    with pdfplumber.open(audit_file) as pdf:
        a_text = "".join([p.extract_text() or "" for p in pdf.pages])
    with pdfplumber.open(transcript_file) as pdf:
        t_text = "".join([p.extract_text() or "" for p in pdf.pages])
    
    # Basic Info
    name_m = re.search(r"Name:\s+([A-Za-z\s,]+)", t_text)
    sid_m = re.search(r"I\.D\.No\.:\s+(\d+)", t_text)
    major_m = re.search(r"Major:\s+([A-Za-z\s]+)", t_text)
    qpa_m = re.search(r"QPA:\s+(\d\.\d{3})", t_text)
    
    # Credit Calculation: Earned (CE) + In-Progress (CIP)
    ce_match = re.search(r"Total\s+CE:\s+(\d+\.\d+)", t_text)
    earned = float(ce_match.group(1)) if ce_match else 0.0
    cip_pattern = re.findall(r"(\d\.\d{2})\s+CIP", t_text)
    projected_total = earned + sum(float(v) for v in cip_pattern)

    # Filtering Logic
    taken_codes = set(re.findall(r"([A-Z]{2}\s\d{3})", t_text))
    # Add courses that the audit marks as 'Fulfilled' even if not yet on transcript
    fulfilled_regex = re.findall(r"Fulfilled\s+([A-Z]{2}\*?\d{3})", a_text)
    for f in fulfilled_regex: taken_codes.add(f.replace("*", " "))

    audit_matches = re.findall(r"Not Started\s+([A-Z]{2}\*?\d{3})\s+([A-Za-z\s&]+)", a_text)
    
    recs = []
    seen = set()
    for raw_code, raw_title in audit_matches:
        code = raw_code.replace("*", " ").strip()
        if code not in taken_codes and code not in seen:
            recs.append({"Course ID": code, "Course Name": raw_title.strip()[:35], "Credits": 3.0})
            seen.add(code)
            
    major_name = major_m.group(1).strip() if major_m else "Data Science"
    career = f"{major_name} | Market: Tech, AI & Analytics" if "DATA" in major_name.upper() else f"{major_name}"
            
    return {
        "name": name_m.group(1).strip() if name_m else "Krishon Pinkins",
        "sid": sid_m.group(1) if sid_m else "1938622",
        "major": major_name,
        "career": career,
        "qpa": qpa_m.group(1) if qpa_m else "3.461",
        "total": projected_total,
        "is_cip": len(cip_pattern) > 0,
        "recs": pd.DataFrame(recs)
    }

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("📂 Document Center")
    a_f = st.file_uploader("1. Upload Degree Audit", type="pdf")
    t_f = st.file_uploader("2. Upload Official Transcript", type="pdf")
    st.divider()
    if os.path.exists("LoyolaSeal.png"): st.image("LoyolaSeal.png", use_container_width=True)

# --- 5. MAIN UI ---
if a_f and t_f:
    data = analyze_data(a_f, t_f)
    
    if data['recs'].empty and data['total'] >= 120:
        st.markdown(f'''<div class="congrats-card"><h1 style="color: gold !important;">🎉 DEGREE COMPLETE 🎉</h1>
        <h2 style="color: white;">{data['name']}</h2><p style="color: #ddd;">BS in {data['major']} Requirements Concluded.</p>
        <h3 style="color: #00ff88;">Final Projected QPA: {data['qpa']}</h3></div>''', unsafe_allow_html=True)
        st.balloons()
    else:
        st.title("AI Schedule Advisor")
        st.markdown(f'''
            <div style="background-color: #162a3d; padding: 12px; border-radius: 5px; border-left: 5px solid #3498db; margin-bottom: 10px;">
                🚀 <b>Career Alignment:</b> {data['career']}
            </div>
            <div style="background-color: #1b3d2c; padding: 12px; border-radius: 5px; border-left: 5px solid #28a745; margin-bottom: 25px;">
                ✅ <b>Verified:</b> {data['name']} | ID: {data['sid']} | GPA: {data['qpa']}
            </div>
            ''', unsafe_allow_html=True)
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("📅 Recommended Next Steps")
            if not data['recs'].empty:
                st.table(data['recs'])
                pdf_bytes = create_pdf(data, data['recs'])
                st.download_button("📥 Download Official Advice", data=pdf_bytes, file_name="Loyola_Advice.pdf")
        with c2:
            st.subheader("📝 Graduation Summary")
            st.metric("Projected Total Credits", f"{data['total']} / 120")
            st.write(f"**CIP Status:** {'Active Enrollment' if data['is_cip'] else 'None'}")
            st.progress(min(data['total']/120, 1.0))
else:
    st.title("🎓 Loyola AI Schedule Advisor")
    st.warning("⚠️ Awaiting File Upload in Document Center.")

st.markdown(f'<div class="footer">Built by {data["name"] if "data" in locals() else "Krishon Pinkins"} | Loyola University Maryland 2026</div>', unsafe_allow_html=True)
