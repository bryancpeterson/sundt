import os
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Import our existing agents and search engine
from projects_agent import ProjectsAgent
from awards_agent import AwardsAgent
from local_vector_search import LocalVectorSearchEngine

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Sundt RAG API",
    description="API for querying Sundt Construction projects and awards",
    version="1.0.0"
)

# Add CORS middleware to allow frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize our agents and search engine
projects_agent = ProjectsAgent()
awards_agent = AwardsAgent()
search_engine = LocalVectorSearchEngine()

# Check if data files exist and log warning if not
if not os.path.exists("data/projects.json"):
    print("WARNING: Projects data file not found. Run the crawler first.")

if not os.path.exists("data/awards.json"):
    print("WARNING: Awards data file not found. Run the crawler first.")

# Define request and response models
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

# API Endpoints
@app.get("/", tags=["General"])
async def root():
    """Root endpoint for API verification"""
    return {
        "message": "Sundt RAG API is running",
        "status": "online",
        "endpoints": {
            "search": "/search?query={query}&type={type}",
            "projects": "/projects?query={query}",
            "awards": "/awards?query={query}",
            "metrics": "/metrics"
        }
    }

@app.get("/search", response_model=BasicSearchResponse, tags=["Search"])
async def search(
    query: str = Query(..., description="Search query"),
    type: str = Query("all", description="Search type: 'projects', 'awards', or 'all'")
):
    """
    Basic search for both projects and awards using the search engine directly
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    if type not in ["all", "projects", "awards"]:
        raise HTTPException(status_code=400, detail="Type must be 'all', 'projects', or 'awards'")
    
    # Perform the search
    results = search_engine.search(query, type)
    return results

@app.post("/projects", response_model=ProjectsSearchResponse, tags=["Projects"])
async def query_projects(request: SearchRequest):
    """
    Query the Projects Agent for intelligent responses about Sundt projects
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # Process the query through the Projects Agent
    result = projects_agent.run(request.query)
    
    if not result["success"] and "injection" in result.get("reason", "").lower():
        raise HTTPException(status_code=400, detail="Potential prompt injection detected")
    
    return result

@app.post("/awards", response_model=AwardsSearchResponse, tags=["Awards"])
async def query_awards(request: SearchRequest):
    """
    Query the Awards Agent for intelligent responses about Sundt awards
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # Process the query through the Awards Agent
    result = awards_agent.run(request.query)
    
    if not result["success"] and "injection" in result.get("reason", "").lower():
        raise HTTPException(status_code=400, detail="Potential prompt injection detected")
    
    return result

@app.get("/metrics", response_model=MetricsResponse, tags=["Admin"])
async def get_metrics():
    """
    Get usage metrics for projects and awards agents
    """
    projects_metrics = projects_agent.get_metrics()
    awards_metrics = awards_agent.get_metrics()
    
    return {
        "projects": projects_metrics,
        "awards": awards_metrics
    }

# Additional endpoints for completeness

@app.get("/projects/list", response_model=List[ProjectResponse], tags=["Projects"])
async def list_projects(limit: int = Query(10, description="Maximum number of projects to return")):
    """
    List all projects with optional limit
    """
    # Limit the number of projects to return
    projects = search_engine.projects[:limit]
    return projects

@app.get("/awards/list", response_model=List[AwardResponse], tags=["Awards"])
async def list_awards(limit: int = Query(10, description="Maximum number of awards to return")):
    """
    List all awards with optional limit
    """
    # Limit the number of awards to return
    awards = search_engine.awards[:limit]
    return awards

if __name__ == "__main__":
    import uvicorn
    # Run the FastAPI app with uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)