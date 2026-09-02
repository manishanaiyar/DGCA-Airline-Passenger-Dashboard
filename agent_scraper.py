import sqlite3
import json
import os
import tempfile
from typing import TypedDict

import requests
from pypdf import PdfReader
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

from database import DB_PATH, create_database

load_dotenv()

# Only pages from this section onward (until the next major section) are sent to the LLM.
# This is far more targeted than matching loose keywords like "plf" on every page.
START_SECTION_KEYWORD = "scheduled domestic airlines"
END_SECTION_KEYWORD = "scheduled international"  # first section after the one we want
MAX_SECTION_PAGES = 5  # safety cap so a bad match never sends the whole PDF


class AgentState(TypedDict):
    year_period: str
    raw_text: str
    parsed_data: list


def scrape_daily_data(state: AgentState):
    print("🚀 Fetching directly from DGCA's AWS S3 Bucket...")
    year = state["year_period"]
    s3_url = (
        "https://public-prd-dgca.s3.ap-south-1.amazonaws.com/"
        f"InventoryList/dataReports/aviationDataStatistics/handbookCivilAviation/HANDBOOK%20{year}.pdf"
    )

    print(f"📥 Downloading PDF for {year}...")
    res = requests.get(s3_url, timeout=30)  # SSL verification stays ON
    if res.status_code != 200:
        raise Exception(f"Failed to download from S3 for year '{year}'. Status: {res.status_code}")

    # Unique temp file per run so concurrent users/requests never collide
    tmp_fd, pdf_path = tempfile.mkstemp(suffix=".pdf")
    os.close(tmp_fd)

    try:
        with open(pdf_path, "wb") as f:
            f.write(res.content)

        print("🔍 Locating the relevant section...")
        reader = PdfReader(pdf_path)
        section_pages = []
        collecting = False
        for page in reader.pages:
            page_text = (page.extract_text() or "").lower()

            if not collecting and START_SECTION_KEYWORD in page_text:
                collecting = True

            if collecting:
                section_pages.append(page_text)
                if END_SECTION_KEYWORD in page_text and len(section_pages) > 1:
                    break  # hit the next section, stop here
                if len(section_pages) >= MAX_SECTION_PAGES:
                    break  # safety cap

        if not section_pages:
            raise Exception(
                f"Could not locate the '{START_SECTION_KEYWORD}' section in the PDF — "
                "DGCA may have changed the report layout."
            )

        return {"raw_text": "".join(section_pages)}
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def parse_with_gemini(state: AgentState):
    print("🧠 AI is formatting the data...")
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    prompt = f"""
Extract scheduled domestic airline passenger data from this text for {state['year_period']}.
Return ONLY a raw JSON array — no markdown code fences, no explanation, no extra text before or after.
Each item must have exactly these keys:
"airline_name" (string), "passengers_carried" (integer, no commas),
"yoy_growth_passengers" (float), "plf_percent" (float, 0-100), "yoy_growth_plf" (float).

Text: {state['raw_text']}
"""
    raw_res = llm.invoke(prompt).content.strip()

    # Strip common markdown code-fence wrapping if the model adds it anyway
    cleaned = raw_res
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise Exception(f"Gemini did not return valid JSON — parsing failed. Details: {e}")

    if not isinstance(parsed, list):
        raise Exception("Gemini's JSON was not a list as expected.")

    valid_rows = []
    for row in parsed:
        if not isinstance(row, dict):
            continue

        name = row.get("airline_name")
        passengers = row.get("passengers_carried")
        plf = row.get("plf_percent")
        yoy_pax = row.get("yoy_growth_passengers")
        yoy_plf = row.get("yoy_growth_plf")

        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(passengers, (int, float)) or passengers < 0:
            continue
        if plf is not None and (not isinstance(plf, (int, float)) or not (0 <= plf <= 100)):
            continue
        if yoy_pax is not None and not isinstance(yoy_pax, (int, float)):
            continue
        if yoy_plf is not None and not isinstance(yoy_plf, (int, float)):
            continue

        row["passengers_carried"] = int(passengers)
        valid_rows.append(row)

    if not valid_rows:
        raise Exception("Parsed data failed validation — no valid rows found.")

    return {"parsed_data": valid_rows}


def save_to_database(state: AgentState):
    print("💾 Saving clean data to SQLite...")
    if not os.path.exists(DB_PATH):
        create_database()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    saved = 0
    for row in state["parsed_data"]:
        # UPSERT: naya/corrected data aane par purana row overwrite ho jayega,
        # silently ignore nahi hoga (jaise pehle INSERT OR IGNORE karta tha)
        c.execute('''
            INSERT INTO aviation_data
                (airline_name, passengers_carried, yoy_growth_passengers, plf_percent, yoy_growth_plf, year_period)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(airline_name, year_period) DO UPDATE SET
                passengers_carried = excluded.passengers_carried,
                yoy_growth_passengers = excluded.yoy_growth_passengers,
                plf_percent = excluded.plf_percent,
                yoy_growth_plf = excluded.yoy_growth_plf
        ''', (
            row.get("airline_name"), row.get("passengers_carried"),
            row.get("yoy_growth_passengers"), row.get("plf_percent"),
            row.get("yoy_growth_plf"), state["year_period"]
        ))
        saved += 1
    conn.commit()
    conn.close()
    print(f"✅ Saved/updated {saved} rows for {state['year_period']}")
    return state


workflow = StateGraph(AgentState)
workflow.add_node("scrape", scrape_daily_data)
workflow.add_node("parse", parse_with_gemini)
workflow.add_node("save", save_to_database)
workflow.set_entry_point("scrape")
workflow.add_edge("scrape", "parse")
workflow.add_edge("parse", "save")
workflow.add_edge("save", END)

app = workflow.compile()

if __name__ == "__main__":
    inputs = {"year_period": "2024-25"}
    app.invoke(inputs)
    print("✅ Scrape Complete! Database is updated.")
