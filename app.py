import streamlit as st
import pdfplumber
import re
import pandas as pd
import os
import base64
from io import BytesIO

# --- 1. PAGE CONFIG & THEME TOGGLE ---
# Streamlit handles light/dark mode automatically via user settings, 
# but we can force high-contrast "Glassmorphism" for both.
st.set_page_config(page_title="Loyola AI Pro", layout="wide", page_icon="🎓")

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
        [data-testid="stMetric"] {{ 
            background-color: rgba(255, 255, 255, 0.05) !important; 
            border-left: 6px solid #006838 !important; border-radius: 10px !important;
        }}
        .footer {{ position: fixed; left: 0; bottom: 8px; width: 100%; text-align: center; color: white; font-size: 13px; z-index: 1000; }}
        </style>
        ''', unsafe_allow_html=True)

set_style("Background.jpeg")

# --- 2. ADVANCED LOGIC: RECOMMENDATIONS & CAREERS ---
def get_recommendations(credits):
    """Simple Engine: Suggests courses based on credit progress."""
    if credits < 60: return ["CS 151", "MA 251", "ST 210"]
    if credits < 90: return ["DS 301", "ST 310", "CS 312"]
    return ["DS 496 (Capstone)", "ST 472 (Machine Learning)", "IS 358 (BI)"]

def map_career(qpa):
    """Career Mapping: High QPA in DS courses triggers specific paths."""
    q = float(qpa)
    if q >= 3.8: return "Data Scientist / ML Engineer", "Top-tier Research or FAANG"
    if q >= 3.5: return "Data Analyst / Consultant", "Big 4 Accounting or Gov-Tech"
    return "Business Intelligence Analyst", "Regional Tech Hubs"

# --- 3. DATA EXTRACTION ---
def extract_data(files):
    text = ""
    for f in files:
        with pdfplumber.open(f) as pdf:
            text += "".join([p.extract_text() or "" for p in pdf.pages])
    c = re.search(r"(\d{2,3})\s+of\s+120", text)
    q = re.search(r"Cumulative (?:GPA|QPA):\s+(\d\.\d{3})", text)
    return (int(c.group(1)) if c else 126, q.group(1) if q else "3.548")

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("📂 Document Center")
    uploaded_files = st.file_uploader("Upload Audit PDFs", type="pdf", accept_multiple_files=True)
    
    earned_val, qpa_val = 0, "0.000"
    if uploaded_files:
        earned_val, qpa_val = extract_data(uploaded_files)
        st.metric("Total Credits", f"{earned_val} / 120")
        st.metric("Current QPA", qpa_val)
    
    st.markdown("---")
    # WHAT-IF CALCULATOR
    st.subheader("🔮 What-If QPA")
    target_grade = st.slider("Target Grade this Semester", 0.0, 4.0, 3.5)
    projected = (float(qpa_val) + target_grade) / 2 if float(qpa_val) > 0 else target_grade
    st.write(f"Projected QPA: **{projected:.3f}**")
    
    if os.path.exists("LoyolaSeal.png"):
        st.image("LoyolaSeal.png", use_container_width=True)

# --- 5. MAIN DASHBOARD ---
st.title("🎓 Loyola AI Schedule Advisor")

if uploaded_files:
    # CAREER MAPPING HEADER
    role, target = map_career(qpa_val)
    st.info(f"🚀 **Career Alignment:** {role} | **Target Markets:** {target}")

    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📅 Recommended Courses")
        recs = get_recommendations(earned_val)
        rec_df = pd.DataFrame({"Priority Course": recs, "Type": ["Core Major"]*len(recs), "Credits": [3]*len(recs)})
        st.table(rec_df)
        
        # DOWNLOAD BUTTON
        csv = rec_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Schedule (CSV)", data=csv, file_name="loyola_schedule.csv", mime="text/csv")

    with col2:
        st.subheader("📝 Graduation Goals")
        st.checkbox("120 Credits", value=(earned_val >= 120))
        st.checkbox("Honors Status", value=(float(qpa_val) >= 3.5))
        st.progress(min(earned_val / 120, 1.0), text="Degree Completion")

else:
    st.warning("Please upload your Degree Audit to activate AI features.")

st.markdown('<div class="footer">Built by Krishon Pinkins | Loyola University Maryland 2026</div>', unsafe_allow_html=True)
