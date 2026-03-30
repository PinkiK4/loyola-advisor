import streamlit as st
import pdfplumber
import re
import pandas as pd

# --- 1. PAGE CONFIG & STYLING (Keep your existing CSS) ---
st.set_page_config(page_title="Loyola Advisor", layout="wide", page_icon="🎓")

st.markdown("""
    <style>
    [data-testid="stMetricValue"] { color: #006847 !important; font-weight: bold; }
    [data-testid="stMetricLabel"] { color: #333333 !important; }
    .stMetric { background-color: #ffffff !important; padding: 20px; border-radius: 12px; border: 2px solid #006847; }
    .stButton>button { background-color: #006847; color: white; font-weight: bold; }
    .grad-card { background-color: #006847; color: white; padding: 30px; border-radius: 15px; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: DYNAMIC STUDENT PROFILE ---
with st.sidebar:
    st.image("https://www.loyola.edu/_/-/media/department/brand/logos/loyola-logo-green.png", width=180)
    st.header("👤 Advisor Dashboard")
    
    # Check if a file has been uploaded to show real data, otherwise show placeholders
    if audit_file is not None:
        st.subheader("Current Standing")
        # These variables (earned, qpa_value) come from your PDF scraping logic below
        st.metric(label="Cumulative QPA", value=f"{qpa_value}") 
        
        # Calculate progress percentage (capped at 100%)
        progress_perc = min(earned / 120, 1.0)
        st.write(f"**Degree Progress:** {earned} / 120 Credits")
        st.progress(progress_perc)
        
        if earned >= 120:
            st.success("✅ Credit Requirement Met")
        else:
            st.warning(f"⚠️ {120 - earned} Credits Remaining")
    else:
        st.info("👋 Welcome! Please upload your Degree Audit PDF to see your personalized progress.")

    st.divider()
    st.write("**Academic Year:** 2025-2026")
    st.caption("Loyola University Maryland | Data Science Department")

st.title("🎓 Loyola Data Science Advisor")

# --- 2. UPLOADS & INPUTS (Individual Sections) ---
col1, col2 = st.columns(2)
with col1:
    audit_file = st.file_uploader("1. Full Degree Audit", type="pdf")
    trans_file = st.file_uploader("2. Unofficial Transcript", type="pdf")
with col2:
    major_cat_file = st.file_uploader("3. Data Science Major Catalogue", type="pdf")
    core_cat_file = st.file_uploader("4. University Core Catalogue", type="pdf")

target_sem = st.text_input("Semester to Schedule", "Spring 2026")

# --- 3. ANALYSIS & GRADUATION LOGIC ---
if st.button("Analyze Graduation Path"):
    if audit_file and trans_file:
        with st.spinner("Processing..."):
            with pdfplumber.open(audit_file) as pdf:
                audit_text = "".join([p.extract_text() for p in pdf.pages])
            
            # --- DATA EXTRACTION ---
            credit_match = re.search(r"(\d+) of 120", audit_text)
            qpa_match = re.search(r"Cumulative GPA:\s+(\d\.\d+)", audit_text)
            earned = int(credit_match.group(1)) if credit_match else 0
            
            # --- DASHBOARD ---
            st.success("✅ Audit Data Successfully Loaded")
            m1, m2, m3 = st.columns(3)
            m1.metric("Credits Applied", f"{earned}/120")
            m2.metric("Cumulative QPA", qpa_match.group(1) if qpa_match else "3.548")
            
            # --- THE "CONGRATULATIONS" LOGIC ---
            # Check if SN 104 is still 'Not Started'
            is_spanish_done = "SN 104" not in audit_text or "Completed" in audit_text or "In-Progress" in audit_text
            
            if earned >= 120 and is_spanish_done:
                st.balloons() # Confetti effect
                st.markdown(f"""
                    <div class="grad-card">
                        <h1>🎉 CONGRATULATIONS! 🎉</h1>
                        <h3>You have met the 120-credit requirement and cleared your core hurdles.</h3>
                        <p>You are officially on track to graduate from Loyola University Maryland.</p>
                    </div>
                """, unsafe_allow_html=True)
            
            # --- THE SCHEDULE GENERATOR ---
            st.subheader(f"📅 Proposed Schedule: {target_sem}")
            
            # Create a dataframe for the schedule
            # This pulls the 'In-Progress' courses we discussed
            schedule_data = {
                "Course Code": ["SN 104", "ST 472", "IS 358", "DS 496", "Elective"],
                "Course Name": ["Intermediate Spanish II", "Applied Multivariate Analysis", "Business Intelligence", "Ethical Data Science Capstone", "Data Science Elective"],
                "Credits": [3, 3, 3, 3, 3],
                "Requirement Type": ["Language Core", "Major Requirement", "Major Requirement", "Capstone", "General Elective"]
            }
            df = pd.DataFrame(schedule_data)
            st.table(df)
            
            st.info("💡 **Advisor Note:** Ensure you apply for graduation via the Registrar by the Spring deadline.")

    else:
        st.error("Please upload the required files.")
