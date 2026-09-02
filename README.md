# ✈️ DGCA Airline Passenger Dashboard

An end-to-end GenAI-powered dashboard and data pipeline that scrapes, parses, and visualizes domestic airline passenger data from the Directorate General of Civil Aviation (DGCA) of India.

### 📸 Dashboard Preview

![Dashboard View 1](Screenshot%202026-05-28%20193226.png)
![Dashboard View 2](Screenshot%202026-05-28%20193237.png)

## 🧠 System Pipeline

1. **Data Extraction:** Connects directly to DGCA's AWS S3 bucket to fetch the latest aviation statistics (PDF).
2. **AI Agent Parsing:** Utilizes Gemini (`gemini-2.5-flash`) to parse unstructured PDF text into clean, structured JSON format, with basic sanity validation before saving.
3. **Database Storage:** Safely stores the extracted statistics into a lightweight SQLite database.
4. **Dashboard UI:** A Streamlit frontend for dynamic data filtering and visualization.
5. **Contextual AI Chatbot:** An integrated Gemini-powered assistant that answers questions based on the currently selected year's data.

## 🛠️ Tech Stack

- **Frontend:** Streamlit
- **Backend Agent:** LangChain, LangGraph
- **LLM:** Google Gemini 2.5 Flash
- **Database:** SQLite
- **Data Extraction:** Requests, PyPDF

## 🚀 How to Run Locally

1. **Clone the repository**

```bash
git clone https://github.com/manishanaiyar/DGCA-Airline-Passenger-Dashboard.git
cd DGCA-Airline-Passenger-Dashboard
```

2. **Create a virtual environment and install dependencies**

```bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Set up your environment variables**

Copy `.env.example` to `.env` and add your own Gemini API key:

```bash
cp .env.example .env
```

```text
GOOGLE_API_KEY=your_google_api_key_here
```

4. **Run the dashboard**

```bash
streamlit run app.py
```

The database schema is created automatically on first run if `dgca_dashboard.db` doesn't exist yet — you don't need to run anything manually. If you prefer to create it explicitly (e.g. before running the scraper standalone), you can still do:

```bash
python database.py
```

5. **(Optional) Fetch new year data from the command line**

```bash
python agent_scraper.py
```

## ⚠️ Notes

- Never commit your real `.env` file or API key — only `.env.example` is tracked.
- The scraper depends on DGCA's S3 file naming convention (`HANDBOOK <year>.pdf`); if DGCA changes this, the download step will fail with a clear error.
- LLM-parsed data goes through validation (type checks, non-empty airline name, non-negative passengers, PLF between 0–100) before being saved, but you should still spot-check results against the source PDF.
- Re-fetching a year that already exists in the database **updates** that year's rows (upsert) instead of silently ignoring the new data.
- `requirements.txt` uses minimum-version pins (`>=`) for readability. For guaranteed reproducibility (e.g. before deploying), run `pip freeze > requirements.txt` in your working virtual environment and commit exact `==` versions instead.
