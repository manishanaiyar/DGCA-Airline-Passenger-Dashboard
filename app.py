import os
import re
import streamlit as st
import sqlite3
import pandas as pd
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

from database import DB_PATH, create_database
from agent_scraper import app as scraper_app

load_dotenv()
st.set_page_config(page_title="DGCA AI Dashboard", layout="wide")

# Auto-initialize the database on first run so a fresh clone doesn't need
# the user to manually run `python database.py` before the UI is usable.
if not os.path.exists(DB_PATH):
    create_database()


@st.cache_data
def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM aviation_data", conn)
    conn.close()
    return df


try:
    df = load_data()
except Exception as e:
    st.error(f"Could not read the database. Details: {e}")
    df = pd.DataFrame(columns=[
        "airline_name", "passengers_carried",
        "yoy_growth_passengers", "plf_percent", "yoy_growth_plf", "year_period"
    ])

# --- ⚙️ FETCH NEW DATA DIRECTLY FROM UI ---
st.sidebar.title("⚙️ Fetch Live Data")
new_year = st.sidebar.text_input("Enter Year (e.g., 2019-20)")

if st.sidebar.button("Get Data"):
    if not new_year.strip():
        st.sidebar.warning("Please enter a year first.")
    elif not re.fullmatch(r"\d{4}-\d{2}", new_year.strip()):
        st.sidebar.error("Enter the year in format YYYY-YY, e.g. 2024-25")
    else:
        with st.spinner(f"AI Agent fetching {new_year} from DGCA S3..."):
            try:
                scraper_app.invoke({"year_period": new_year})
                st.sidebar.success(f"✅ Data for {new_year} added to DB!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error: {e}")

st.sidebar.divider()

# --- 📊 FILTERS ---
st.sidebar.title("📊 Filters")
years = []
if not df.empty:
    years = sorted(df['year_period'].unique().tolist())
    years.insert(0, "All Years")

selected_year = st.sidebar.selectbox("Select Year", years) if years else None

if not years or selected_year == "All Years" or df.empty:
    filtered_df = df
else:
    filtered_df = df[df['year_period'] == selected_year]

# --- MAIN DASHBOARD ---
st.title("✈️ DGCA Airline Passenger Dashboard")

if df.empty:
    st.info("Koi data nahi mila abhi. Sidebar mein saal daal ke 'Get Data' se pehla dataset fetch karo.")

col1, col2 = st.columns(2)

with col1:
    st.subheader(f"Data Table ({selected_year or 'No data'})")
    st.dataframe(filtered_df, hide_index=True, use_container_width=True)

with col2:
    st.subheader("Passengers Carried by Airline")
    if not filtered_df.empty:
        st.bar_chart(filtered_df, x="airline_name", y="passengers_carried")
    else:
        st.info("No data available for this filter.")

st.divider()

# --- AI CHATBOT ---
st.subheader("🤖 Ask AI About This Data")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "llm" not in st.session_state:
    st.session_state.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

# Clear chat history when the selected year changes, so old answers
# don't stay on screen referring to a year that's no longer selected.
if "last_selected_year" not in st.session_state:
    st.session_state.last_selected_year = selected_year
elif st.session_state.last_selected_year != selected_year:
    st.session_state.messages = []
    st.session_state.last_selected_year = selected_year

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).markdown(msg["content"])

if prompt := st.chat_input("E.g., Which airline has the highest PLF?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").markdown(prompt)

    if df.empty:
        response = "Abhi database mein koi data nahi hai — pehle sidebar se kisi saal ka data fetch karo."
        st.chat_message("assistant").markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
    else:
        try:
            # Uses the currently selected/filtered year, not the entire dataset
            context_df = filtered_df if not filtered_df.empty else df
            context = context_df.to_string(index=False)

            sys_prompt = f"""
You are an expert aviation data analyst. Answer the user's query based ONLY on this structured data.

Data Context (Year: {selected_year}):
{context}

User Query: {prompt}

Answer pointwise and keep it short. Use math symbols (+, -, %, =, >, <) where applicable.
If the answer isn't in the data, say so clearly instead of guessing.
"""
            response = st.session_state.llm.invoke(sys_prompt).content
            st.chat_message("assistant").markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
        except Exception as e:
            st.error(f"API Error: {e}")
