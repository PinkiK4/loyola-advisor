import base64
import json
import os
import re
import tempfile
import urllib.error
import urllib.request
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
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
GEMINI_URL = os.getenv("GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_course_code(subject: str, number: str) -> str:
    return f"{subject.strip().upper()} {number.strip()}"


def canonicalize_audit_status(text: str) -> str:
    normalized = normalize_space(text.replace("-", ""))
    lowered = normalized.lower()
    compact = lowered.replace(" ", "")
    if compact in {"completed", "complete"}:
        return "Completed"
    if compact in {"inprogress"}:
        return "In Progress"
    if compact in {"fulfilled"}:
        return "Fulfilled"
    if compact in {"notstarted"}:
        return "Not Started"
    return normalized.title()


def clean_course_title(title: str) -> str:
    cleaned = normalize_space(title)
    cleaned = re.sub(
        r"\b(?:A|A-|B\+|B|B-|C\+|C|C-|D\+|D|D-|F|P|S|U|W|IP|CIP)\b\s+\d{2}/[A-Z]{2}\s+\d+(?:\.\d+)?\b",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\b\d{2}/[A-Z]{2}\b\s+\d+(?:\.\d+)?\b", "", cleaned)
    cleaned = re.sub(
        r"\b(?:A|A-|B\+|B|B-|C\+|C|C-|D\+|D|D-|F|P|S|U|W|IP|CIP)\b\s+\d{2}/[A-Z]{2}\s+\d+\b",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\b\d{2}/[A-Z]{2}\b\s+\d+\b", "", cleaned)
    cleaned = re.sub(r"(?<=\s)(?:A|A-|B\+|B|B-|C\+|C|C-|D\+|D|D-|F|P|S|U|W|IP|CIP)(?=\s+[A-Z])", "", cleaned)
    cleaned = re.sub(r"\b(Freshman Year|Sophomore Year|Junior Year|Senior Year|Elective Component|Foundational Component|DS Elective)\b.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(Program:|Requirements for the Major|Status Course Grade Term Credits)\b.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(Completed|In Progress|Not Started|Fulfilled)\b$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"(?:\s|^)(A|A-|B\+|B|B-|C\+|C|C-|D\+|D|D-|F|P|S|U|W|IP|CIP)$", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.rstrip(" -,:;")


def strip_catalog_title_noise(title: str) -> str:
    cleaned = clean_course_title(title)
    cleaned = re.sub(
        r"\b(Freshman|Sophomore|Junior|Senior)\s+Year\b.*$",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r"\b(?:Spring|Fall|Summer|Winter)\s+Term\b",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r"\b(?:Language Core|Social Science Core|Fine Arts Core|HS-\d{3}\s+Level Core Course|Core Elective|Elective Component|Foundational Component)\b",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"\bElective\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\bRestricted to [^.]+\.?", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\bAppropriate course as approved by [^.]+\.?", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\bor\s*$", "", cleaned, flags=re.I)
    cleaned = cleaned.replace("*", " ")
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.rstrip(" -,:;")


def parse_audit_term_code(text: str) -> str:
    match = re.search(r"\b(\d{2}/[A-Z]{2})\b", text)
    return match.group(1) if match else ""


def term_sort_key(term_label: str):
    if not term_label:
        return None

    transcript_match = re.match(r"^(Winter|Spring|Summer|Fall)\s+(\d{2})$", term_label, re.I)
    if transcript_match:
        season, year = transcript_match.groups()
        season_map = {"winter": 0, "spring": 1, "summer": 2, "fall": 3}
        return (int(year), season_map[season.lower()])

    audit_match = re.match(r"^(\d{2})/([A-Z]{2})$", term_label, re.I)
    if audit_match:
        year, season = audit_match.groups()
        season_map = {"WI": 0, "SP": 1, "SU": 2, "FA": 3, "OC": -1}
        return (int(year), season_map.get(season.upper(), 9))

    return None


def term_index(term_label: str):
    key = term_sort_key(term_label)
    if key is None:
        return None
    year, season = key
    return year * 4 + season


def get_latest_transcript_term(transcript_data: dict):
    if transcript_data["courses_df"].empty:
        return None

    term_keys = [
        term_sort_key(term)
        for term in transcript_data["courses_df"]["Term"].dropna().unique().tolist()
    ]
    term_keys = [key for key in term_keys if key is not None]
    return max(term_keys) if term_keys else None


def requirement_category_priority(requirement_area: str, requirement_block: str, requirement_complete) -> int:
    area = (requirement_area or "").lower()
    block = (requirement_block or "").lower()

    if requirement_complete is True:
        base = 2
    else:
        base = 0

    if "free elective" in block or "additional free elective" in block:
        return base + 3
    if "diversity requirement" in area or "diversity courses" in block:
        return base + 2
    if "university core" in area or "data science" in area:
        return base
    return base + 1


def sequence_gap_priority(course_id: str, transcript_data: dict) -> int:
    subject_match = re.match(r"^([A-Z]{2,4})\s+(\d{3})$", str(course_id))
    if not subject_match:
        return 0

    subject, number = subject_match.groups()
    target_number = int(number)
    subject_numbers = []
    for code in transcript_data["taken_codes"].union(transcript_data["in_progress_codes"]):
        match = re.match(rf"^{re.escape(subject)}\s+(\d{{3}})$", str(code))
        if match:
            subject_numbers.append(int(match.group(1)))

    if not subject_numbers:
        return 0

    highest_taken = max(subject_numbers)
    if target_number <= highest_taken + 1:
        return 0

    # Penalize skipped sequence steps, especially lower-level progressions like languages.
    if highest_taken < 200 and target_number < 200:
        return target_number - highest_taken - 1

    return 0


def increment_roman_numeral(title: str) -> str:
    roman_steps = {"I": "II", "II": "III", "III": "IV", "IV": "V"}
    for current, nxt in roman_steps.items():
        if re.search(rf"\b{current}\b", title):
            return re.sub(rf"\b{current}\b", nxt, title, count=1)
    return title


def infer_sequenced_course(row: pd.Series, transcript_data: dict) -> pd.Series:
    course_id = str(row["Course ID"])
    subject_match = re.match(r"^([A-Z]{2,5})\s+(\d{3})$", course_id)
    if not subject_match:
        return row

    subject, number = subject_match.groups()
    target_number = int(number)
    if subject == "LANG":
        inferred_subject = infer_language_subject(transcript_data)
        if not inferred_subject:
            return row
        subject = inferred_subject
    subject_rows = transcript_data["courses_df"][
        transcript_data["courses_df"]["Course ID"].str.startswith(f"{subject} ", na=False)
    ]
    subject_numbers = []
    for code in transcript_data["taken_codes"].union(transcript_data["in_progress_codes"]):
        match = re.match(rf"^{re.escape(subject)}\s+(\d{{3}})$", str(code))
        if match:
            subject_numbers.append(int(match.group(1)))

    if not subject_numbers:
        return row

    highest_taken = max(subject_numbers)
    if not (highest_taken < target_number and highest_taken < 200 and target_number < 200):
        return row

    next_number = highest_taken + 1
    if next_number >= target_number:
        row = row.copy()
        row["Course ID"] = f"{subject} {target_number:03d}"
        if not row.get("Course Name"):
            row["Course Name"] = f"{subject} {target_number:03d}"
        return row

    row = row.copy()
    row["Course ID"] = f"{subject} {next_number:03d}"
    row["Audit Status"] = "Not Started"
    row["Recommended Term"] = "Next Term"

    previous_title = ""
    if not subject_rows.empty:
        previous_title = str(subject_rows.sort_values(by="Course ID").iloc[-1]["Course Name"])
    if previous_title:
        row["Course Name"] = increment_roman_numeral(previous_title)
    elif not row.get("Course Name", ""):
        row["Course Name"] = f"{subject} {next_number:03d}"
    elif str(row.get("Course Name", "")).startswith("Intermediate II Language Course"):
        language_names = {
            "SN": "Spanish",
            "FR": "French",
            "IT": "Italian",
            "LT": "Latin",
            "GR": "Greek",
            "GK": "Greek",
            "AB": "Arabic",
            "CI": "Chinese",
        }
        display_name = language_names.get(subject, subject)
        if next_number == 104:
            row["Course Name"] = f"Intermediate {display_name} II"
        elif next_number == 103:
            row["Course Name"] = f"Intermediate {display_name} I"
        elif next_number == 102:
            row["Course Name"] = f"Introductory {display_name} II"
        elif next_number == 101:
            row["Course Name"] = f"Introductory {display_name} I"

    return row


def clean_catalog_title(title: str) -> str:
    return clean_course_title(title)


TITLE_STOPWORDS = {
    "and",
    "for",
    "the",
    "of",
    "in",
    "to",
    "or",
    "ii",
    "iii",
    "iv",
    "i",
    "course",
}


def normalized_title_tokens(text: str) -> set[str]:
    cleaned = clean_course_title(text).lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    tokens = {
        token
        for token in cleaned.split()
        if len(token) > 1 and token not in TITLE_STOPWORDS and not token.isdigit()
    }
    return tokens


def title_similarity(left: str, right: str) -> float:
    left_tokens = normalized_title_tokens(left)
    right_tokens = normalized_title_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0

    overlap = len(left_tokens & right_tokens)
    if overlap == 0:
        return 0.0

    containment = overlap / min(len(left_tokens), len(right_tokens))
    jaccard = overlap / len(left_tokens | right_tokens)
    return max(containment, (containment + jaccard) / 2)


def transcript_has_equivalent_course(course_id: str, course_name: str, transcript_data: dict, min_similarity: float = 0.74) -> bool:
    if course_id in transcript_data["taken_codes"] or course_id in transcript_data["in_progress_codes"]:
        return True

    courses_df = transcript_data.get("courses_df", pd.DataFrame())
    if courses_df.empty or not course_name:
        return False

    for transcript_title in courses_df["Course Name"].dropna().tolist():
        if title_similarity(course_name, str(transcript_title)) >= min_similarity:
            return True
    return False


def future_audit_course_ready(row: pd.Series, transcript_data: dict) -> bool:
    if not bool(row.get("Future Audit Snapshot", False)):
        return True

    course_id = str(row.get("Course ID", ""))
    course_name = str(row.get("Course Name", ""))
    match = re.match(r"^([A-Z]{2,5})\s+(\d{3})$", course_id)
    if not match:
        return True

    subject, number = match.groups()
    target_number = int(number)
    if target_number < 200:
        return True

    if transcript_has_equivalent_course(course_id, course_name, transcript_data):
        return True

    subject_rows = transcript_data["courses_df"][
        transcript_data["courses_df"]["Course ID"].str.startswith(f"{subject} ", na=False)
    ]
    subject_numbers = []
    for transcript_code in subject_rows["Course ID"].tolist():
        code_match = re.match(rf"^{re.escape(subject)}\s+(\d{{3}})$", str(transcript_code))
        if code_match:
            subject_numbers.append(int(code_match.group(1)))

    if any(number < target_number for number in subject_numbers):
        return True

    return False


def build_schedule_summary(schedule_df: pd.DataFrame, ai_enabled: bool) -> str:
    if schedule_df.empty:
        return ""

    course_bits = [
        f"{row['Course ID']} ({row['Course Name']})"
        for _, row in schedule_df.iterrows()
    ]
    intro = "AI recommendation" if ai_enabled else "Recommended path"
    return f"{intro}: " + ", ".join(course_bits) + "."


def default_course_reason(row: pd.Series) -> str:
    course_id = str(row.get("Course ID", ""))
    course_name = str(row.get("Course Name", ""))
    block = str(row.get("Requirement Block", ""))
    area = str(row.get("Requirement Area", ""))
    recommended_term = str(row.get("Recommended Term", ""))
    is_elective = bool(row.get("Is Elective Block", False))

    if recommended_term == "Current Term":
        return f"{course_id} is already on the active path for the current term and remains part of the strongest requirement sequence."
    if "DS 496" == course_id:
        return f"{course_id} is the required Data Science capstone and should stay in the graduation plan."
    if is_elective:
        return f"{course_id} helps fill a remaining elective requirement from the current degree path after higher-priority required courses."
    if "Foreign Language" in block or "language" in block.lower():
        return f"{course_id} continues the remaining language/core requirement for the selected degree path."
    if "Data Science" in area or "CS*151, DS*496, IS*358, MA*251, ST*472" in block:
        return f"{course_id} is still needed in the remaining Data Science requirement path."
    return f"{course_id} remains one of the strongest unfinished requirements in the current degree path."


def ensure_reason_coverage(schedule_df: pd.DataFrame, notes: list[dict]) -> list[dict]:
    if schedule_df.empty:
        return notes

    covered_ids = {
        str(item.get("course_id", "")).strip()
        for item in notes
        if isinstance(item, dict) and item.get("course_id")
    }
    augmented = list(notes)
    for _, row in schedule_df.iterrows():
        course_id = str(row.get("Course ID", "")).strip()
        if not course_id or course_id in covered_ids:
            continue
        augmented.append(
            {
                "course_id": course_id,
                "reason": default_course_reason(row),
            }
        )
        covered_ids.add(course_id)
    return augmented


def build_empty_schedule(overlap: dict | None = None) -> pd.DataFrame:
    empty_df = pd.DataFrame()
    overlap = overlap or {"overlap_count": 0, "usable": False}
    empty_df.attrs["catalog_overlap_count"] = overlap["overlap_count"]
    empty_df.attrs["catalog_usable"] = overlap["usable"]
    return empty_df


def infer_block_remaining(row: pd.Series) -> int:
    raw_value = row.get("Block Remaining", None)
    if pd.notna(raw_value):
        try:
            return max(int(raw_value), 1)
        except Exception:
            pass

    block_label = str(row.get("Requirement Block", ""))
    progress_match = re.search(r"(\d+)\s+of\s+(\d+)\s+Courses\s+Completed", block_label, re.I)
    if progress_match:
        completed = int(progress_match.group(1))
        total = int(progress_match.group(2))
        return max(total - completed, 1)

    return 1


def clean_requirement_area_label(area: str) -> str:
    cleaned = normalize_space(area or "")
    replacements = {
        "Persp on Suffering": "University Core",
        "Sci thrh Programmin g": "Data Science Core",
        "Sci thrh Programming": "Data Science Core",
        "Photography": "University Core",
        "Statistics": "Data Science Core",
        "Intellig&Data Mining": "Data Science Core",
        "Multivariate Analysis": "Data Science Core",
        "Matters": "University Core",
    }
    return replacements.get(cleaned, cleaned)


def clean_requirement_block_label(block: str) -> str:
    cleaned = normalize_space(block or "")
    cleaned = re.sub(r"\bFulfi\s*lled\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\b\d+\s+of\s+\d+\s+Courses\s+Completed\.?", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\b\d+\s+of\s+\d+\s+Credits\s+Completed\.?", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\bHide Details\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" .")


def finalize_schedule_output(schedule_df: pd.DataFrame) -> pd.DataFrame:
    if schedule_df.empty:
        return pd.DataFrame()

    output_df = schedule_df[
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
    output_df["Requirement Area"] = output_df["Requirement Area"].apply(clean_requirement_area_label)
    output_df["Requirement Block"] = output_df["Requirement Block"].apply(clean_requirement_block_label)
    output_df["Course Name"] = output_df["Course Name"].apply(clean_course_title)
    output_df.attrs["catalog_overlap_count"] = schedule_df.attrs.get("catalog_overlap_count", 0)
    output_df.attrs["catalog_usable"] = schedule_df.attrs.get("catalog_usable", False)
    return output_df


def sanitized_requirement_block_label(row: pd.Series) -> str:
    block_label = str(row.get("Requirement Block", ""))
    if not bool(row.get("Future Audit Snapshot", False)):
        return block_label

    sanitized = re.sub(r"\bFulfi\s*lled\b", "", block_label, flags=re.I)
    sanitized = re.sub(r"\b\d+\s+of\s+\d+\s+Courses\s+Completed\.?", "", sanitized, flags=re.I)
    sanitized = re.sub(r"\b\d+\s+of\s+\d+\s+Credits\s+Completed\.?", "", sanitized, flags=re.I)
    sanitized = re.sub(r"\s{2,}", " ", sanitized)
    return sanitized.strip(" .")


def select_ai_candidate_window(pending_df: pd.DataFrame) -> pd.DataFrame:
    if pending_df.empty:
        return pending_df

    if "Future Audit Snapshot" in pending_df.columns:
        non_future_df = pending_df[pending_df["Future Audit Snapshot"] != True].copy()
    else:
        non_future_df = pending_df.copy()

    current_term_df = pending_df[pending_df["Recommended Term"] == "Current Term"].copy()
    if current_term_df.empty:
        source_df = non_future_df if not non_future_df.empty else pending_df
        next_term_df = source_df.copy()
        next_term_df["Block Key"] = next_term_df["Requirement Block"].fillna(next_term_df["Course ID"])
        next_term_df = next_term_df.drop_duplicates(subset=["Block Key"]).drop(columns=["Block Key"])
        return next_term_df.head(6).copy()

    remaining_slots = max(0, 6 - len(current_term_df))
    source_df = non_future_df if not non_future_df.empty else pending_df
    next_term_df = source_df[source_df["Recommended Term"] != "Current Term"].copy()
    if not next_term_df.empty:
        next_term_df["Block Key"] = next_term_df["Requirement Block"].fillna(next_term_df["Course ID"])
        next_term_df = next_term_df.drop_duplicates(subset=["Block Key"]).drop(columns=["Block Key"])
    next_term_df = next_term_df.head(remaining_slots).copy()
    candidate_df = pd.concat([current_term_df, next_term_df], ignore_index=True)
    return candidate_df.drop_duplicates(subset=["Course ID", "Requirement Block"])


def select_ranked_schedule(pending_df: pd.DataFrame) -> pd.DataFrame:
    selected_rows = []
    running_credits = 0.0
    block_counts = {}
    selected_course_ids = set()
    for _, row in pending_df.iterrows():
        credits = float(row["Credits"])
        course_id = str(row.get("Course ID", ""))
        block_label = str(row.get("Requirement Block", ""))
        recommended_term = str(row.get("Recommended Term", ""))
        block_limit = row.get("Block Remaining", 1)
        try:
            block_limit = int(block_limit) if pd.notna(block_limit) else 1
        except Exception:
            block_limit = 1
        block_limit = max(block_limit, 1)

        if course_id in selected_course_ids:
            continue
        if recommended_term != "Current Term" and block_counts.get(block_label, 0) >= block_limit:
            continue
        if running_credits + credits > 15:
            continue
        selected_rows.append(row)
        running_credits += credits
        selected_course_ids.add(course_id)
        block_counts[block_label] = block_counts.get(block_label, 0) + 1
        if running_credits >= 15:
            break

    selected_df = pd.DataFrame(selected_rows)
    if selected_df.empty:
        return pd.DataFrame()

    return selected_df.reset_index(drop=True)


def extend_schedule_to_credit_target(
    selected_df: pd.DataFrame,
    source_df: pd.DataFrame,
    min_credits: float = 12.0,
    max_credits: float = 15.0,
) -> pd.DataFrame:
    if selected_df.empty:
        return selected_df

    running_credits = float(selected_df["Credits"].sum())
    if running_credits >= min_credits:
        return selected_df.reset_index(drop=True)

    selected_course_ids = set(selected_df["Course ID"].tolist())
    block_counts = selected_df.groupby("Requirement Block").size().to_dict()
    extra_rows = []

    candidate_df = source_df.copy()
    candidate_df["Elective Fill Priority"] = candidate_df["Is Elective Block"].map({False: 0, True: 1}).fillna(1)
    candidate_df = candidate_df.sort_values(
        by=[
            "Elective Fill Priority",
            "Priority",
            "Snapshot Priority",
            "Requirement Priority",
            "Readiness Priority",
            "Sequence Priority",
            "Term Sort",
            "Level",
            "Course ID",
        ],
        ascending=[True, True, True, True, True, True, True, True, True],
    )

    for _, row in candidate_df.iterrows():
        if running_credits >= min_credits:
            break

        course_id = str(row.get("Course ID", ""))
        block_label = str(row.get("Requirement Block", ""))
        if course_id in selected_course_ids:
            continue

        credits = float(row["Credits"])
        if running_credits + credits > max_credits:
            continue

        block_limit = row.get("Block Remaining", 1)
        try:
            block_limit = int(block_limit) if pd.notna(block_limit) else 1
        except Exception:
            block_limit = 1
        block_limit = max(block_limit, 1)
        if block_counts.get(block_label, 0) >= block_limit:
            continue

        extra_rows.append(row)
        selected_course_ids.add(course_id)
        block_counts[block_label] = block_counts.get(block_label, 0) + 1
        running_credits += credits

    if not extra_rows:
        return selected_df.reset_index(drop=True)

    return pd.concat([selected_df, pd.DataFrame(extra_rows)], ignore_index=True).reset_index(drop=True)


def get_gemini_api_key() -> str:
    session_key = st.session_state.get("gemini_api_key_input", "").strip()
    if session_key:
        return session_key

    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key

    compatibility_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if compatibility_key:
        return compatibility_key

    try:
        secret_key = st.secrets.get("GEMINI_API_KEY", "").strip()
    except Exception:
        secret_key = ""

    if secret_key:
        return secret_key

    try:
        compatibility_secret = st.secrets.get("GOOGLE_API_KEY", "").strip()
    except Exception:
        compatibility_secret = ""

    return compatibility_secret


def get_course_subject(course_code: str) -> str:
    return course_code.split()[0] if course_code else ""


def should_merge_pdf_line(previous_line: str, current_line: str) -> bool:
    if not previous_line or not current_line:
        return False

    previous = previous_line.strip()
    current = current_line.strip()
    if not previous or not current:
        return False

    previous_structural_patterns = [
        r"^(Completed|Com\s*pleted|In[-\s]*Pr\s*ogress|Not Started|Fulfi\s*lled|Fulfilled)\s+[A-Z]{2,4}\*?\d{3}\b",
        r"^(Transfer Equivalency)\s+[A-Z]{2,4}\*?\d{3}\b",
        r"^https?://",
        r"^My Progress\b",
        r"^Page\s+\d+\s+of\s+\d+",
        r"^[-=]{3,}$",
    ]
    if any(re.match(pattern, previous, re.I) for pattern in previous_structural_patterns):
        return False

    structural_patterns = [
        r"^(Fall|Spring|Summer|Winter)\s+\d{2}$",
        r"^(Status|Total|Term|Degree|Major|Catalog|Description|Requirements|Progress|Specializations|Departments|Majors)\b",
        r"^\d+\.\s+",
        r"^[A-Z]\.\s+",
        r"^(Completed|Com\s*pleted|In[-\s]*Pr\s*ogress|Not Started|Fulfi\s*lled|Fulfilled)\b",
        r"^(Transfer Equivalency)\b",
        r"^[A-Z]{2,4}\*?\s*\d{3}\b",
        r"^Page:\s+\d+",
        r"^Page\s+\d+\s+of\s+\d+",
        r"^My Progress\b",
        r"^https?://",
        r"^©\s*\d{4}",
        r"^[-=]{3,}$",
    ]
    if any(re.match(pattern, current, re.I) for pattern in structural_patterns):
        return False

    if previous.endswith((".", "!", "?", ":")):
        return False

    if re.search(r"\b\d+\.\d{2}\s+(?:[A-Z][+-]?|CIP|IP|P|S|U|W|AU)?$", previous):
        return False

    return True


def is_likely_title_continuation(line: str) -> bool:
    cleaned = normalize_space(line)
    if not cleaned:
        return False
    if any(token in cleaned for token in ("http://", "https://", "Page ", "Status Course Grade Term Credits")):
        return False
    if re.match(r"^(Completed|Com\s*pleted|In[-\s]*Pr\s*ogress|Not Started|Fulfi\s*lled|Fulfilled)\b", cleaned, re.I):
        return False
    if re.match(r"^\d+\.\s+(Take|Complete)\b", cleaned, re.I):
        return False
    if re.match(r"^[A-Z]{2,4}\*?\d{3}\b", cleaned):
        return False
    if re.search(r"\b\d{2}/[A-Z]{2}\b|\b\d+\.\d+\b", cleaned):
        return False
    words = cleaned.split()
    return len(words) <= 4 and all(re.match(r"^[A-Za-z&'\-]+$", word) for word in words)


def soften_pdf_line_breaks(text: str) -> str:
    softened_lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if softened_lines and should_merge_pdf_line(softened_lines[-1], line):
            softened_lines[-1] = f"{softened_lines[-1]} {line}".strip()
        else:
            softened_lines.append(line)

    return "\n".join(softened_lines)


def uploaded_pdf_text(uploaded_file) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.getbuffer())
        temp_path = tmp.name

    try:
        with pdfplumber.open(temp_path) as pdf:
            extracted_pages = []
            for page in pdf.pages:
                extracted_pages.append(
                    page.extract_text(x_tolerance=2, y_tolerance=3) or ""
                )
            return soften_pdf_line_breaks("\n".join(extracted_pages))
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
        r"([A-Z]{2,4})\s+(\d{3})\s+([A-Z0-9]{2,3})\s+(.+?)\s+(\d+\.\d{2})(?:\s+([A-Z][+-]?|CIP|IP|P|S|U|W|AU))(?=(?:\s+[A-Z]{2,4}\s+\d{3}\s+[A-Z0-9]{2,3}\s)|\s+Term CA:|\s+Total CA:|$)"
    )

    header_name_match = re.search(r"Name:\s*(.+?)\s+LOYOLA UNIVERSITY MARYLAND", text, re.I)
    if header_name_match:
        name = normalize_space(header_name_match.group(1))

    header_sid_match = re.search(r"I\.D\.No\.:\s*(\d{5,10})", text, re.I)
    if header_sid_match:
        sid = header_sid_match.group(1)

    for line in lines:
        if "NOT FOR OFFICIAL USE" in line or "This may not be a comprehensive" in line:
            continue

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

        for course_match in course_pattern.finditer(line):
            subject, number, section, raw_title, credits, grade = course_match.groups()
            code = normalize_course_code(subject, number)
            course_rows.append(
                {
                    "Course ID": code,
                    "Course Name": clean_course_title(raw_title),
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


def parse_program_profile(audit_text: str, catalog_files, transcript_major: str) -> dict:
    def extract_items(label: str) -> list[str]:
        match = re.search(rf"^{label}:\s*(.+)$", audit_text, re.I | re.M)
        if not match:
            return []
        raw_value = normalize_space(match.group(1))
        if not raw_value:
            return []
        parts = re.split(r"\s*(?:,| and )\s*", raw_value)
        return [normalize_space(part) for part in parts if normalize_space(part)]

    majors = extract_items("Majors")
    specializations = extract_items("Specializations")
    minors = extract_items("Minors")

    catalog_programs = []
    for catalog_file in catalog_files or []:
        catalog_text = uploaded_pdf_text(catalog_file)
        program_match = re.search(r"^Program:\s*(.+)$", catalog_text, re.I | re.M)
        if not program_match:
            continue
        program_name = normalize_space(program_match.group(1))
        program_name = re.sub(r"\s*-\s*Loyola University Maryland.*$", "", program_name, flags=re.I)
        if program_name and program_name not in catalog_programs:
            catalog_programs.append(program_name)

    if not majors and transcript_major and transcript_major != "Unknown":
        majors = [transcript_major]

    display_parts = []
    if majors:
        display_parts.append(", ".join(majors))
    if specializations:
        display_parts.append(", ".join(specializations))
    if minors:
        minor_label = ", ".join(minors)
        if len(minors) == 1:
            display_parts.append(f"Minor: {minor_label}")
        else:
            display_parts.append(f"Minors: {minor_label}")
    if not display_parts and catalog_programs:
        display_parts.extend(catalog_programs[:2])

    return {
        "majors": majors,
        "specializations": specializations,
        "minors": minors,
        "catalog_programs": catalog_programs,
        "display_label": " | ".join(display_parts) if display_parts else "Unknown",
    }


def derive_program_major(audit_text: str, catalog_files, transcript_major: str) -> str:
    return parse_program_profile(audit_text, catalog_files, transcript_major)["display_label"]


def build_completion_state(transcript_data: dict, audit_data: dict, display_major: str, schedule_df: pd.DataFrame | None = None) -> dict:
    earned_credits = float(transcript_data["total"] or 0)
    in_progress_codes = set(transcript_data["in_progress_codes"])
    requirements_df = audit_data["requirements_df"]

    if requirements_df.empty:
        return {"is_complete": False, "message": ""}

    remaining_required_df = requirements_df[
        (requirements_df["Requirement Complete"] != True)
        & (requirements_df["Audit Status"] == "Not Started")
    ].copy()

    has_credit_target = earned_credits >= 111
    has_no_not_started_requirements = remaining_required_df.empty
    has_no_remaining_schedule = schedule_df is None or schedule_df.empty
    major_label = (display_major or "").lower()
    is_data_science_path = "data science" in major_label
    is_capstone_only = (
        is_data_science_path
        and in_progress_codes
        and in_progress_codes.issubset({"DS 496", "IS 358", "IS 420", "SN 104", "ST 472"})
    )

    if has_credit_target and has_no_remaining_schedule:
        return {
            "is_complete": True,
            "message": "Congratulations! Your transcript and selected degree path appear complete enough for graduation review.",
        }

    if has_credit_target and has_no_not_started_requirements and has_no_remaining_schedule:
        return {
            "is_complete": True,
            "message": "Congratulations! Your transcript and audit indicate that your remaining requirements are already satisfied or fully in progress for graduation.",
        }

    if has_credit_target and is_capstone_only and len(in_progress_codes) <= 5 and has_no_remaining_schedule:
        return {
            "is_complete": True,
            "message": "Congratulations! You appear to be at the finish line with only your final in-progress graduation plan remaining.",
        }

    return {"is_complete": False, "message": ""}


def parse_audit(text: str) -> dict:
    lines = [line.rstrip() for line in text.splitlines()]
    requirement_rows = []
    current_section = "Requirements"
    current_block = "Degree Requirement"
    current_block_complete = None
    current_block_remaining = None
    current_block_total = None
    block_order = 0
    language_placeholder_added = False
    section_pattern = re.compile(r"^[A-Z][A-Za-z/&,\-\s]{3,}$")
    course_line_pattern = re.compile(
        r"^(Completed|Com\s*pleted|In[-\s]*Pr\s*ogress|Not Started|Fulfi\s*lled|Fulfilled)\s+([A-Z]{2,4})\*?(\d{3})(?:\s+(.+))?$",
        re.I,
    )
    block_progress_pattern = re.compile(
        r"(\d+)\s+of\s+(\d+)\s+(?:Courses|Credits)?\s*Completed\.?$",
        re.I,
    )

    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue

        if (
            section_pattern.match(line)
            and "Page " not in line
            and "Status Course Grade Term Credits" not in line
            and not any(line.startswith(prefix) for prefix in STATUS_WORDS)
            and len(line.split()) <= 6
        ):
            current_section = normalize_space(line)
            idx += 1
            continue

        if line.startswith("Take ") or re.match(r"^\d+\.\s+(Take|Complete) ", line):
            current_block = normalize_space(line)
            block_order += 1
            current_block_complete = bool(re.search(r"Fulfi\s*lled$", line, re.I))
            current_block_remaining = None
            current_block_total = None
            if (
                "Foreign Language course" in current_block
                and "Intermediate II" in current_block
                and not language_placeholder_added
            ):
                requirement_rows.append(
                    {
                        "Audit Status": "Not Started",
                        "Course ID": "LANG 104",
                        "Course Name": "Intermediate II Language Course",
                        "Audit Term": "",
                        "Requirement Area": current_section,
                        "Requirement Block": current_block,
                        "Requirement Complete": current_block_complete,
                        "Block Remaining": current_block_remaining,
                        "Block Total": current_block_total,
                        "Block Order": block_order,
                        "Is Elective Block": False,
                    }
                )
                language_placeholder_added = True
            idx += 1
            continue

        progress_match = block_progress_pattern.search(line)
        if progress_match:
            completed = int(progress_match.group(1))
            total = int(progress_match.group(2))
            current_block_complete = completed >= total
            current_block_remaining = max(total - completed, 0)
            current_block_total = total
            idx += 1
            continue

        if re.search(r"Fulfi\s*lled$", line, re.I) and "Status Course Grade Term Credits" not in line:
            current_block_complete = True
            current_block = normalize_space(line)
            idx += 1
            continue

        if line == "Not Started":
            current_block_complete = False
            idx += 1
            continue

        match = course_line_pattern.match(line)
        if not match:
            idx += 1
            continue

        status, subject, number, title = match.groups()
        continuation_parts = []
        lookahead = idx + 1
        while lookahead < len(lines):
            next_line = lines[lookahead].strip()
            if not next_line:
                lookahead += 1
                continue
            if (
                "Status Course Grade Term Credits" in next_line
                or next_line.startswith("Take ")
                or re.match(r"^\d+\.\s+(Take|Complete) ", next_line)
                or next_line == "Not Started"
                or any(next_line.startswith(prefix) for prefix in STATUS_WORDS)
                or course_line_pattern.match(next_line)
                or block_progress_pattern.search(next_line)
                or next_line.startswith("https://")
                or next_line.startswith("Page ")
                or (section_pattern.match(next_line) and not is_likely_title_continuation(next_line))
            ):
                break
            continuation_parts.append(next_line)
            lookahead += 1

        if continuation_parts:
            title = normalize_space(f"{title or ''} {' '.join(continuation_parts)}")
            idx = lookahead - 1

        cleaned_title = clean_course_title(title or "")
        if cleaned_title in GRADE_TOKENS:
            idx += 1
            continue
        code = normalize_course_code(subject, number)
        canonical_status = canonicalize_audit_status(status)
        audit_term = parse_audit_term_code(title or "")
        block_label = current_block or "Degree Requirement"
        block_lower = block_label.lower()
        is_elective_block = "choose from" in block_lower or re.search(r"complete\s+\d+\s+courses", block_lower) is not None
        requirement_rows.append(
            {
                "Audit Status": canonical_status,
                "Course ID": code,
                "Course Name": cleaned_title or code,
                "Audit Term": audit_term,
                "Requirement Area": current_section,
                "Requirement Block": block_label,
                "Requirement Complete": current_block_complete,
                "Block Remaining": current_block_remaining,
                "Block Total": current_block_total,
                "Block Order": block_order,
                "Is Elective Block": is_elective_block,
            }
        )
        idx += 1

    requirements_df = pd.DataFrame(requirement_rows)
    if requirements_df.empty:
        return {"requirements_df": requirements_df, "audit_gpa": "N/A"}

    requirements_df = requirements_df.drop_duplicates(subset=["Course ID", "Requirement Block"])
    audit_gpa_match = re.search(r"Cumulative GPA:\s*([\d.]+)", text, re.I)
    audit_gpa = audit_gpa_match.group(1) if audit_gpa_match else "N/A"

    return {"requirements_df": requirements_df, "audit_gpa": audit_gpa}


def extract_course_codes(text: str) -> list[str]:
    codes = []
    for subject, number in re.findall(r"\b([A-Z]{2,4})\*?\s?(\d{3})\b", text or ""):
        code = normalize_course_code(subject, number)
        if code not in codes:
            codes.append(code)
    return codes


def split_embedded_catalog_markers(line: str) -> list[str]:
    expanded = line
    expanded = re.sub(
        r"\s+((?:Freshman|Sophomore|Junior|Senior)\s+Year)\b",
        r"\n\1\n",
        expanded,
        flags=re.I,
    )
    expanded = re.sub(
        r"\s+((?:Fall|Spring|Summer|Winter)\s+Term)\b",
        r"\n\1\n",
        expanded,
        flags=re.I,
    )
    expanded = re.sub(
        r"\s+(Program:\s+)",
        r"\n\1",
        expanded,
        flags=re.I,
    )
    return [normalize_space(part) for part in expanded.splitlines() if normalize_space(part)]


def split_catalog_course_blocks(text: str) -> list[dict]:
    course_header_pattern = re.compile(r"^\s*([A-Z]{2,4})\s+(\d{3})\s*[-:]\s*(.+)$")
    blocks = []
    current_block = None
    current_year = ""
    current_term = ""

    for raw_line in text.splitlines():
        for line in split_embedded_catalog_markers(raw_line):
            year_match = re.match(r"^(Freshman|Sophomore|Junior|Senior)\s+Year$", line, re.I)
            if year_match:
                current_year = year_match.group(1).title()
                continue

            term_match = re.match(r"^(Fall|Spring|Summer|Winter)\s+Term$", line, re.I)
            if term_match:
                current_term = term_match.group(1).title()
                continue

            header_match = course_header_pattern.match(line)
            if header_match:
                subject, number, title = header_match.groups()
                if current_block:
                    blocks.append(current_block)
                current_block = {
                    "course_id": normalize_course_code(subject, number),
                    "title_line": title,
                    "lines": [line],
                    "year": current_year,
                    "term": current_term,
                }
                continue

            if current_block:
                current_block["lines"].append(line)

    if current_block:
        blocks.append(current_block)

    return blocks


def infer_catalog_plan_rank(year_label: str, term_label: str, position: int) -> int | None:
    if not year_label and not term_label:
        return None

    year_map = {
        "Freshman": 0,
        "Sophomore": 1,
        "Junior": 2,
        "Senior": 3,
    }
    term_map = {
        "Fall": 0,
        "Winter": 1,
        "Spring": 2,
        "Summer": 3,
    }
    return (
        year_map.get(year_label, 9) * 100
        + term_map.get(term_label, 9) * 10
        + position
    )


def level_based_catalog_rank(course_id: str) -> int | None:
    match = re.search(r"(\d{3})", str(course_id))
    if not match:
        return None

    number = int(match.group(1))
    if number >= 400:
        return 350
    if number >= 300:
        return 250
    if number >= 200:
        return 150
    if number >= 100:
        return 50
    return None


def apply_catalog_fallback_metadata(entries: OrderedDict) -> None:
    populated_entries = [
        value
        for value in entries.values()
        if value["Catalog Terms"] or value["Catalog Rank"] is not None
    ]

    for value in entries.values():
        if value["Catalog Terms"] and value["Catalog Rank"] is not None:
            continue

        title = str(value.get("Catalog Title", ""))
        best_match = None
        best_score = 0.0
        for reference in populated_entries:
            if reference["Course ID"] == value["Course ID"]:
                continue
            score = title_similarity(title, str(reference.get("Catalog Title", "")))
            if score > best_score:
                best_score = score
                best_match = reference

        if best_match and best_score >= 0.9:
            if not value["Catalog Terms"] and best_match["Catalog Terms"]:
                value["Catalog Terms"] = list(best_match["Catalog Terms"])
            if value["Catalog Rank"] is None and best_match["Catalog Rank"] is not None:
                value["Catalog Rank"] = best_match["Catalog Rank"]

        offering_notes = " | ".join(value.get("Catalog Offering Notes", []))
        title_lower = title.lower()

        if not value["Catalog Terms"]:
            if re.search(r"\bfall only\b", offering_notes, re.I):
                value["Catalog Terms"] = ["Fall"]
            elif re.search(r"\bspring only\b", offering_notes, re.I):
                value["Catalog Terms"] = ["Spring"]
            elif re.search(r"\bsummer only\b", offering_notes, re.I):
                value["Catalog Terms"] = ["Summer"]
            elif "capstone" in title_lower:
                value["Catalog Terms"] = ["Spring"]
            else:
                value["Catalog Terms"] = ["Fall", "Spring"]

        if value["Catalog Rank"] is None:
            if "capstone" in title_lower:
                value["Catalog Rank"] = 380
            else:
                value["Catalog Rank"] = level_based_catalog_rank(value["Course ID"])


def parse_catalog_notes(text: str) -> dict:
    notes_by_course: dict[str, dict[str, list[str]]] = {}

    def ensure_course_entry(course_id: str) -> dict[str, list[str]]:
        if course_id not in notes_by_course:
            notes_by_course[course_id] = {
                "prereqs": [],
                "coreqs": [],
                "offering_notes": [],
                "restrictions": [],
            }
        return notes_by_course[course_id]

    normalized_text = normalize_space(text)
    sentences = re.split(r"(?<=[.])\s+", normalized_text)
    for sentence in sentences:
        if not sentence:
            continue

        prereq_match = re.search(
            r"([A-Z]{2,4}\s?\d{3})\s+is a prerequisite for\s+([A-Z]{2,4}\s?\d{3})",
            sentence,
            re.I,
        )
        if prereq_match:
            prereq_code = normalize_course_code(*re.match(r"([A-Z]{2,4})\s?(\d{3})", prereq_match.group(1), re.I).groups())
            target_code = normalize_course_code(*re.match(r"([A-Z]{2,4})\s?(\d{3})", prereq_match.group(2), re.I).groups())
            entry = ensure_course_entry(target_code)
            if prereq_code not in entry["prereqs"]:
                entry["prereqs"].append(prereq_code)

        coreq_match = re.search(
            r"([A-Z]{2,4}\s?\d{3})\s+is a co(?:-|\s)?requisite for\s+([A-Z]{2,4}\s?\d{3})",
            sentence,
            re.I,
        )
        if coreq_match:
            coreq_code = normalize_course_code(*re.match(r"([A-Z]{2,4})\s?(\d{3})", coreq_match.group(1), re.I).groups())
            target_code = normalize_course_code(*re.match(r"([A-Z]{2,4})\s?(\d{3})", coreq_match.group(2), re.I).groups())
            entry = ensure_course_entry(target_code)
            if coreq_code not in entry["coreqs"]:
                entry["coreqs"].append(coreq_code)

        offering_match = re.search(r"((?:[A-Z]{2,4}\s?\d{3}(?:\s+and\s+)?)+)\s+are offered every other year", sentence, re.I)
        if offering_match:
            for course_code in extract_course_codes(offering_match.group(1)):
                entry = ensure_course_entry(course_code)
                note = "Offered every other year"
                if note not in entry["offering_notes"]:
                    entry["offering_notes"].append(note)

        standing_match = re.search(
            r"([A-Z]{2,4}\s?\d{3})[^.]*\b(junior|senior)\s+standing\b",
            sentence,
            re.I,
        )
        if standing_match:
            course_code = normalize_course_code(*re.match(r"([A-Z]{2,4})\s?(\d{3})", standing_match.group(1), re.I).groups())
            entry = ensure_course_entry(course_code)
            restriction = f"{standing_match.group(2).title()} standing"
            if restriction not in entry["restrictions"]:
                entry["restrictions"].append(restriction)

    return notes_by_course


def interpret_catalog_rule_text(block_text: str) -> dict:
    normalized = normalize_space(block_text)
    prereqs = []
    coreqs = []
    prereq_match = re.search(r"(?:Prerequisite[s]?|Prereq[s]?):\s*(.+)", normalized, re.I)
    if prereq_match:
        prereqs = extract_course_codes(prereq_match.group(1))
    coreq_match = re.search(r"(?:Corequisite[s]?|Coreq[s]?):\s*(.+)", normalized, re.I)
    if coreq_match:
        coreqs = extract_course_codes(coreq_match.group(1))
    restrictions = []
    offering_notes = []
    standing_requirements = []

    if re.search(r"\bjunior standing\b", normalized, re.I):
        restrictions.append("Junior standing")
        standing_requirements.append("Junior standing")
    if re.search(r"\bsenior standing\b", normalized, re.I):
        restrictions.append("Senior standing")
        standing_requirements.append("Senior standing")
    if re.search(r"\bpermission of instructor\b|\bpermission of program director\b", normalized, re.I):
        restrictions.append("Permission required")
    if re.search(r"\bevery other year\b|\balternate years?\b", normalized, re.I):
        offering_notes.append("Offered every other year")
    if re.search(r"\bfall only\b", normalized, re.I):
        offering_notes.append("Fall only")
    if re.search(r"\bspring only\b", normalized, re.I):
        offering_notes.append("Spring only")
    if re.search(r"\bsummer only\b", normalized, re.I):
        offering_notes.append("Summer only")
    if re.search(r"\bor equivalent\b", normalized, re.I):
        restrictions.append("Equivalent course allowed")

    return {
        "prereqs": prereqs,
        "coreqs": coreqs,
        "restrictions": restrictions,
        "offering_notes": offering_notes,
        "standing_requirements": standing_requirements,
        "raw_rule_text": normalized,
    }


def parse_catalogs(catalog_files) -> pd.DataFrame:
    entries = OrderedDict()
    credit_pattern = re.compile(r"(\d+(?:\.\d+)?)\s+credits?", re.I)

    for catalog_file in catalog_files:
        text = uploaded_pdf_text(catalog_file)
        notes_by_course = parse_catalog_notes(text)
        blocks = split_catalog_course_blocks(text)
        for position, block in enumerate(blocks, start=1):
            code = block["course_id"]
            title = strip_catalog_title_noise(block["title_line"])
            block_text = "\n".join(block["lines"])
            credits_match = credit_pattern.search(block_text)
            interpreted = interpret_catalog_rule_text(block_text)
            prereq_codes = []
            prereq_match = re.search(r"Prerequisite[s]?:\s*(.+)$", block_text, re.I)
            if prereq_match:
                prereq_codes = extract_course_codes(prereq_match.group(1))
            block_rank = infer_catalog_plan_rank(block["year"], block["term"], position)
            if code not in entries:
                entries[code] = {
                    "Course ID": code,
                    "Catalog Title": title,
                    "Catalog Credits": float(credits_match.group(1)) if credits_match else 3.0,
                    "Catalog Terms": [],
                    "Catalog Prereqs": [],
                    "Catalog Coreqs": [],
                    "Catalog Restrictions": [],
                    "Catalog Offering Notes": [],
                    "Catalog Rule Text": "",
                    "Catalog Rank": block_rank,
                }
            elif entries[code]["Catalog Rank"] is None and block_rank is not None:
                entries[code]["Catalog Rank"] = block_rank
            if block["term"] and block["term"] not in entries[code]["Catalog Terms"]:
                entries[code]["Catalog Terms"].append(block["term"])
            for prereq_code in prereq_codes:
                if prereq_code not in entries[code]["Catalog Prereqs"]:
                    entries[code]["Catalog Prereqs"].append(prereq_code)
            note_entry = notes_by_course.get(code, {})
            for prereq_code in note_entry.get("prereqs", []):
                if prereq_code not in entries[code]["Catalog Prereqs"]:
                    entries[code]["Catalog Prereqs"].append(prereq_code)
            for coreq_code in note_entry.get("coreqs", []):
                if coreq_code not in entries[code]["Catalog Coreqs"]:
                    entries[code]["Catalog Coreqs"].append(coreq_code)
            for restriction in note_entry.get("restrictions", []):
                if restriction not in entries[code]["Catalog Restrictions"]:
                    entries[code]["Catalog Restrictions"].append(restriction)
            for offering_note in note_entry.get("offering_notes", []):
                if offering_note not in entries[code]["Catalog Offering Notes"]:
                    entries[code]["Catalog Offering Notes"].append(offering_note)
            for prereq_code in interpreted.get("prereqs", []):
                if prereq_code == code:
                    continue
                if prereq_code not in entries[code]["Catalog Prereqs"]:
                    entries[code]["Catalog Prereqs"].append(prereq_code)
            for coreq_code in interpreted.get("coreqs", []):
                if coreq_code == code:
                    continue
                if coreq_code not in entries[code]["Catalog Coreqs"]:
                    entries[code]["Catalog Coreqs"].append(coreq_code)
            for restriction in interpreted.get("restrictions", []):
                if restriction not in entries[code]["Catalog Restrictions"]:
                    entries[code]["Catalog Restrictions"].append(restriction)
            for offering_note in interpreted.get("offering_notes", []):
                if offering_note not in entries[code]["Catalog Offering Notes"]:
                    entries[code]["Catalog Offering Notes"].append(offering_note)
            if interpreted.get("raw_rule_text"):
                entries[code]["Catalog Rule Text"] = interpreted["raw_rule_text"]

    if not entries:
        return pd.DataFrame()

    apply_catalog_fallback_metadata(entries)

    catalog_rows = []
    for value in entries.values():
        catalog_rows.append(
            {
                "Course ID": value["Course ID"],
                "Catalog Title": value["Catalog Title"],
                "Catalog Credits": value["Catalog Credits"],
                "Catalog Terms": ", ".join(value["Catalog Terms"]),
                "Catalog Prereqs": ", ".join(value["Catalog Prereqs"]),
                "Catalog Coreqs": ", ".join(value["Catalog Coreqs"]),
                "Catalog Restrictions": " | ".join(value["Catalog Restrictions"]),
                "Catalog Offering Notes": " | ".join(value["Catalog Offering Notes"]),
                "Catalog Rule Text": value["Catalog Rule Text"],
                "Catalog Rank": value["CatalogRank"] if "CatalogRank" in value else value["Catalog Rank"],
            }
        )
    return pd.DataFrame(catalog_rows)


def recommended_term_name(term_label: str) -> str:
    term_text = str(term_label or "")
    if term_text in {"Current Term", "Next Term"}:
        return ""
    if term_text.endswith("/SP"):
        return "Spring"
    if term_text.endswith("/FA"):
        return "Fall"
    if term_text.endswith("/SU"):
        return "Summer"
    if term_text.endswith("/WI"):
        return "Winter"
    return ""


def catalog_term_available(recommended_term: str, catalog_terms: str) -> bool:
    terms = [normalize_space(part) for part in str(catalog_terms or "").split(",") if normalize_space(part)]
    if not terms:
        return True
    expected_term = recommended_term_name(recommended_term)
    if not expected_term:
        return True
    return expected_term in terms


def catalog_prereqs_satisfied(course_id: str, catalog_prereqs: str, transcript_data: dict, pending_df: pd.DataFrame) -> bool:
    prereq_codes = [normalize_space(part) for part in str(catalog_prereqs or "").split(",") if normalize_space(part)]
    if not prereq_codes:
        return True

    satisfied_codes = set(transcript_data["taken_codes"]) | set(transcript_data["in_progress_codes"])
    candidate_codes = set(pending_df["Course ID"].tolist()) if not pending_df.empty else set()
    current_course_level_match = re.search(r"(\d{3})", str(course_id))
    current_course_level = int(current_course_level_match.group(1)) if current_course_level_match else 999

    for prereq_code in prereq_codes:
        if prereq_code in satisfied_codes:
            continue
        prereq_level_match = re.search(r"(\d{3})", prereq_code)
        prereq_level = int(prereq_level_match.group(1)) if prereq_level_match else 0
        if prereq_code in candidate_codes and prereq_level < current_course_level:
            return False
        return False
    return True


def catalog_coreqs_satisfied(catalog_coreqs: str, transcript_data: dict, pending_df: pd.DataFrame) -> bool:
    coreq_codes = [normalize_space(part) for part in str(catalog_coreqs or "").split(",") if normalize_space(part)]
    if not coreq_codes:
        return True

    satisfied_codes = set(transcript_data["taken_codes"]) | set(transcript_data["in_progress_codes"])
    candidate_codes = set(pending_df["Course ID"].tolist()) if not pending_df.empty else set()
    return all(code in satisfied_codes or code in candidate_codes for code in coreq_codes)


def catalog_restrictions_satisfied(restrictions: str, transcript_data: dict) -> bool:
    restriction_items = [normalize_space(part) for part in re.split(r"\|", str(restrictions or "")) if normalize_space(part)]
    if not restriction_items:
        return True

    earned_credits = float(transcript_data.get("total") or 0)
    program_profile = transcript_data.get("program_profile", {})
    minors = [item.lower() for item in program_profile.get("minors", [])]

    for restriction in restriction_items:
        lowered = restriction.lower()
        if "junior standing" in lowered and earned_credits < 60:
            return False
        if "senior standing" in lowered and earned_credits < 90:
            return False
        if lowered.startswith("minor restriction:"):
            restricted_minor = lowered.replace("minor restriction:", "", 1).strip()
            if any(restricted_minor in minor for minor in minors):
                return False
    return True


def catalog_offering_priority(recommended_term: str, offering_notes: str, catalog_terms: str) -> int:
    if not catalog_term_available(recommended_term, catalog_terms):
        return 1
    if "every other year" in str(offering_notes or "").lower():
        return 1
    return 0


def estimate_program_overlap_priority(row: pd.Series, program_profile: dict) -> int:
    majors = [item.lower() for item in program_profile.get("majors", [])]
    minors = [item.lower() for item in program_profile.get("minors", [])]
    specializations = [item.lower() for item in program_profile.get("specializations", [])]
    haystack = " ".join(
        [
            str(row.get("Requirement Area", "")),
            str(row.get("Requirement Block", "")),
            str(row.get("Course Name", "")),
        ]
    ).lower()

    match_count = 0
    for group in (majors, minors, specializations):
        for item in group:
            item_tokens = [token for token in re.split(r"[\s,/&-]+", item) if len(token) > 2]
            if item_tokens and any(token in haystack for token in item_tokens):
                match_count += 1

    if match_count >= 2:
        return 0
    if match_count == 1:
        return 1
    return 2


def planning_bucket(recommended_term: str) -> int:
    term_text = str(recommended_term or "")
    if term_text == "Current Term":
        return 0
    if term_text in {"Next Term", "26/SP", "26/FA", "26/SU", "26/WI"}:
        return 1
    return 2


def build_local_reference_context(base_dir: str, transcript_data: dict, audit_data: dict) -> list[dict]:
    references = []
    if not base_dir or not os.path.isdir(base_dir):
        return references

    relevant_codes = set(transcript_data.get("taken_codes", set()))
    if not audit_data["requirements_df"].empty:
        relevant_codes |= set(audit_data["requirements_df"]["Course ID"].tolist())

    for filename in sorted(os.listdir(base_dir)):
        lower_name = filename.lower()
        if not lower_name.endswith(".pdf"):
            continue
        if "audit" not in lower_name:
            continue

        path = os.path.join(base_dir, filename)
        try:
            class _Upload:
                def __init__(self, p):
                    self.p = p

                def getbuffer(self):
                    return open(self.p, "rb").read()

            ref_text = uploaded_pdf_text(_Upload(path))
            ref_audit = parse_audit(ref_text)["requirements_df"]
            if ref_audit.empty:
                continue
            ref_codes = set(ref_audit["Course ID"].tolist())
            overlap_count = len(ref_codes & relevant_codes)
            if overlap_count == 0:
                continue
            references.append(
                {
                    "file": filename,
                    "overlap_count": overlap_count,
                    "sample_courses": sorted(list(ref_codes & relevant_codes))[:8],
                }
            )
        except Exception:
            continue

    references.sort(key=lambda item: item["overlap_count"], reverse=True)
    return references[:5]


def catalog_overlap_summary(catalog_df: pd.DataFrame, transcript_data: dict, audit_data: dict) -> dict:
    if catalog_df.empty:
        return {"usable": False, "overlap_count": 0, "overlap_ratio": 0.0}

    audit_codes = set(audit_data["requirements_df"]["Course ID"].tolist()) if not audit_data["requirements_df"].empty else set()
    transcript_codes = set(transcript_data["courses_df"]["Course ID"].tolist()) if not transcript_data["courses_df"].empty else set()
    relevant_codes = audit_codes | transcript_codes
    if not relevant_codes:
        return {"usable": False, "overlap_count": 0, "overlap_ratio": 0.0}

    catalog_codes = set(catalog_df["Course ID"].tolist())
    overlap_count = len(catalog_codes & relevant_codes)
    overlap_ratio = overlap_count / max(len(catalog_codes), 1)

    return {
        "usable": overlap_count >= 3 or overlap_ratio >= 0.25,
        "overlap_count": overlap_count,
        "overlap_ratio": overlap_ratio,
    }


def infer_language_subject(transcript_data: dict) -> str | None:
    if transcript_data["courses_df"].empty:
        return None

    language_like = []
    for code in transcript_data["courses_df"]["Course ID"].tolist():
        match = re.match(r"^([A-Z]{2,4})\s+(\d{3})$", str(code))
        if not match:
            continue
        subject, number = match.groups()
        if int(number) < 200:
            language_like.append(subject)

    if not language_like:
        return None

    in_progress = []
    for code in transcript_data["in_progress_codes"]:
        match = re.match(r"^([A-Z]{2,4})\s+(\d{3})$", str(code))
        if not match:
            continue
        subject, number = match.groups()
        if int(number) < 200:
            in_progress.append(subject)
    if in_progress:
        return sorted(in_progress)[0]

    counts = pd.Series(language_like).value_counts()
    return str(counts.index[0]) if not counts.empty else None


def extract_allowed_subjects(requirement_block: str) -> set[str]:
    block = str(requirement_block or "")
    subjects = set()
    for match in re.finditer(r"\b([A-Z]{2,4})\s*\d{3}\b", block):
        subjects.add(match.group(1))
    for match in re.finditer(r"\b([A-Z]{2,4})\s+\d{3}-", block):
        subjects.add(match.group(1))
    return subjects


def row_matches_block_subject(row: pd.Series) -> bool:
    course_id = str(row.get("Course ID", ""))
    course_name = str(row.get("Course Name", ""))
    requirement_block = str(row.get("Requirement Block", ""))
    subject = get_course_subject(course_id)
    allowed_subjects = extract_allowed_subjects(requirement_block)

    if not allowed_subjects:
        return True

    # Be strict only for placeholder/no-title rows. Real titled rows can still be valid alternates.
    if course_name != course_id:
        return True

    return subject in allowed_subjects


def lock_language_blocks_to_transcript_subject(pending_df: pd.DataFrame, transcript_data: dict) -> pd.DataFrame:
    if pending_df.empty:
        return pending_df

    preferred_language = infer_language_subject(transcript_data)
    if not preferred_language:
        return pending_df

    locked_groups = []
    for requirement_block, group in pending_df.groupby("Requirement Block", dropna=False):
        block_label = str(requirement_block or "").lower()
        is_language_block = "language" in block_label and (
            "104" in block_label or "intermediate ii" in block_label or "200 level" in block_label
        )
        if not is_language_block:
            locked_groups.append(group)
            continue

        preferred_rows = group[group["Course ID"].str.startswith(f"{preferred_language} ", na=False)].copy()
        if not preferred_rows.empty:
            locked_groups.append(preferred_rows)
        else:
            locked_groups.append(group)

    return pd.concat(locked_groups, ignore_index=True) if locked_groups else pending_df


def drop_block_alternatives_covered_by_in_progress(
    pending_df: pd.DataFrame, requirements_df: pd.DataFrame, transcript_data: dict
) -> pd.DataFrame:
    if pending_df.empty or requirements_df.empty:
        return pending_df

    covered_blocks = set()
    in_progress_codes = set(transcript_data["in_progress_codes"])

    for requirement_block, group in requirements_df.groupby("Requirement Block", dropna=False):
        block_remaining = group["Block Remaining"].dropna()
        if block_remaining.empty:
            continue

        try:
            remaining_needed = int(block_remaining.iloc[0])
        except Exception:
            continue

        if remaining_needed <= 0:
            continue

        # Only trust transcript-confirmed in-progress courses here. A newer audit can mark
        # future courses as in progress even when an older transcript has not reached them yet.
        in_progress_count = int(group["Course ID"].isin(in_progress_codes).sum())
        if in_progress_count >= remaining_needed:
            covered_blocks.add(requirement_block)

    if not covered_blocks:
        return pending_df

    return pending_df[
        ~(
            pending_df["Requirement Block"].isin(covered_blocks)
            & (pending_df["Audit Status"] == "Not Started")
            & (pending_df.get("Future Audit Snapshot", False) != True)
        )
    ].copy()


def get_ollama_status() -> dict:
    try:
        request = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
            models = [item.get("name", "") for item in payload.get("models", [])]
            return {
                "ok": response.status == 200,
                "models": models,
                "message": "connected",
            }
    except Exception as exc:
        return {
            "ok": False,
            "models": [],
            "message": str(exc),
        }


def get_gemini_status() -> dict:
    if not get_gemini_api_key():
        return {"ok": False, "message": "Add a Gemini API key in the sidebar or environment."}

    return {"ok": True, "message": f"Ready to use {GEMINI_MODEL} via Gemini API."}


def call_ollama_json(model: str, system_prompt: str, user_payload: dict) -> dict:
    prompt = (
        f"{system_prompt}\n\n"
        "Return valid JSON only. Do not include markdown fences.\n\n"
        f"{json.dumps(user_payload, ensure_ascii=True)}"
    )
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
        return json.loads(payload["response"])


def call_gemini_json(model: str, system_prompt: str, user_payload: dict) -> dict:
    api_key = get_gemini_api_key()
    if not api_key:
        raise RuntimeError("No Gemini API key is available.")

    body = json.dumps(
        {
            "system_instruction": {
                "parts": [{"text": system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                "Return valid JSON only. Do not include markdown fences.\n\n"
                                f"{json.dumps(user_payload, ensure_ascii=True)}"
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{GEMINI_URL}/models/{model}:generateContent?key={api_key}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
        candidate = (payload.get("candidates") or [{}])[0]
        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts).strip()
        return json.loads(text)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini request failed: HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"Gemini request failed: {type(exc).__name__}: {exc}") from exc


def call_ai_json(system_prompt: str, user_payload: dict) -> dict:
    provider = st.session_state.get("ai_provider", "ollama")
    if provider == "gemini":
        return call_gemini_json(
            model=st.session_state.get("gemini_model", GEMINI_MODEL),
            system_prompt=system_prompt,
            user_payload=user_payload,
        )

    return call_ollama_json(
        model=st.session_state.get("ollama_model", OLLAMA_MODEL),
        system_prompt=system_prompt,
        user_payload=user_payload,
    )


def infer_subject_history(option_subjects: list[str], transcript_data: dict) -> dict[str, list[str]]:
    history = {subject: [] for subject in option_subjects}
    for course_code in transcript_data["taken_codes"].union(transcript_data["in_progress_codes"]):
        subject = get_course_subject(course_code)
        if subject in history:
            history[subject].append(course_code)

    for subject in history:
        history[subject] = sorted(history[subject], key=lambda code: int(re.search(r"(\d{3})", code).group(1)))

    return history


def interpret_requirement_blocks_with_ai(pending_df: pd.DataFrame, transcript_data: dict):
    if pending_df.empty:
        return pending_df, []

    blocks = []
    for requirement_block, group in pending_df.groupby("Requirement Block", dropna=False):
        blocks.append(
            {
                "requirement_block": requirement_block,
                "requirement_area": group["Requirement Area"].iloc[0],
                "courses": group[["Course ID", "Course Name", "Audit Status"]].to_dict(orient="records"),
            }
        )

    result = call_ai_json(
        system_prompt=(
            "You are the primary interpreter of a student's remaining degree requirements. "
            "For each requirement block, decide which remaining course options are still logically relevant given the transcript. "
            "Keep continuing sequences the student has already started. "
            "Remove alternate-track options that no longer make sense. "
            "Return only JSON."
        ),
        user_payload={
            "student": {
                "major": transcript_data["major"],
                "completed_courses": sorted(transcript_data["taken_codes"]),
                "in_progress_courses": sorted(transcript_data["in_progress_codes"]),
            },
            "requirement_blocks": blocks,
            "output_schema": {
                "blocks": [
                    {
                        "requirement_block": "string",
                        "keep_course_ids": ["string"],
                        "reason": "string",
                    }
                ]
            },
        },
    )

    notes = []
    kept_frames = []
    block_map = {row["requirement_block"]: row for row in result.get("blocks", [])}
    for requirement_block, group in pending_df.groupby("Requirement Block", dropna=False):
        decision = block_map.get(requirement_block)
        if not decision:
            kept_frames.append(group)
            continue
        keep_ids = set(decision.get("keep_course_ids", []))
        filtered = group[group["Course ID"].isin(keep_ids)].copy() if keep_ids else group.iloc[0:0].copy()
        if filtered.empty:
            filtered = group.copy()
        kept_frames.append(filtered)
        notes.append(
            {
                "requirement_block": requirement_block,
                "reason": decision.get("reason", ""),
                "kept_courses": ", ".join(filtered["Course ID"].tolist()),
            }
        )

    return pd.concat(kept_frames, ignore_index=True), notes


def apply_transcript_track_lock(pending_df: pd.DataFrame, transcript_data: dict) -> pd.DataFrame:
    if pending_df.empty:
        return pending_df

    locked_groups = []

    for requirement_block, group in pending_df.groupby("Requirement Block", dropna=False):
        group = group.copy()
        block_label = str(requirement_block or "")
        block_lower = block_label.lower()
        supports_track_lock = (
            "choose from" in block_lower
            or block_lower.startswith("take 1 ")
            or block_lower.startswith("1. take 1 ")
            or (" or " in block_lower and not block_lower.startswith("take courses"))
        )
        if not supports_track_lock:
            locked_groups.append(group)
            continue

        option_subjects = group["Course ID"].str.extract(r"^([A-Z]{2,4})")[0].dropna().unique().tolist()
        subject_history = infer_subject_history(option_subjects, transcript_data)
        taken_in_block = [code for codes in subject_history.values() for code in codes]

        if len(option_subjects) <= 1 or not taken_in_block:
            locked_groups.append(group)
            continue

        preferred_subject = max(
            option_subjects,
            key=lambda subject: (
                len(subject_history[subject]),
                max(
                    [int(re.search(r"(\d{3})", code).group(1)) for code in subject_history[subject]],
                    default=0,
                ),
            ),
        )

        if preferred_subject and subject_history.get(preferred_subject):
            group = group[group["Course ID"].str.startswith(f"{preferred_subject} ")].copy()

        locked_groups.append(group)

    return pd.concat(locked_groups, ignore_index=True) if locked_groups else pending_df


def refine_track_locks_with_ai(pending_df: pd.DataFrame, transcript_data: dict):
    if pending_df.empty:
        return pending_df, []

    candidate_groups = []
    for requirement_block, group in pending_df.groupby("Requirement Block", dropna=False):
        option_subjects = sorted(group["Course ID"].str.extract(r"^([A-Z]{2,4})")[0].dropna().unique().tolist())
        if len(option_subjects) <= 1:
            continue

        candidate_groups.append(
            {
                "requirement_block": requirement_block,
                "requirement_area": group["Requirement Area"].iloc[0],
                "option_subjects": option_subjects,
                "course_options": group[["Course ID", "Course Name"]].to_dict(orient="records"),
                "subject_history": infer_subject_history(option_subjects, transcript_data),
            }
        )

    if not candidate_groups:
        return pending_df, []

    prompt = {
        "transcript_courses": transcript_data["courses_df"][
            ["Course ID", "Course Name", "Grade", "Term"]
        ].to_dict(orient="records"),
        "requirement_groups": candidate_groups,
        "output_schema": {
            "locks": [
                {
                    "requirement_block": "string",
                    "locked_subject": "string or null",
                    "reason": "string",
                }
            ]
        },
    }

    result = call_ai_json(
        system_prompt=(
            "You determine which subject track a student has already committed to inside a degree requirement block. "
            "Prefer the subject sequence already started on the transcript, even if the exact remaining course numbers differ. "
            "If there is not enough evidence, set locked_subject to null. "
            "Only choose a locked_subject from the provided option_subjects."
        ),
        user_payload=prompt,
    )
    explanations = result.get("locks", [])

    for item in explanations:
        locked_subject = item.get("locked_subject")
        requirement_block = item.get("requirement_block")
        if not locked_subject:
            continue

        pending_df = pending_df[
            (pending_df["Requirement Block"] != requirement_block)
            | (pending_df["Course ID"].str.startswith(f"{locked_subject} "))
        ].copy()

    return pending_df, explanations


def optimize_schedule_with_ai(pending_df: pd.DataFrame, transcript_data: dict):
    if pending_df.empty:
        return pending_df, []

    required_current_ids = pending_df.loc[
        pending_df["Recommended Term"] == "Current Term", "Course ID"
    ].tolist()
    candidates = pending_df[
        [
            "Course ID",
            "Course Name",
            "Credits",
            "Requirement Area",
            "Recommended Term",
            "Audit Status",
            "Catalog Prereqs",
            "Catalog Coreqs",
            "Catalog Restrictions",
            "Catalog Offering Notes",
            "Catalog Terms",
        ]
    ].copy()
    candidates["Requirement Block"] = pending_df.apply(sanitized_requirement_block_label, axis=1)
    if "Future Audit Snapshot" in pending_df.columns:
        candidates["Future Audit Snapshot"] = pending_df["Future Audit Snapshot"].fillna(False)
    candidate_records = candidates.to_dict(orient="records")

    prompt = {
        "student": {
            "major": transcript_data["major"],
            "program_profile": transcript_data.get("program_profile", {}),
            "reference_context": transcript_data.get("reference_context", []),
            "earned_credits": transcript_data["total"],
            "gpa": transcript_data["qpa"],
            "in_progress_courses": sorted(transcript_data["in_progress_codes"]),
            "completed_courses": sorted(transcript_data["taken_codes"]),
        },
        "required_current_course_ids": required_current_ids,
        "candidate_courses": candidate_records,
        "output_schema": {
            "selected_course_ids": ["string"],
            "rationales": [{"course_id": "string", "reason": "string"}],
        },
    }

    result = call_ai_json(
        system_prompt=(
            "You are the main decision engine for a college schedule planner. "
            "Choose the strongest next-semester schedule from the candidate courses. "
            "Keep the total as close to 15 credits as possible without going over, unless fewer than 4 valid courses exist. "
            "Prefer in-progress courses first, prefer coherent subject sequences already started by the student, "
            "and avoid mixing alternate tracks inside the same requirement block unless there is strong evidence that both belong. "
            "If the student has multiple majors, specializations, or minors, preserve a balanced forward path across those programs without double-counting overlapping courses. "
            "When a candidate has Future Audit Snapshot = true, treat it as a reopened requirement from a newer audit snapshot, not as already fulfilled. "
            "Respect catalog prerequisite, co-requisite, restriction, and offering-note hints whenever they are present. "
            "Use the reference_context only as a weak pattern guide for similar stored audits; never let it override the uploaded audit, transcript, or catalog rules. "
            "You MUST include every course in required_current_course_ids in selected_course_ids. "
            "After including required_current_course_ids, keep filling the schedule with the strongest remaining candidates until it reaches a realistic full load. "
            "When the student is on a Data Science path and required courses are already represented, prefer adding a reasonable remaining major elective before stopping at 12 credits."
        ),
        user_payload=prompt,
    )
    raw_selected_ids = result.get("selected_course_ids", [])
    selected_ids = []
    for course_id in required_current_ids + raw_selected_ids:
        if course_id in pending_df["Course ID"].values and course_id not in selected_ids:
            selected_ids.append(course_id)

    if not selected_ids:
        selected_ids = pending_df["Course ID"].tolist()

    selected_df = pending_df[pending_df["Course ID"].isin(selected_ids)].copy()
    selected_df["ai_rank"] = selected_df["Course ID"].apply(
        lambda course_id: selected_ids.index(course_id) if course_id in selected_ids else 999
    )
    selected_df = selected_df.sort_values(by=["ai_rank", "Priority", "Level", "Course ID"]).drop(columns=["ai_rank"])

    running_credits = 0.0
    kept_rows = []
    for _, row in selected_df.iterrows():
        credits = float(row["Credits"])
        if (
            row["Course ID"] not in required_current_ids
            and running_credits + credits > 15
        ):
            continue
        kept_rows.append(row)
        running_credits += credits

    kept_df = pd.DataFrame(kept_rows)
    if kept_df.empty:
        return kept_df, result.get("rationales", [])

    kept_df = extend_schedule_to_credit_target(kept_df, pending_df, min_credits=12.0, max_credits=15.0)
    return kept_df, result.get("rationales", [])


def ai_schedule_is_valid(candidate_df: pd.DataFrame, optimized_df: pd.DataFrame) -> bool:
    if candidate_df.empty or optimized_df.empty:
        return False

    required_current_ids = set(
        candidate_df.loc[candidate_df["Recommended Term"] == "Current Term", "Course ID"].tolist()
    )
    optimized_ids = set(optimized_df["Course ID"].tolist())
    candidate_ids = set(candidate_df["Course ID"].tolist())
    credit_total = float(optimized_df["Credits"].sum()) if "Credits" in optimized_df.columns else 0.0
    has_reasonable_load = credit_total >= 9 or len(candidate_df) <= 2
    return (
        required_current_ids.issubset(optimized_ids)
        and optimized_ids.issubset(candidate_ids)
        and has_reasonable_load
    )


def build_schedule(transcript_data: dict, audit_data: dict, catalog_df: pd.DataFrame, use_ai: bool = False):
    requirements_df = audit_data["requirements_df"]
    if requirements_df.empty:
        return pd.DataFrame(), []

    pending_df = requirements_df.copy()
    latest_transcript_term = get_latest_transcript_term(transcript_data)
    latest_transcript_index = None if latest_transcript_term is None else (latest_transcript_term[0] * 4 + latest_transcript_term[1])
    future_term_mask = pd.Series(False, index=pending_df.index)
    if latest_transcript_term is not None:
        future_term_mask = pending_df.apply(
            lambda row: (
                row["Audit Status"] in {"Completed", "In Progress"}
                and row.get("Audit Term", "")
                and term_index(row["Audit Term"]) is not None
                and row["Course ID"] not in transcript_data["taken_codes"]
                and row["Course ID"] not in transcript_data["in_progress_codes"]
                and not transcript_has_equivalent_course(
                    str(row.get("Course ID", "")),
                    str(row.get("Course Name", "")),
                    transcript_data,
                )
                and row["Audit Term"][-2:] != "OC"
                and term_index(row["Audit Term"]) > latest_transcript_index
            ),
            axis=1,
        )

    pending_mask = (
        pending_df["Audit Status"].isin(["Not Started", "In Progress"])
        | future_term_mask
    )
    incomplete_mask = (pending_df["Requirement Complete"] != True) | future_term_mask
    pending_df = pending_df[incomplete_mask & pending_mask].copy()
    pending_df["Future Audit Snapshot"] = future_term_mask.reindex(pending_df.index, fill_value=False)
    pending_df.loc[pending_df["Future Audit Snapshot"] == True, "Audit Status"] = "Not Started"
    pending_df.loc[pending_df["Future Audit Snapshot"] == True, "Requirement Complete"] = False
    pending_df = pending_df[
        ~pending_df["Audit Status"].astype(str).str.contains(r"Completed|Fulfi\s*lled|Fulfilled", case=False, na=False)
        | pending_df["Course ID"].isin(["LANG 104"])
        | (pending_df["Future Audit Snapshot"] == True)
    ].copy()
    pending_df = pending_df[~pending_df["Course ID"].isin(transcript_data["taken_codes"])].copy()
    pending_df = pending_df.drop_duplicates(subset=["Course ID", "Requirement Block"])
    pending_df = pending_df[pending_df.apply(row_matches_block_subject, axis=1)].copy()
    pending_df = lock_language_blocks_to_transcript_subject(pending_df, transcript_data)
    pending_df = drop_block_alternatives_covered_by_in_progress(pending_df, requirements_df, transcript_data)
    pending_df = apply_transcript_track_lock(pending_df, transcript_data)

    overlap = catalog_overlap_summary(catalog_df, transcript_data, audit_data)
    if pending_df.empty:
        return build_empty_schedule(overlap), []

    if overlap["usable"]:
        pending_df = pending_df.merge(catalog_df, on="Course ID", how="left")
        pending_df["Course Name"] = pending_df["Catalog Title"].fillna(pending_df["Course Name"])
        pending_df["Credits"] = pending_df["Catalog Credits"].fillna(3.0)
    else:
        pending_df["Credits"] = 3.0
        pending_df["Catalog Terms"] = ""
        pending_df["Catalog Prereqs"] = ""
        pending_df["Catalog Coreqs"] = ""
        pending_df["Catalog Restrictions"] = ""
        pending_df["Catalog Offering Notes"] = ""
        pending_df["Catalog Rank"] = pd.NA

    pending_df["Audit Term Index"] = pending_df["Audit Term"].apply(term_index)
    pending_df["Level"] = pending_df["Course ID"].str.extract(r"(\d{3})").astype(float)
    pending_df["Recommended Term"] = pending_df.apply(
        lambda row: (
            "Current Term"
            if (
                row["Course ID"] in transcript_data["in_progress_codes"]
                or (
                    row["Audit Status"] == "In Progress"
                    and not bool(row.get("Future Audit Snapshot", False))
                    and (
                        latest_transcript_index is None
                        or row["Audit Term Index"] is None
                        or row["Audit Term Index"] - latest_transcript_index <= 2
                    )
                )
            )
            else (row["Audit Term"] if row.get("Audit Term", "") else "Next Term")
        ),
        axis=1,
    )
    pending_df["Priority"] = pending_df["Recommended Term"].map({"Current Term": 0, "Next Term": 1}).fillna(1)
    pending_df["Term Sort"] = pending_df["Recommended Term"].apply(
        lambda term: term_sort_key(term) if term_sort_key(term) is not None else (99, 99)
    )
    pending_df["Block Remaining"] = pending_df.apply(infer_block_remaining, axis=1)
    pending_df["Block Order"] = pending_df["Block Order"].fillna(999)
    pending_df["Is Elective Block"] = pending_df["Is Elective Block"].fillna(False)
    pending_df["Block Priority"] = pending_df["Is Elective Block"].map({False: 0, True: 1}).fillna(1)
    pending_df["Snapshot Priority"] = pending_df["Future Audit Snapshot"].map({False: 0, True: 1}).fillna(1)
    pending_df["Requirement Priority"] = pending_df.apply(
        lambda row: requirement_category_priority(
            row["Requirement Area"],
            row["Requirement Block"],
            row["Requirement Complete"],
        ),
        axis=1,
    )
    pending_df["Catalog Term Priority"] = pending_df.apply(
        lambda row: 0 if catalog_term_available(row["Recommended Term"], row.get("Catalog Terms", "")) else 1,
        axis=1,
    )
    pending_df["Catalog Prereq Ready"] = pending_df.apply(
        lambda row: catalog_prereqs_satisfied(
            row["Course ID"],
            row.get("Catalog Prereqs", ""),
            transcript_data,
            pending_df,
        ),
        axis=1,
    )
    pending_df["Catalog Prereq Priority"] = pending_df["Catalog Prereq Ready"].map({True: 0, False: 1}).fillna(0)
    pending_df["Catalog Coreq Priority"] = pending_df.apply(
        lambda row: 0 if catalog_coreqs_satisfied(row.get("Catalog Coreqs", ""), transcript_data, pending_df) else 1,
        axis=1,
    )
    pending_df["Catalog Restriction Priority"] = pending_df.apply(
        lambda row: 0 if catalog_restrictions_satisfied(row.get("Catalog Restrictions", ""), transcript_data) else 1,
        axis=1,
    )
    pending_df["Catalog Offering Priority"] = pending_df.apply(
        lambda row: catalog_offering_priority(
            row["Recommended Term"],
            row.get("Catalog Offering Notes", ""),
            row.get("Catalog Terms", ""),
        ),
        axis=1,
    )
    pending_df["Readiness Priority"] = pending_df.apply(
        lambda row: 0 if future_audit_course_ready(row, transcript_data) else 1,
        axis=1,
    )
    pending_df["Program Overlap Priority"] = pending_df.apply(
        lambda row: estimate_program_overlap_priority(row, transcript_data.get("program_profile", {})),
        axis=1,
    )
    pending_df["Planning Bucket"] = pending_df["Recommended Term"].apply(planning_bucket)
    pending_df["Catalog Rank"] = pd.to_numeric(pending_df["Catalog Rank"], errors="coerce").fillna(999)
    pending_df = pending_df.apply(lambda row: infer_sequenced_course(row, transcript_data), axis=1)
    pending_df = pending_df[
        ~pending_df["Course ID"].isin(
            transcript_data["taken_codes"].union(transcript_data["in_progress_codes"])
        )
    ].copy()
    if pending_df.empty:
        return build_empty_schedule(overlap), []
    pending_df = pending_df.drop_duplicates(subset=["Course ID", "Requirement Block"])
    pending_df["Sequence Priority"] = pending_df["Course ID"].apply(
        lambda code: sequence_gap_priority(code, transcript_data)
    )

    pending_df = pending_df.sort_values(
        by=[
            "Priority",
            "Snapshot Priority",
            "Requirement Priority",
            "Catalog Prereq Priority",
            "Catalog Coreq Priority",
            "Catalog Restriction Priority",
            "Program Overlap Priority",
            "Readiness Priority",
            "Planning Bucket",
            "Sequence Priority",
            "Term Sort",
            "Catalog Offering Priority",
            "Block Priority",
            "Block Remaining",
            "Block Order",
            "Recommended Term",
            "Catalog Rank",
            "Level",
            "Course ID",
        ],
        ascending=[True, True, True, True, True, True, True, True, True, True, True, True, True, True, True, True, True, True, True],
    )

    ranked_schedule_df = select_ranked_schedule(pending_df)
    ranked_schedule_df = extend_schedule_to_credit_target(ranked_schedule_df, pending_df, min_credits=12.0, max_credits=15.0)
    ranked_schedule_df.attrs["catalog_overlap_count"] = overlap["overlap_count"]
    ranked_schedule_df.attrs["catalog_usable"] = overlap["usable"]
    ai_notes = []
    provider = st.session_state.get("ai_provider", "ollama")
    if use_ai:
        try:
            if provider == "gemini":
                ai_candidate_df = select_ai_candidate_window(ranked_schedule_df)
                optimized_df, schedule_notes = optimize_schedule_with_ai(ai_candidate_df, transcript_data)
                if ai_schedule_is_valid(ai_candidate_df, optimized_df):
                    pending_df = extend_schedule_to_credit_target(
                        optimized_df,
                        ranked_schedule_df,
                        min_credits=12.0,
                        max_credits=15.0,
                    )
                    ai_notes.extend(ensure_reason_coverage(pending_df, schedule_notes))
                else:
                    ai_notes.append(
                        {"reason": "AI fallback used deterministic ranking because the AI plan dropped required current-term courses."}
                    )
                    pending_df = ranked_schedule_df
            else:
                pending_df, interpreter_notes = interpret_requirement_blocks_with_ai(pending_df, transcript_data)
                ai_notes.extend(interpreter_notes)

                pending_df, track_lock_notes = refine_track_locks_with_ai(pending_df, transcript_data)
                ai_notes.extend(track_lock_notes)

                optimized_df, schedule_notes = optimize_schedule_with_ai(pending_df, transcript_data)
                if not optimized_df.empty:
                    pending_df = optimized_df
                    ai_notes.extend(schedule_notes)
        except Exception as exc:
            warning_message = f"AI reasoning fallback used: {exc}"
            st.warning(warning_message)
            ai_notes.append({"reason": warning_message})
            pending_df = ranked_schedule_df

    if not use_ai or provider != "gemini":
        pending_df = select_ranked_schedule(pending_df)
    if pending_df.empty:
        return pd.DataFrame(), ai_notes

    pending_df.attrs["catalog_overlap_count"] = overlap["overlap_count"]
    pending_df.attrs["catalog_usable"] = overlap["usable"]
    finalized_df = finalize_schedule_output(pending_df.reset_index(drop=True))
    return finalized_df, ai_notes


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
    provider_options = ["Gemini", "Ollama"]
    provider = st.selectbox("AI provider", provider_options, index=0)
    st.session_state["ai_provider"] = provider.lower()

    if provider == "Gemini":
        gemini_model = st.text_input("Gemini model", value=os.getenv("GEMINI_MODEL", GEMINI_MODEL))
        st.session_state["gemini_model"] = gemini_model
        st.text_input(
            "Gemini API Key",
            type="password",
            key="gemini_api_key_input",
            help="Stored only for this Streamlit session unless you use environment variables or Streamlit secrets.",
        )
    else:
        default_model = os.getenv("OLLAMA_MODEL", OLLAMA_MODEL)
        ollama_model = st.text_input("Ollama model", value=default_model)
        st.session_state["ollama_model"] = ollama_model

    audit_file = st.file_uploader("1. Upload Degree Audit", type="pdf", key="audit")
    transcript_file = st.file_uploader("2. Upload Official Transcript", type="pdf", key="transcript")
    catalog_files = st.file_uploader(
        "3. Upload Course Catalog PDF(s)",
        type="pdf",
        accept_multiple_files=True,
        key="catalogs",
    )
    st.caption("Course catalog upload is required for cleaner titles, credits, and stronger schedule recommendations.")
    ollama_status = get_ollama_status()
    ollama_ready = ollama_status["ok"]
    gemini_status = get_gemini_status()
    gemini_ready = gemini_status["ok"]
    ai_ready = gemini_ready if provider == "Gemini" else ollama_ready
    use_ai = st.toggle(
        "Use AI reasoning",
        value=ai_ready,
        help="Uses the selected AI provider for track selection and final schedule optimization.",
        disabled=not ai_ready,
    )
    if provider == "Gemini":
        st.caption(gemini_status["message"])
    else:
        if not ollama_ready:
            st.caption("Start Ollama locally to enable model-based track selection and schedule optimization.")
        else:
            st.caption(
                f"Ollama connected. Installed models: {', '.join(ollama_status['models'][:6]) or 'none reported'}"
            )
    st.divider()

    if os.path.exists("LoyolaSeal.png"):
        st.image("LoyolaSeal.png", use_container_width=True)


st.title("Loyola AI Schedule Advisor")

if audit_file and transcript_file and catalog_files:
    transcript_text = uploaded_pdf_text(transcript_file)
    audit_text = uploaded_pdf_text(audit_file)

    transcript_data = parse_transcript(transcript_text)
    audit_data = parse_audit(audit_text)
    catalog_df = parse_catalogs(catalog_files or [])
    program_profile = parse_program_profile(audit_text, catalog_files or [], transcript_data["major"])
    display_major = program_profile["display_label"]
    transcript_data["major"] = display_major
    transcript_data["program_profile"] = program_profile
    transcript_data["reference_context"] = build_local_reference_context(
        os.path.dirname(os.path.abspath(__file__)),
        transcript_data,
        audit_data,
    )
    schedule_df, ai_notes = build_schedule(transcript_data, audit_data, catalog_df, use_ai=use_ai)
    completion_state = build_completion_state(transcript_data, audit_data, display_major, schedule_df)

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
        if completion_state["is_complete"]:
            st.subheader("Graduation Status")
            st.success(completion_state["message"])
            st.markdown(
                f"""
                <div class="info-card" style="background-color: rgba(32, 92, 54, 0.92); border-left: 5px solid #5dd67a;">
                    <b>Congratulations, {transcript_data['name']}!</b><br>
                    You have earned {transcript_data['total']} credits and your degree audit appears complete enough for graduation review.
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif schedule_df.empty:
            st.subheader("Recommended Schedule")
            st.success("No remaining courses were detected from the audit.")
        else:
            st.subheader("Recommended Schedule")
            summary_text = build_schedule_summary(schedule_df, use_ai and not bool(ai_notes and "fallback used" in str(ai_notes[0]).lower()))
            if summary_text:
                st.info(summary_text)
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
        st.metric("Transcript GPA", gpa_display)
        st.metric("Audit GPA", audit_gpa)
        st.metric("Transcript Courses Found", len(transcript_data["courses_df"]))
        st.metric("Remaining Audit Courses", 0 if completion_state["is_complete"] else len(schedule_df))
        st.metric("Suggested Credits", int(schedule_df["Credits"].sum()) if not schedule_df.empty else 0)
        st.metric("Catalog Matches", int(schedule_df.attrs.get("catalog_overlap_count", 0)))

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

        with st.expander("Catalog Rule Debug"):
            if not catalog_df.empty:
                debug_columns = [
                    "Course ID",
                    "Catalog Title",
                    "Catalog Terms",
                    "Catalog Prereqs",
                    "Catalog Coreqs",
                    "Catalog Restrictions",
                    "Catalog Offering Notes",
                    "Catalog Rank",
                ]
                present_columns = [column for column in debug_columns if column in catalog_df.columns]
                st.dataframe(
                    catalog_df[present_columns].head(40),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.write("No parsed catalog rules available.")

        with st.expander("Reference Audits"):
            if transcript_data.get("reference_context"):
                st.dataframe(pd.DataFrame(transcript_data["reference_context"]), use_container_width=True, hide_index=True)
            else:
                st.write("No similar stored audit references found.")

        if ai_notes:
            with st.expander("AI Decisions"):
                st.dataframe(pd.DataFrame(ai_notes), use_container_width=True, hide_index=True)

    if schedule_df.attrs.get("catalog_usable"):
        st.caption(
            "Catalog enrichment is active. Next step would be parsing prerequisites and term availability from the catalog."
        )
    else:
        st.warning(
            "The uploaded catalog did not match enough of the audit/transcript course set, so it was ignored for schedule enrichment."
        )

else:
    st.warning("Upload the degree audit, official transcript, and course catalog PDFs to start the analysis.")


st.markdown(
    '<div class="footer">Built by Krishon Pinkins | Loyola University Maryland 2026</div>',
    unsafe_allow_html=True,
)
