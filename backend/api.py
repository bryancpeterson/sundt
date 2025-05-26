import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from projects_agent import ProjectsAgent
from awards_agent import AwardsAgent
from local_vector_search import LocalVectorSearchEngine

load_dotenv()

app = FastAPI(
    title="Sundt RAG API",
    description="API for querying Sundt Construction projects and awards",
    version="1.0.0"
)

# Allow frontend to call the API during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize our core components
projects_agent = ProjectsAgent()
awards_agent = AwardsAgent()
search_engine = LocalVectorSearchEngine()

# Warn if data files are missing
if not os.path.exists("data/projects.json"):
    print("WARNING: Projects data file not found. Run the crawler first.")

if not os.path.exists("data/awards.json"):
    print("WARNING: Awards data file not found. Run the crawler first.")

# Request/response models
class SearchRequest(BaseModel):
    query: str

class ProjectResponse(BaseModel):
    title: str
    url: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    client: Optional[str] = None
    value: Optional[str] = None
    features: Optional[List[str]] = None

class AwardResponse(BaseModel):
    title: str
    organization: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    date: Optional[str] = None
    year: Optional[str] = None
    image_url: Optional[str] = None

class ProjectsSearchResponse(BaseModel):
    query: str
    response: str
    projects: List[Dict[str, Any]]
    execution_time: float
    success: bool

class AwardsSearchResponse(BaseModel):
    query: str
    response: str
    awards: List[Dict[str, Any]]
    execution_time: float
    success: bool

class BasicSearchResponse(BaseModel):
    query: str
    type: str
    projects: Optional[List[Dict[str, Any]]] = None
    awards: Optional[List[Dict[str, Any]]] = None
    project_count: Optional[int] = None
    award_count: Optional[int] = None

class MetricsResponse(BaseModel):
    projects: Dict[str, Any]
    awards: Dict[str, Any]

class AdminResponse(BaseModel):
    success: bool
    message: str
    count: Optional[int] = None
    projects_count: Optional[int] = None
    awards_count: Optional[int] = None
    type: Optional[str] = None

class SystemStatusResponse(BaseModel):
    success: bool
    data: Dict[str, Any]

# Main endpoints
@app.get("/", tags=["General"])
async def root():
    return {
        "message": "Sundt RAG API is running",
        "status": "online",
        "endpoints": {
            "search": "/search?query={query}&type={type}",
            "projects": "/projects?query={query}",
            "awards": "/awards?query={query}",
            "metrics": "/metrics",
            "admin": {
                "crawl_projects": "/admin/crawl/projects",
                "crawl_awards": "/admin/crawl/awards",
                "generate_embeddings": "/admin/generate-embeddings",
                "status": "/admin/status"
            }
        }
    }

@app.get("/search", response_model=BasicSearchResponse, tags=["Search"])
async def search(
    query: str = Query(..., description="Search query"),
    type: str = Query("all", description="Search type: 'projects', 'awards', or 'all'")
):
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    if type not in ["all", "projects", "awards"]:
        raise HTTPException(status_code=400, detail="Type must be 'all', 'projects', or 'awards'")
    
    results = search_engine.search(query, type)
    return results

@app.post("/projects", response_model=ProjectsSearchResponse, tags=["Projects"])
async def query_projects(request: SearchRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    result = projects_agent.run(request.query)
    
    if not result["success"] and "injection" in result.get("reason", "").lower():
        raise HTTPException(status_code=400, detail="Potential prompt injection detected")
    
    return result

@app.post("/awards", response_model=AwardsSearchResponse, tags=["Awards"])
async def query_awards(request: SearchRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    result = awards_agent.run(request.query)
    
    if not result["success"] and "injection" in result.get("reason", "").lower():
        raise HTTPException(status_code=400, detail="Potential prompt injection detected")
    
    return result

@app.get("/metrics", response_model=MetricsResponse, tags=["Admin"])
async def get_metrics():
    projects_metrics = projects_agent.get_metrics()
    awards_metrics = awards_agent.get_metrics()
    
    return {
        "projects": projects_metrics,
        "awards": awards_metrics
    }

# Admin endpoints for data management
@app.post("/admin/crawl/projects", response_model=AdminResponse, tags=["Admin"])
async def run_projects_crawler():
    try:
        from crawlers.projects_crawler import SundtProjectsCrawler
        
        crawler = SundtProjectsCrawler()
        projects = crawler.crawl()
        
        return {
            "success": True,
            "message": "Projects crawler completed successfully",
            "count": len(projects),
            "type": "projects"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run projects crawler: {str(e)}")

@app.post("/admin/crawl/awards", response_model=AdminResponse, tags=["Admin"])
async def run_awards_crawler():
    try:
        from crawlers.awards_crawler import SundtAwardsCrawler
        
        crawler = SundtAwardsCrawler()
        awards = crawler.crawl()
        
        return {
            "success": True,
            "message": "Awards crawler completed successfully",
            "count": len(awards),
            "type": "awards"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run awards crawler: {str(e)}")

@app.post("/admin/generate-embeddings", response_model=AdminResponse, tags=["Admin"])
async def generate_embeddings():
    try:
        from local_vector_search import LocalVectorSearchEngine
        
        # Force regeneration by creating new instance without cached embeddings
        search_engine_new = LocalVectorSearchEngine(use_cached_embeddings=False)
        
        projects_count = len(search_engine_new.projects)
        awards_count = len(search_engine_new.awards)
        
        # Update global instances to use the new embeddings
        global search_engine
        search_engine = search_engine_new
        
        projects_agent.search_engine = search_engine_new
        awards_agent.search_engine = search_engine_new
        
        return {
            "success": True,
            "message": "Embeddings generated successfully",
            "count": projects_count + awards_count,
            "projects_count": projects_count,
            "awards_count": awards_count,
            "type": "embeddings"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate embeddings: {str(e)}")

@app.get("/admin/status", response_model=SystemStatusResponse, tags=["Admin"])
async def get_system_status():
    try:
        projects_count = len(search_engine.projects) if search_engine.projects else 0
        awards_count = len(search_engine.awards) if search_engine.awards else 0
        
        # Check which data files actually exist
        projects_file_exists = os.path.exists("data/projects.json")
        awards_file_exists = os.path.exists("data/awards.json")
        embeddings_file_exists = os.path.exists("data/local_embeddings.json")
        
        return {
            "success": True,
            "data": {
                "projects_count": projects_count,
                "awards_count": awards_count,
                "files": {
                    "projects_data": projects_file_exists,
                    "awards_data": awards_file_exists,
                    "embeddings": embeddings_file_exists
                },
                "system_status": "online"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system status: {str(e)}")

# Convenience endpoints for browsing data
@app.get("/projects/list", response_model=List[ProjectResponse], tags=["Projects"])
async def list_projects(limit: int = Query(10, description="Maximum number of projects to return")):
    projects = search_engine.projects[:limit]
    return projects

@app.get("/awards/list", response_model=List[AwardResponse], tags=["Awards"])
async def list_awards(limit: int = Query(10, description="Maximum number of awards to return")):
    awards = search_engine.awards[:limit]
    return awards

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)