import sqlite3
import json
import os
import re
import requests
from typing import TypedDict

from pypdf import PdfReader
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

load_dotenv()

KEYWORDS = ["passengers carried", "domestic airlines", "passenger load factor", "plf"]


class AgentState(TypedDict):
    year_period: str
    raw_text: str
    parsed_data: list


def scrape_daily_data(state: AgentState):
    print("🚀 Fetching directly from DGCA's AWS S3 Bucket...")
    pdf_path = "daily_temp.pdf"
    year = state["year_period"]
    s3_url = (
        "https://public-prd-dgca.s3.ap-south-1.amazonaws.com/"
        f"InventoryList/dataReports/aviationDataStatistics/handbookCivilAviation/HANDBOOK%20{year}.pdf"
    )

    print(f"📥 Downloading PDF for {year}...")
    res = requests.get(s3_url, timeout=30)  # SSL verification kept ON (verify=False removed)
    if res.status_code != 200:
        raise Exception(f"Failed to download from S3 for year '{year}'. Status: {res.status_code}")

    with open(pdf_path, "wb") as f:
        f.write(res.content)

    print("🔍 Extracting text (dynamic keyword-based page search)...")
    reader = PdfReader(pdf_path)
    matched_pages = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if any(k in page_text.lower() for k in KEYWORDS):
            matched_pages.append(page_text)

    if os.path.exists(pdf_path):
        os.remove(pdf_path)  # cleanup temp file

    if not matched_pages:
        raise Exception("Relevant data pages not found — DGCA PDF format may have changed.")

    return {"raw_text": "".join(matched_pages)}


def parse_with_gemini(state: AgentState):
    print("🧠 AI is formatting the data...")
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    prompt = f"""
Extract scheduled domestic airline passenger data from this text for {state['year_period']}.
Return STRICTLY a JSON array (no markdown, no explanation) with keys:
"airline_name" (string), "passengers_carried" (integer, no commas),
"yoy_growth_passengers" (float), "plf_percent" (float), "yoy_growth_plf" (float).

Text: {state['raw_text']}
"""
    res = llm.invoke(prompt).content
    match = re.search(r'\[.*\]', res, re.DOTALL)
    if not match:
        raise Exception("Gemini did not return valid JSON — parsing failed.")

    parsed = json.loads(match.group(0))

    # Basic sanity validation before saving
    valid_rows = []
    for row in parsed:
        if not row.get("airline_name"):
            continue
        if (row.get("passengers_carried") or 0) < 0:
            continue
        plf = row.get("plf_percent")
        if plf is not None and not (0 <= plf <= 100):
            continue
        valid_rows.append(row)

    if not valid_rows:
        raise Exception("Parsed data failed validation — no valid rows found.")

    return {"parsed_data": valid_rows}


def save_to_database(state: AgentState):
    print("💾 Saving clean data to SQLite...")
    conn = sqlite3.connect('dgca_dashboard.db')
    c = conn.cursor()
    inserted, skipped = 0, 0
    for row in state["parsed_data"]:
        c.execute('''
            INSERT OR IGNORE INTO aviation_data
            (airline_name, passengers_carried, yoy_growth_passengers, plf_percent, yoy_growth_plf, year_period)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            row.get("airline_name"), row.get("passengers_carried"),
            row.get("yoy_growth_passengers"), row.get("plf_percent"),
            row.get("yoy_growth_plf"), state["year_period"]
        ))
        if c.rowcount == 1:
            inserted += 1
        else:
            skipped += 1
    conn.commit()
    conn.close()
    print(f"✅ Inserted: {inserted}, Skipped (duplicate): {skipped}")
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
