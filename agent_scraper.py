import sqlite3
import json
import requests
import re
import urllib3
from typing import TypedDict
from pypdf import PdfReader
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

# Ignore SSL warnings for government/S3 buckets
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class AgentState(TypedDict):
    year_period: str
    raw_text: str
    parsed_data: list

# 1. DIRECT S3 DOWNLOAD (No timeouts)
def scrape_daily_data(state: AgentState):
    print("🚀 Fetching directly from DGCA's AWS S3 Bucket...")
    pdf_path = "daily_temp.pdf"
    year = state["year_period"]
    
    s3_url = f"https://public-prd-dgca.s3.ap-south-1.amazonaws.com/InventoryList/dataReports/aviationDataStatistics/handbookCivilAviation/HANDBOOK%20{year}.pdf"
    
    print(f"📥 Downloading PDF for {year}...")
    res = requests.get(s3_url, verify=False, timeout=30)
    
    if res.status_code == 200:
        with open(pdf_path, "wb") as f:
            f.write(res.content)
    else:
        raise Exception(f"Failed to download from S3. Status: {res.status_code}")

    print("🔍 Extracting text...")
    reader = PdfReader(pdf_path)
    text = "".join([page.extract_text() for page in reader.pages[6:9]])
    
    return {"raw_text": text}

# 2. AI PARSING
def parse_with_gemini(state: AgentState):
    print("🧠 AI is formatting the data...")
    # FIX: Updated to -latest to resolve 404 error
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    prompt = f"""
    Extract scheduled domestic airline passenger data from this text for {state['year_period']}.
    Return strictly a JSON array with keys:
    "airline_name" (string), "passengers_carried" (integer, no commas),
    "yoy_growth_passengers" (float), "plf_percent" (float), "yoy_growth_plf" (float).
    Text: {state['raw_text']}
    """
    res = llm.invoke(prompt).content
    
    match = re.search(r'\[.*\]', res, re.DOTALL)
    clean_json = match.group(0) if match else "[]"
    
    return {"parsed_data": json.loads(clean_json)}

# 3. SAVE TO DATABASE
def save_to_database(state: AgentState):
    print("💾 Saving clean data to SQLite...")
    conn = sqlite3.connect('dgca_dashboard.db')
    c = conn.cursor()
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
    conn.commit()
    conn.close()
    return state

# GRAPH SETUP
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