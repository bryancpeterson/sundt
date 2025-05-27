# Sundt RAG System

AI-powered search system for Sundt Construction projects and awards data.

## Quick Start

### 1. Download & Setup
```bash
cd sundt-rag
python setup.py
```

### 2. Add API Key
Edit `backend/.env` and add your OpenAI API key:
```
OPENAI_API_KEY=sk-your-actual-key-here
```

### 3. Start the System
```bash
./start.sh     # Mac/Linux
start.bat      # Windows
```

The system will start:
- **Frontend:** http://localhost:3000
- **Backend:** http://localhost:8000

### 4. Collect Data (First Time Only)

Go to the **Admin** page in the frontend and run:

1. **Projects Crawler** - Collects project data from Sundt's website (Takes ~5 minutes)
2. **Awards Crawler** - Collects awards data from Sundt's website  (Takes ~10 seconds)
3. **Generate Embeddings** - Creates vector search index (Takes ~10 seconds)


### 5. Start Querying

Go to the **Search** page and begin querying.

## System Overview

- **Frontend:** React app with search interface
- **Backend:** FastAPI with RAG agents  
- **Search:** Local vector embeddings for semantic search
- **Data:** Web-scraped from Sundt's public website
- **AI:** OpenAI GPT-4.1-mini for query responses

## Requirements

- Python 3.8+
- Node.js 16+
- OpenAI API key

## Troubleshooting

**"No results found"**
- Make sure you ran the crawlers and generated embeddings

**"API key not set"**  
- Add your OpenAI API key to `backend/.env`

**"Module not found"**
- Run `python setup.py` to install dependencies

**Port conflicts**
- Frontend: Edit `frontend/vite.config.js` 
- Backend: Edit `backend/api.py`

---

Built for technical demonstration purposes
