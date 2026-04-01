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
            backdrop-filter: blur(15px); padding: 2rem; border-radius: 25px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        h1 {{ color: #006838 !important; font-weight: 800 !important; }}
        [data-testid="stSidebar"] {{
            background-color: rgba(15, 15, 15, 0.98) !important;
            border-right: 5px solid #006838 !important;
        }}
        .footer {{ position: fixed; left: 0; bottom: 8px; width: 100%; text-align: center; color: #888; font-size: 12px; }}
        </style>
        ''', unsafe_allow_html=True)

set_style("Background.jpeg")

# --- 2. DYNAMIC CAREER LOGIC ---
def generate_career_alignment(major_name):
    """Generates market targeting based on detected major keywords."""
    m = major_name.upper()
    if "DATA" in m or "STAT" in m:
        return f"{major_name} | Market: Tech, AI & Analytics"
    elif "COMP" in m:
        return f"{major_name} | Market: Software & Systems Engineering"
    elif "BUS" in m or "ECON" in m:
        return f"{major_name} | Market: Corporate Finance & Strategy"
    return f"{major_name} | Market: Specialized Professional Services"

# --- 3. DYNAMIC ANALYSIS ENGINE ---
def analyze_documents(audit_file, transcript_file):
    a_text, t_text = "", ""
    with pdfplumber.open(audit_file) as pdf:
        a_text = "".join([p.extract_text() or "" for p in pdf.pages])
    with pdfplumber.open(transcript_file) as pdf:
        t_text = "".join([p.extract_text() or "" for p in pdf.pages])
    
    # Extract Student Info from Transcript
    name_m = re.search(r"Name:\s+([A-Za-z\s,]+)", t_text)
    sid_m = re.search(r"I\.D\.No\.:\s+(\d+)", t_text)
    major_m = re.search(r"Major:\s+([A-Za-z\s]+)", t_text)
    qpa_m = re.search(r"QPA:\s+(\d\.\d{3})", t_text)
    
    # Dynamic Credit Calculation
    ce_match = re.search(r"Total\s+CE:\s+(\d+\.\d+)", t_text)
    current_ce = float(ce_match.group(1)) if ce_match else 0.0
    cip_pattern = re.findall(r"(\d\.\d{2})\s+CIP", t_text)
    cip_total = sum(float(val) for val in cip_pattern)
    projected_total = current_ce + cip_total

    # Dynamic Scheduling Logic
    taken_codes = set(re.findall(r"([A-Z]{2}\s\d{3})", t_text))
    # Filter Audit for "Not Started" or "In-Progress" requirements
    audit_matches = re.findall(r"(Not Started|In-Progress)\s+([A-Z]{2}\*?\s?\d{3})\s+([A-Za-z\s&]+)", a_text)
    
    recs = []
    seen = set()
    for status, raw_code, raw_title in audit_matches:
        code = raw_code.replace("*", " ").strip()
        # Skip if already on transcript (handles transfers like WR 100)
        if code not in taken_codes and code not in seen:
            recs.append({
                "Course ID": code,
                "Course Name": raw_title.strip()[:40],
                "Credits": 3.0
            })
            seen.add(code)
            
    detected_major = major_m.group(1).strip() if major_m else "General Studies"
            
    return {
        "name": name_m.group(1).strip() if name_m else "Student",
        "sid": sid_m.group(1) if sid_m else "1938622",
        "major": detected_major,
        "career": generate_career_alignment(detected_major),
        "qpa": qpa_m.group(1) if qpa_m else "0.000",
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
    st.info("Verification Engine: Compares Audit requirements against Transcript history to filter completed courses.")

# --- 5. MAIN UI ---
st.title("AI Schedule Advisor")

if a_f and t_f:
    data = analyze_documents(a_f, t_f)
    
    # Career Alignment Banner (Dynamic)
    st.markdown(f'''
        <div style="background-color: #162a3d; padding: 15px; border-radius: 8px; border-left: 5px solid #3498db; margin-bottom: 10px;">
            🚀 <b>Career Alignment:</b> {data['career']}
        </div>
        <div style="background-color: #1b3d2c; padding: 15px; border-radius: 8px; border-left: 5px solid #28a745; margin-bottom: 25px;">
            ✅ <b>Verified:</b> {data['name']} | ID: {data['sid']} | GPA: {data['qpa']}
        </div>
        ''', unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📅 Recommended Next Steps")
        if not data['recs'].empty:
            st.table(data['recs'])
        else:
            st.success("All audit requirements found on transcript. Ready for graduation review!")

    with col2:
        st.subheader("📝 Graduation Summary")
        st.metric("Projected Total Credits", f"{data['total']} / 120")
        st.write(f"**CIP Status:** {'Active Enrollment' if data['is_cip'] else 'No Current Courses'}")
        st.progress(min(data['total']/120, 1.0))
else:
    st.warning("⚠️ Please upload your **Degree Audit** and **Transcript** in the Document Center to begin analysis.")

st.markdown('<div class="footer">Built by Krishon Pinkins | Loyola University Maryland 2026</div>', unsafe_allow_html=True)
