import base64
import os
import re
import tempfile
from collections import OrderedDict

import pandas as pd
import pdfplumber
import streamlit as st
from fpdf import FPDF


st.set_page_config(
    page_title="AI Schedule Advisor | Loyola 2026",
    layout="wide",
    page_icon="🎓",
)


def get_base64(bin_file: str) -> str:
    if os.path.exists(bin_file):
        with open(bin_file, "rb") as file:
            return base64.b64encode(file.read()).decode()
    return ""


def set_style(img_file: str) -> None:
    bin_str = get_base64(img_file)
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{bin_str}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        .stApp > div {{
            background-color: rgba(10, 10, 10, 0.72) !important;
            backdrop-filter: blur(10px);
            padding: 2rem;
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        h1, h2, h3 {{
            color: #e8f6ee !important;
        }}
        [data-testid="stSidebar"] {{
            background-color: rgba(15, 15, 15, 0.98) !important;
            border-right: 5px solid #006838 !important;
        }}
        .info-card {{
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 12px;
        }}
        .footer {{
            position: fixed;
            left: 0;
            bottom: 8px;
            width: 100%;
            text-align: center;
            color: white;
            font-size: 13px;
            z-index: 1000;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


set_style("Background.jpeg")


STATUS_WORDS = ("Completed", "Not Started", "In Progress", "Fulfi lled", "Fulfilled")
GRADE_TOKENS = {
    "A",
    "A-",
    "B+",
    "B",
    "B-",
    "C+",
    "C",
    "C-",
    "D+",
    "D",
    "D-",
    "F",
    "P",
    "S",
    "U",
    "W",
    "AU",
    "IP",
    "CIP",
}


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_course_code(subject: str, number: str) -> str:
    return f"{subject.strip().upper()} {number.strip()}"


def uploaded_pdf_text(uploaded_file) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.getbuffer())
        temp_path = tmp.name

    try:
        with pdfplumber.open(temp_path) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def parse_transcript(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    name = "Unknown Student"
    sid = "N/A"
    major = "Unknown"
    total_credits = 0.0
    gpa = "N/A"
    course_rows = []
    qpa_values = []
    current_term = ""

    term_heading_pattern = re.compile(r"^(Fall|Spring|Summer|Winter)\s+\d{2}$", re.I)
    course_pattern = re.compile(
        r"^([A-Z]{2,4})\s+(\d{3})\s+([A-Z0-9]{2,3})\s*(.+?)\s+(\d+\.\d{2})(?:\s+([A-Z][+-]?|CIP|IP|P|S|U|W|AU))?$"
    )

    for line in lines:
        if line.startswith("Name:"):
            cleaned = re.sub(r"\s+LOYOLA UNIVERSITY MARYLAND.*", "", line)
            name = cleaned.replace("Name:", "", 1).strip() or name

        sid_match = re.search(r"(?:I\.D\.No\.|Student ID|ID|SID):\s*(\d{5,10})", line, re.I)
        if sid_match:
            sid = sid_match.group(1)

        major_match = re.search(r"Major:\s*(.+)", line, re.I)
        if major_match:
            major = normalize_space(major_match.group(1))

        total_match = re.search(r"Total CA:\s*[\d.]+\s+CE:\s*([\d.]+).*QPA:\s*([\d.]+)", line, re.I)
        if total_match:
            total_credits = float(total_match.group(1))
            qpa_values.append(float(total_match.group(2)))

        qpa_match = re.search(r"QPA:\s*([\d.]+)", line, re.I)
        if qpa_match:
            qpa_values.append(float(qpa_match.group(1)))

        if term_heading_pattern.match(line):
            current_term = line

        course_match = course_pattern.match(line)
        if course_match:
            subject, number, section, raw_title, credits, grade = course_match.groups()
            code = normalize_course_code(subject, number)
            course_rows.append(
                {
                    "Course ID": code,
                    "Course Name": normalize_space(raw_title),
                    "Section": section,
                    "Credits": float(credits),
                    "Grade": grade or "",
                    "Term": current_term,
                }
            )

    nonzero_qpas = [value for value in qpa_values if value > 0]
    if nonzero_qpas:
        gpa = f"{nonzero_qpas[-1]:.3f}"

    courses_df = pd.DataFrame(course_rows)
    taken_codes = set(courses_df["Course ID"].tolist()) if not courses_df.empty else set()
    in_progress_codes = (
        set(courses_df.loc[courses_df["Grade"].isin({"CIP", "IP"}), "Course ID"].tolist())
        if not courses_df.empty
        else set()
    )

    return {
        "name": name,
        "sid": sid,
        "major": major,
        "qpa": gpa,
        "total": total_credits,
        "courses_df": courses_df,
        "taken_codes": taken_codes,
        "in_progress_codes": in_progress_codes,
    }


def parse_audit(text: str) -> dict:
    lines = [line.rstrip() for line in text.splitlines()]
    requirement_rows = []
    current_section = "Requirements"
    current_block = "Degree Requirement"
    current_block_complete = None
    section_pattern = re.compile(r"^[A-Z][A-Za-z/&,\-\s]{3,}$")
    course_line_pattern = re.compile(
        r"^(Not Started|In Progress|Completed|Fulfi\s*lled|Fulfilled)\s+([A-Z]{2,4})\*?(\d{3})\s+(.+)$",
        re.I,
    )
    block_progress_pattern = re.compile(
        r"(\d+)\s+of\s+(\d+)\s+(?:Courses|Credits)?\s*Completed\.?$",
        re.I,
    )

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        if (
            section_pattern.match(line)
            and "Page " not in line
            and "Status Course Grade Term Credits" not in line
            and not any(line.startswith(prefix) for prefix in STATUS_WORDS)
            and len(line.split()) <= 6
        ):
            current_section = normalize_space(line)
            continue

        if line.startswith("Take ") or re.match(r"^\d+\.\s+Take ", line):
            current_block = normalize_space(line)
            continue

        progress_match = block_progress_pattern.search(line)
        if progress_match:
            current_block_complete = int(progress_match.group(1)) >= int(progress_match.group(2))
            continue

        if line.endswith("Fulfilled") and "Status Course Grade Term Credits" not in line:
            current_block_complete = True
            current_block = normalize_space(line)
            continue

        if line == "Not Started":
            current_block_complete = False
            continue

        match = course_line_pattern.match(line)
        if not match:
            continue

        status, subject, number, title = match.groups()
        code = normalize_course_code(subject, number)
        requirement_rows.append(
            {
                "Audit Status": normalize_space(status),
                "Course ID": code,
                "Course Name": normalize_space(title),
                "Requirement Area": current_section,
                "Requirement Block": current_block,
                "Requirement Complete": current_block_complete,
            }
        )

    requirements_df = pd.DataFrame(requirement_rows)
    if requirements_df.empty:
        return {"requirements_df": requirements_df, "audit_gpa": "N/A"}

    requirements_df = requirements_df.drop_duplicates(subset=["Course ID", "Requirement Block"])
    audit_gpa_match = re.search(r"Cumulative GPA:\s*([\d.]+)", text, re.I)
    audit_gpa = audit_gpa_match.group(1) if audit_gpa_match else "N/A"

    return {"requirements_df": requirements_df, "audit_gpa": audit_gpa}


def parse_catalogs(catalog_files) -> pd.DataFrame:
    entries = OrderedDict()
    course_pattern = re.compile(
        r"\b([A-Z]{2,4})\s+(\d{3})\s*[-:]\s*([A-Za-z0-9&,'/().\- ]+?)(?=\s{2,}|Prerequisite|Corequisite|$)"
    )
    credit_pattern = re.compile(r"(\d+(?:\.\d+)?)\s+credits?", re.I)

    for catalog_file in catalog_files:
        text = uploaded_pdf_text(catalog_file)
        for raw_line in text.splitlines():
            line = normalize_space(raw_line)
            match = course_pattern.search(line)
            if not match:
                continue

            subject, number, title = match.groups()
            code = normalize_course_code(subject, number)
            credits_match = credit_pattern.search(line)
            entries[code] = {
                "Course ID": code,
                "Catalog Title": normalize_space(title),
                "Catalog Credits": float(credits_match.group(1)) if credits_match else 3.0,
            }

    return pd.DataFrame(entries.values()) if entries else pd.DataFrame()


def apply_transcript_track_lock(pending_df: pd.DataFrame, transcript_data: dict) -> pd.DataFrame:
    if pending_df.empty:
        return pending_df

    locked_groups = []

    for _, group in pending_df.groupby("Requirement Block", dropna=False):
        group = group.copy()
        option_subjects = group["Course ID"].str.extract(r"^([A-Z]{2,4})")[0].dropna().unique().tolist()

        taken_in_block = [
            code
            for code in transcript_data["taken_codes"].union(transcript_data["in_progress_codes"])
            if code in set(group["Course ID"])
        ]

        if not taken_in_block:
            locked_groups.append(group)
            continue

        taken_subjects = [code.split()[0] for code in taken_in_block]
        preferred_subject = max(set(taken_subjects), key=taken_subjects.count)

        if preferred_subject in option_subjects:
            group = group[group["Course ID"].str.startswith(f"{preferred_subject} ")].copy()

        locked_groups.append(group)

    return pd.concat(locked_groups, ignore_index=True) if locked_groups else pending_df


def build_schedule(transcript_data: dict, audit_data: dict, catalog_df: pd.DataFrame) -> pd.DataFrame:
    requirements_df = audit_data["requirements_df"]
    if requirements_df.empty:
        return pd.DataFrame()

    pending_df = requirements_df.copy()
    pending_df = pending_df[pending_df["Requirement Complete"] != True].copy()
    pending_df = pending_df[pending_df["Audit Status"].isin(["Not Started", "In Progress"])].copy()
    pending_df = pending_df[~pending_df["Course ID"].isin(transcript_data["taken_codes"])].copy()
    pending_df = pending_df.drop_duplicates(subset=["Course ID", "Requirement Block"])
    pending_df = apply_transcript_track_lock(pending_df, transcript_data)

    if not catalog_df.empty:
        pending_df = pending_df.merge(catalog_df, on="Course ID", how="left")
        pending_df["Course Name"] = pending_df["Catalog Title"].fillna(pending_df["Course Name"])
        pending_df["Credits"] = pending_df["Catalog Credits"].fillna(3.0)
    else:
        pending_df["Credits"] = 3.0

    pending_df["Level"] = pending_df["Course ID"].str.extract(r"(\d{3})").astype(float)
    pending_df["Recommended Term"] = pending_df["Course ID"].apply(
        lambda code: "Current Term" if code in transcript_data["in_progress_codes"] else "Next Term"
    )
    pending_df["Priority"] = pending_df["Recommended Term"].map({"Current Term": 0, "Next Term": 1}).fillna(9)

    pending_df = pending_df.sort_values(
        by=["Priority", "Recommended Term", "Level", "Course ID"], ascending=[True, True, True, True]
    )

    selected_rows = []
    running_credits = 0.0
    for _, row in pending_df.iterrows():
        credits = float(row["Credits"])
        if running_credits + credits > 15:
            continue
        selected_rows.append(row)
        running_credits += credits
        if running_credits >= 15:
            break

    pending_df = pd.DataFrame(selected_rows)
    if pending_df.empty:
        return pd.DataFrame()

    return pending_df[
        [
            "Recommended Term",
            "Requirement Area",
            "Requirement Block",
            "Course ID",
            "Course Name",
            "Credits",
            "Audit Status",
        ]
    ].reset_index(drop=True)


def create_pdf(student: dict, schedule_df: pd.DataFrame) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "AI Schedule Advice", ln=True, align="C")
    pdf.ln(4)

    pdf.set_font("Arial", size=11)
    pdf.cell(0, 8, f"Student: {student['name']} | ID: {student['sid']}", ln=True)
    pdf.cell(0, 8, f"Major: {student['major']} | GPA: {student['qpa']}", ln=True)
    pdf.cell(0, 8, f"Earned Credits: {student['total']}", ln=True)
    pdf.ln(6)

    pdf.set_font("Arial", "B", 10)
    pdf.cell(34, 8, "Course ID", 1)
    pdf.cell(86, 8, "Course Name", 1)
    pdf.cell(25, 8, "Credits", 1)
    pdf.cell(35, 8, "Term", 1)
    pdf.ln()

    pdf.set_font("Arial", size=9)
    for _, row in schedule_df.iterrows():
        pdf.cell(34, 8, str(row["Course ID"])[:15], 1)
        pdf.cell(86, 8, str(row["Course Name"])[:42], 1)
        pdf.cell(25, 8, str(row["Credits"]), 1)
        pdf.cell(35, 8, str(row["Recommended Term"])[:16], 1)
        pdf.ln()

    return pdf.output(dest="S").encode("latin-1")


with st.sidebar:
    st.header("Document Center")
    audit_file = st.file_uploader("1. Upload Degree Audit", type="pdf", key="audit")
    transcript_file = st.file_uploader("2. Upload Official Transcript", type="pdf", key="transcript")
    catalog_files = st.file_uploader(
        "3. Optional Course Catalog PDFs",
        type="pdf",
        accept_multiple_files=True,
        key="catalogs",
    )
    st.caption("Catalog PDFs improve titles, credits, and future prerequisite logic.")
    st.divider()

    if os.path.exists("LoyolaSeal.png"):
        st.image("LoyolaSeal.png", use_container_width=True)


st.title("Loyola AI Schedule Advisor")

if audit_file and transcript_file:
    transcript_text = uploaded_pdf_text(transcript_file)
    audit_text = uploaded_pdf_text(audit_file)

    transcript_data = parse_transcript(transcript_text)
    audit_data = parse_audit(audit_text)
    catalog_df = parse_catalogs(catalog_files or [])
    schedule_df = build_schedule(transcript_data, audit_data, catalog_df)

    transcript_gpa = transcript_data["qpa"]
    audit_gpa = audit_data["audit_gpa"]
    gpa_display = transcript_gpa if transcript_gpa != "N/A" else audit_gpa

    st.markdown(
        f"""
        <div class="info-card" style="background-color: #162a3d; border-left: 5px solid #3498db;">
            <b>Profile:</b> {transcript_data['name']} | ID: {transcript_data['sid']} | Major: {transcript_data['major']}
        </div>
        <div class="info-card" style="background-color: #1b3d2c; border-left: 5px solid #28a745;">
            <b>GPA / Credits:</b> GPA {gpa_display} | Earned Credits {transcript_data['total']}
        </div>
        """,
        unsafe_allow_html=True,
    )

    left_col, right_col = st.columns([2, 1])

    with left_col:
        st.subheader("Recommended Schedule")
        if schedule_df.empty:
            st.success("No remaining courses were detected from the audit.")
        else:
            st.dataframe(schedule_df, use_container_width=True, hide_index=True)
            pdf_bytes = create_pdf(
                {
                    "name": transcript_data["name"],
                    "sid": transcript_data["sid"],
                    "major": transcript_data["major"],
                    "qpa": gpa_display,
                    "total": transcript_data["total"],
                },
                schedule_df.head(8),
            )
            st.download_button(
                "Download Schedule Advice PDF",
                data=pdf_bytes,
                file_name="Loyola_Schedule_Advice.pdf",
            )

    with right_col:
        st.subheader("Parsing Check")
        st.metric("Transcript GPA", transcript_gpa)
        st.metric("Audit GPA", audit_gpa)
        st.metric("Transcript Courses Found", len(transcript_data["courses_df"]))
        st.metric("Remaining Audit Courses", len(schedule_df))
        st.metric("Suggested Credits", int(schedule_df["Credits"].sum()) if not schedule_df.empty else 0)
        st.metric("Catalog Matches", int(schedule_df["Course Name"].notna().sum()) if not schedule_df.empty else 0)

        with st.expander("In-Progress Courses"):
            if transcript_data["in_progress_codes"]:
                st.write(sorted(transcript_data["in_progress_codes"]))
            else:
                st.write("None detected.")

        with st.expander("Transcript Course Sample"):
            st.dataframe(
                transcript_data["courses_df"].head(12),
                use_container_width=True,
                hide_index=True,
            )

        with st.expander("Unfinished Audit Requirements"):
            st.dataframe(
                audit_data["requirements_df"].head(25),
                use_container_width=True,
                hide_index=True,
            )

    if catalog_files:
        st.caption(
            "Catalog enrichment is active. Next step would be parsing prerequisites and term availability from the catalog."
        )
    else:
        st.info("Upload course catalog PDFs if you want better course titles, credits, and later prerequisite checks.")

else:
    st.warning("Upload both the degree audit and transcript PDFs to start the analysis.")


st.markdown(
    '<div class="footer">Built by Krishon Pinkins | Loyola University Maryland 2026</div>',
    unsafe_allow_html=True,
)
