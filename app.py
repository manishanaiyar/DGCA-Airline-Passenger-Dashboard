import streamlit as st
import sqlite3
import pandas as pd
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

# IMPORT TUMHARA SCRAPER AGENT
from agent_scraper import app as scraper_app

load_dotenv()
st.set_page_config(page_title="DGCA AI Dashboard", layout="wide")

@st.cache_data
def load_data():
    conn = sqlite3.connect('dgca_dashboard.db')
    df = pd.read_sql_query("SELECT * FROM aviation_data", conn)
    conn.close()
    return df

try:
    df = load_data()
except Exception:
    st.error("Database not found. Run 'python database.py' first.")
    st.stop()

# --- ⚙️ FETCH NEW DATA DIRECTLY FROM UI ---
st.sidebar.title("⚙️ Fetch Live Data")
new_year = st.sidebar.text_input("Enter Year (e.g., 2019-20)")

if st.sidebar.button("Get Data"):
    with st.spinner(f"AI Agent fetching {new_year} from DGCA S3..."):
        try:
            # TRIGGER LANGGRAPH AGENT FROM UI
            scraper_app.invoke({"year_period": new_year})
            st.sidebar.success(f"✅ Data for {new_year} added to DB!")
            st.cache_data.clear() # Clear old cache
            st.rerun() # Auto-refresh UI
        except Exception as e:
            st.sidebar.error("Error: Data file not found on DGCA server.")

st.sidebar.divider()

# --- 📊 FILTERS ---
st.sidebar.title("📊 Filters")
years = []
if not df.empty:
    years = df['year_period'].unique().tolist()
years.insert(0, "All Years")
selected_year = st.sidebar.selectbox("Select Year", years)

if selected_year == "All Years" or df.empty:
    filtered_df = df
else:
    filtered_df = df[df['year_period'] == selected_year]

# --- MAIN DASHBOARD ---
st.title("✈️ DGCA Airline Passenger Dashboard")

col1, col2 = st.columns(2)
with col1:
    st.subheader(f"Data Table ({selected_year})")
    st.dataframe(filtered_df, width="stretch", hide_index=True)
with col2:
    st.subheader("Passengers Carried by Airline")
    if not filtered_df.empty:
        st.bar_chart(filtered_df, x="airline_name", y="passengers_carried")

st.divider()

# --- AI CHATBOT ---
st.subheader("🤖 Ask AI About This Data")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).markdown(msg["content"])

if prompt := st.chat_input("E.g., Which airline has the highest PLF?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").markdown(prompt)
    
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        context = df.to_string(index=False) 
        
        sys_prompt = f"""
        You are an expert aviation data analyst. Answer the user's query based ONLY on this structured data.
        Data Context:
        {context}
        
        User Query: {prompt}
        Answer pointwise and keep it short. Use math symbols (+, -, %, =, >, <) where applicable.
        """
        
        response = llm.invoke(sys_prompt).content
        st.chat_message("assistant").markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
    except Exception as e:
        st.error(f"API Error: {e}")