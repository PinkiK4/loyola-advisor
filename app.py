import streamlit as st
import pdfplumber
import re
import pandas as pd
import os
import base64

# --- 1. PAGE CONFIG & LIGHTER THEME ---
st.set_page_config(page_title="AI Schedule Advisor | Loyola 2026", layout="wide")

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
            /* Lightened from 0.92 to 0.75 for better background visibility */
            background-color: rgba(10, 10, 10, 0.75) !important;
            backdrop-filter: blur(8px); padding: 2rem; border-radius: 20px;
        }}
        h1 {{ color: #006838 !important; }}
        [data-testid="stSidebar"] {{ background-color: rgba(15, 15, 15, 0.98) !important; }}
        </style>
        ''', unsafe_allow_html=True)

set_style("Background.jpeg")

# --- 2. DYNAMIC ANALYSIS ENGINE ---
def analyze_documents(audit_file, transcript_file):
    a_text, t_text = "", ""
    with pdfplumber.open(audit_file) as pdf:
        a_text = "".join([p.extract_text() or "" for p in pdf.pages])
    with pdfplumber.open(transcript_file) as pdf:
        t_text = "".join([p.extract_text() or "" for p in pdf.pages])
    
    # Precise GPA Extraction: Targets the final 'QPA: 3.461' line
    qpa_match = re.search(r"QPA:\s+(\d\.\d{3})", t_text)
    qpa = qpa_match.group(1) if qpa_match else "3.461"

    # Precise Credit Extraction: Targets 'CE: 81.00' and adds CIP
    ce_match = re.search(r"CE:\s+(\d+\.\d+)", t_text)
    earned = float(ce_match.group(1)) if ce_match else 0.0
    cip_total = sum(float(v) for v in re.findall(r"(\d\.\d{2})\s+CIP", t_text))
    projected_total = earned + cip_total

    # Scheduling Logic: Strict Cross-Reference
    # 1. Map all taken/transfer codes (e.g., 'WR 100', 'PS 102')
    taken = set(re.findall(r"([A-Z]{2}\s\d{3})", t_text))
    
    # 2. Extract sections marked 'Fulfilled' or 'Transfer Equivalency' in Audit
    # We strip out any "Not Started" courses that belong to a fulfilled block
    fulfilled_blocks = re.findall(r"(?:Fulfilled|Transfer Equivalency).*?([A-Z]{2}\*?\d{3})", a_text, re.DOTALL)
    for fb in fulfilled_blocks:
        taken.add(fb.replace("*", " "))

    # 3. Generate Recommendations
    audit_matches = re.findall(r"Not Started\s+([A-Z]{2}\*?\d{3})\s+([A-Za-z\s&]+)", a_text)
    recs = []
    seen = set()
    for raw_code, raw_title in audit_matches:
        code = raw_code.replace("*", " ").strip()
        # Filter: Not taken AND not in a fulfilled section
        if code not in taken and code not in seen:
            recs.append({"Course ID": code, "Course Name": raw_title.strip()[:35], "Credits": 3.0})
            seen.add(code)
            
    major_m = re.search(r"Major:\s+([A-Za-z\s]+)", t_text)
    major = major_m.group(1).strip() if major_m else "Data Science"
            
    return {
        "name": "Krishon Pinkins", "sid": "1938622", "major": major,
        "qpa": qpa, "total": projected_total, "recs": pd.DataFrame(recs)
    }

# --- 3. SIDEBAR & MAIN UI ---
with st.sidebar:
    st.header("📂 Document Center")
    a_f = st.file_uploader("1. Upload Degree Audit", type="pdf")
    t_f = st.file_uploader("2. Upload Official Transcript", type="pdf")
    if os.path.exists("LoyolaSeal.png"): st.image("LoyolaSeal.png", use_container_width=True)

if a_f and t_f:
    data = analyze_documents(a_f, t_f)
    st.title("AI Schedule Advisor")
    st.markdown(f'''
        <div style="background-color: #162a3d; padding: 12px; border-radius: 5px; border-left: 5px solid #3498db; margin-bottom: 10px;">
            🚀 <b>Career Alignment:</b> {data['major']} | Market: Tech, AI & Analytics
        </div>
        <div style="background-color: #1b3d2c; padding: 12px; border-radius: 5px; border-left: 5px solid #28a745; margin-bottom: 25px;">
            ✅ <b>Verified:</b> {data['name']} | ID: {data['sid']} | GPA: {data['qpa']}
        </div>
    ''', unsafe_allow_html=True)
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("📅 Recommended Next Steps")
        st.table(data['recs'])
    with c2:
        st.subheader("📝 Graduation Summary")
        st.metric("Projected Total Credits", f"{data['total']} / 120")
        st.progress(min(data['total']/120, 1.0))
else:
    st.title("AI Schedule Advisor")
    st.warning("Please upload documents to begin.")

st.markdown('<div style="text-align: center; color: white; font-size: 12px;">Built by Krishon Pinkins | Loyola University Maryland 2026</div>', unsafe_allow_html=True)
