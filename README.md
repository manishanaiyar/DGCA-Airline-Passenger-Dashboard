# ✈️ DGCA Airline Passenger Dashboard

An end-to-end GenAI-powered dashboard and data pipeline that scrapes, parses, and visualizes domestic airline passenger data from the Directorate General of Civil Aviation (DGCA) of India. 

### 📸 Dashboard Preview
![Dashboard View 1](Screenshot%202026-05-28%20193226.png)
![Dashboard View 2](Screenshot%202026-05-28%20193237.png)

## 🧠 System Pipeline
1. **Data Extraction:** Connects directly to DGCA's AWS S3 bucket to fetch the latest aviation statistics (PDF).
2. **AI Agent Parsing:** Utilizes Gemini (`gemini-2.5-flash`) to parse unstructured PDF text into clean, structured JSON format.
3. **Database Storage:** Safely stores the extracted statistics into a lightweight SQLite database.
4. **Dashboard UI:** A Streamlit frontend for dynamic data filtering and visualization.
5. **Contextual AI Chatbot:** An integrated Gemini-powered assistant that answers questions based purely on the structured database context.

## 🛠️ Tech Stack
* **Frontend:** Streamlit
* **Backend Agent:** LangChain, LangGraph
* **LLM:** Google Gemini 2.5 Flash
* **Database:** SQLite
* **Data Extraction:** Requests, PyPDF

## 🚀 How to Run Locally

1. **Clone the repository**
   ```bash
   git clone [https://github.com/your-username/DGCA-Airline-Passenger-Dashboard.git](https://github.com/your-username/DGCA-Airline-Passenger-Dashboard.git)
   cd DGCA-Airline-Passenger-Dashboard
