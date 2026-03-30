[import streamlit as st
import pdfplumber
import re
import pandas as pd

# --- CONFIGURATION ---
st.set_page_config(page_title="Loyola Advisor", layout="wide", page_icon="🎓")

# --- DATA EXTRACTION LOGIC ---
def extract_audit_data(file):
    """Scrapes the PDF for key Loyola graduation metrics."""
    try:
        with pdfplumber.open(file) as pdf:
            # We look at the first two pages for summary data
            text = "".join([page.extract_text() for page in pdf.pages[:2]])
            
        # Regex to find credit counts (e.g., "126 of 120")
        credit_match = re.search(r"(\d+)\s+of\s+120", text)
        # Regex to find GPA (e.g., "Cumulative QPA: 3.548")
        qpa_match = re.search(r"Cumulative (?:GPA|QPA):\s+(\d\.\d+)", text)
        
        earned = int(credit_match.group(1)) if credit_match else 0
        qpa = qpa_match.group(1) if qpa_match else "0.000"
        
        return earned, qpa
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return 0, "0.000"

# --- SIDEBAR: UPLOADS & METRICS ---
with st.sidebar:
    st.image("https://www.loyola.edu/_/-/media/department/brand/logos/loyola-logo-green.png", width=180)
    st.header("📂 Document Center")
    
    # Define the uploader first to avoid NameErrors
    audit_file = st.file_uploader("Upload Degree Audit (PDF)", type="pdf")
    
    st.divider()
    
    # Default values
    earned_val = 0
    qpa_val = "0.000"
    
    if audit_file:
        # Run the scraper
        earned_val, qpa_val = extract_audit_data(audit_file)
        
        st.subheader("📊 Academic Snapshot")
        st.metric("Total Credits", f"{earned_val} / 120")
        st.metric("Current QPA", qpa_val)
        
        # Visual Progress Bar
        progress = min(earned_val / 120, 1.0)
        st.progress(progress)
        
        if earned_val >= 120:
            st.success("✅ Graduation Credits Met")
    else:
        st.info("👋 Upload an audit to sync your dashboard.")

# --- MAIN UI ---
st.title("🎓 Loyola Data Science Advisor")
st.markdown("---")

if audit_file:
    # 1. Honors Recognition
    if float(qpa_val) >= 3.5:
        st.balloons()
        st.success(f"### 🎉 Honors Candidate: {qpa_val} QPA")
        st.write("You are currently on track for **Cum Laude** graduation honors!")

    # 2. Recommended Schedule (General Example)
    st.subheader("📅 Recommended Spring 2026 Schedule")
    schedule_data = {
        "Course Code": ["DS 496", "ST 472", "IS 358", "SN 104", "Elective"],
        "Course Name": ["Capstone Project", "Statistical Learning", "Business Intelligence", "Intermediate Spanish II", "Free Elective"],
        "Credits": [3, 3, 3, 3, 3]
    }
    df = pd.DataFrame(schedule_data)
    st.table(df)

    # 3. Graduation Roadmap
    with st.expander("📝 View Graduation Checklist"):
        st.write("- [x] 120 Total Credit Minimum")
        st.write("- [x] Cumulative QPA above 2.0")
        st.write("- [ ] Completion of SN 104 (Language Core)")
        st.write("- [ ] Submission of Graduation Application")

else:
    st.warning("Please upload your Degree Audit in the sidebar to generate your report.")
    st.info("This tool is a student-led project for Data Science portfolio purposes.")

# --- FOOTER ---
st.markdown("---")
st.caption("Built by Krishon Pinkins | Loyola University Maryland 2026")]
