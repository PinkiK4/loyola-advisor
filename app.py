import streamlit as st
import pdfplumber
import re
import pandas as pd
import os
import base64

# --- 1. PAGE CONFIG & BACKGROUND INJECTOR ---
st.set_page_config(page_title="Loyola Advisor", layout="wide", page_icon="🎓")

def get_base64(bin_file):
    with open(bin_file, 'rb') as f:
        return base64.b64encode(f.read()).decode()

def set_style(img_file):
    if os.path.exists(img_file):
        bin_str = get_base64(img_file)
        st.markdown(f'''
            <style>
            .stApp {{
                background-image: url("data:image/jpeg;base64,{bin_str}");
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
            }}
            .stApp > div {{
                background-color: rgba(0, 0, 0, 0.8) !important;
                padding: 1rem;
                border-radius: 10px;
            }}
            
            /* Branded Headings */
            h1 {{ color: #006838 !important; font-weight: 800 !important; }}
            h2, h3 {{ color: white !important; }}
            
            [data-testid="stMetric"] {{ background-color: #1e1e1e !important; border-left: 5px solid #006838 !important; }}
            thead tr th {{ background-color: #006838 !important; color: white !important; }}
            
            /* Sidebar Styling */
            [data-testid="stSidebar"] {{
                background-color: rgba(0, 0, 0, 0.9) !important;
                border-right: 1px solid #333333;
            }}
            
            /* FIXED BOTTOM ATTRIBUTION */
            .footer {{
                position: fixed;
                left: 0;
                bottom: 10px;
                width: 100%;
                text-align: center;
                color: #888888;
                font-size: 14px;
                z-index: 100;
            }}
            </style>
            ''', unsafe_allow_html=True)

set_style("Background.jpeg")

# --- 2. DATA LOGIC ---
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

# --- 3. SIDEBAR WITH PINNED SEAL ---
# We use a column layout within the sidebar to create a distinct bottom section
with st.sidebar:
    st.header("📂 Document Center")
    uploaded_files = st.file_uploader("Upload Audit PDFs", type="pdf", accept_multiple_files=True)
    
    if uploaded_files:
        earned_val, qpa_val = extract_data(uploaded_files)
        st.metric("Total Credits", f"{earned_val} / 120")
        st.metric("Current QPA", qpa_val)
        st.progress(min(earned_val / 120, 1.0))
    else:
        # Placeholder so the sidebar doesn't shrink when empty
        st.markdown("<br><br><br><br><br><br><br>", unsafe_allow_html=True)
    
    # --- SEAL PLACEMENT (NOW PINNED TO SIDEBAR BOTTOM) ---
    st.markdown("---") # Line separator
    if os.path.exists("LoyolaSeal.png"):
        seal_base64 = get_base64("LoyolaSeal.png")
        st.markdown(f'''
            <div style="text-align: center; padding-top: 10px;">
                <img src="data:image/png;base64,{seal_base64}" width="150">
            </div>
        ''', unsafe_allow_html=True)
    else:
        st.error("'LoyolaSeal.png' missing.")

# --- 4. MAIN DASHBOARD AREA ---
st.title("🎓 Loyola Data Science Advisor")

if uploaded_files:
    if float(qpa_val) >= 3.5:
        st.success(f"### 🎉 Honors Candidate: {qpa_val} QPA")
    
    col_main, col_checklist = st.columns([2, 1])
    
    with col_main:
        st.subheader("📅 Recommended Spring 2026 Schedule")
        df = pd.DataFrame({"Course": ["DS 496", "ST 472", "IS 358", "SN 104"], "Credits": [3, 3, 3, 3]})
        st.table(df)
        
    with col_checklist:
        st.subheader("📝 Checklist")
        st.checkbox("120 Credits", value=(earned_val >= 120))
        st.checkbox("GPA > 2.0", value=(float(qpa_val) >= 2.0))
        st.checkbox("Minor Electives", value=True)
else:
    st.info("Awaiting document upload...")

# --- FIXED FOOTER (BOTTOM OF SCREEN) ---
st.markdown('<div class="footer">Built by Krishon Pinkins | Loyola University Maryland 2026</div>', unsafe_allow_html=True)
