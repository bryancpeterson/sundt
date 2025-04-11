import os
import json
import re
from datetime import datetime
import time
from typing import Dict, Any, List
from local_vector_search import LocalVectorSearchEngine
from langchain.prompts import PromptTemplate
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from dotenv import load_dotenv

# Load environment variables from .env file (contains OPENAI_API_KEY)
load_dotenv()

class ProjectsAgent:
    """Agent specialized for retrieving project information"""
    
    def __init__(self, model_name="gpt-3.5-turbo", temperature=0.2):
        # Initialize search engine
        self.search_engine = LocalVectorSearchEngine()

        
        # Initialize OpenAI LLM
        self.model_name = model_name
        self.temperature = temperature
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature)
        
        # Set up the prompt template
        self.prompt_template = PromptTemplate(
            input_variables=["query", "project_data"],
            template="""
            You are the Projects Agent for Sundt Construction. Your role is to provide 
            accurate information about Sundt's past construction projects.
            
            USER QUERY: {query}
            
            PROJECT DATA:
            {project_data}
            
            Based on the information provided, respond to the user's query about Sundt's projects.
            Present the information in a clear, concise, and helpful manner.
            If the provided data doesn't contain relevant information to answer the query,
            say that you don't have that specific information about Sundt's projects.
            
            RESPONSE:
            """
        )
        
        # Create the chain
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt_template)
        
        # Set up metrics tracking
        self.metrics_file = os.path.join("data", "projects_agent_metrics.json")
        self.metrics = self._load_metrics()
    
    def _load_metrics(self) -> Dict[str, Any]:
        """Load metrics from file or initialize if not exists"""
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return self._initialize_metrics()
        else:
            return self._initialize_metrics()
    
    def _initialize_metrics(self) -> Dict[str, Any]:
        """Initialize empty metrics structure"""
        return {
            "total_queries": 0,
            "query_times": [],
            "injection_attempts": [],
            "queries_by_date": {},
            "popular_terms": {}
        }
    
    def _update_metrics(self, query: str, execution_time: float, 
                       is_injection: bool = False) -> None:
        """Update metrics with query information"""
        # Load latest metrics
        self.metrics = self._load_metrics()
        
        # Get today's date as string
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Update total queries
        self.metrics["total_queries"] += 1
        
        # Update query times (keep the last 100)
        self.metrics["query_times"].append(execution_time)
        if len(self.metrics["query_times"]) > 100:
            self.metrics["query_times"] = self.metrics["query_times"][-100:]
        
        # Log injection attempts
        if is_injection:
            self.metrics["injection_attempts"].append({
                "query": query,
                "date": today
            })
        
        # Update date-based metrics
        if today not in self.metrics["queries_by_date"]:
            self.metrics["queries_by_date"][today] = 0
        self.metrics["queries_by_date"][today] += 1
        
        # Update popular terms (simple word frequency)
        words = re.findall(r'\b\w+\b', query.lower())
        for word in words:
            if len(word) > 3:  # Only count words with more than 3 characters
                if word not in self.metrics["popular_terms"]:
                    self.metrics["popular_terms"][word] = 0
                self.metrics["popular_terms"][word] += 1
        
        # Save updated metrics
        self._save_metrics()
    
    def _save_metrics(self) -> None:
        """Save metrics to file"""
        try:
            os.makedirs(os.path.dirname(self.metrics_file), exist_ok=True)
            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                json.dump(self.metrics, f, indent=2)
        except Exception as e:
            print(f"Error saving metrics: {e}")
    
    def _sanitize_input(self, query: str) -> tuple:
        """
        Sanitize user input to prevent prompt injection
        Returns tuple of (sanitized_query, is_injection)
        """
        # Check for common prompt injection patterns
        injection_patterns = [
            r'ignore previous instructions',
            r'disregard (?:all|previous)',
            r'forget (?:all|your|previous)',
            r'new prompt:',
            r'system prompt:',
            r'new instructions:',
            r'you are now',
            r'you will be',
            r'your new role',
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                # Don't modify the query for metrics but flag as injection
                return (query, True)
        
        # Basic sanitization
        sanitized = re.sub(r'[^\w\s\.,\-\?:;\'\"()]', ' ', query)
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        return (sanitized, False)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return self._load_metrics()
    
    def run(self, query: str) -> Dict[str, Any]:
        """Process a project-related query"""
        start_time = time.time()
        
        # Sanitize input
        sanitized_query, is_injection = self._sanitize_input(query)
        
        if is_injection:
            result = {
                "query": query,
                "response": "I can only provide information about Sundt Construction projects. Please rephrase your query.",
                "success": False,
                "reason": "Potential prompt injection detected"
            }
        else:
            # Search for relevant projects
            search_results = self.search_engine.search(sanitized_query, "projects", limit=5)
            projects = search_results.get("projects", [])
            
            if not projects:
                result = {
                    "query": sanitized_query,
                    "response": "I couldn't find any Sundt Construction projects matching your query. Would you like to try a different search term?",
                    "success": False,
                    "reason": "No matching projects found"
                }
            else:
                # Format project data for the prompt
                project_data = []
                for i, project in enumerate(projects, 1):
                    project_info = [f"PROJECT {i}:"]
                    project_info.append(f"Title: {project.get('title', 'Untitled')}")
                    
                    if "description" in project:
                        project_info.append(f"Description: {project.get('description')}")
                    elif "overview" in project:
                        project_info.append(f"Overview: {project.get('overview')}")
                    
                    for field in ["location", "client", "value"]:
                        if field in project:
                            project_info.append(f"{field.title()}: {project.get(field)}")
                    
                    if "features" in project and project["features"]:
                        features = project.get("features")
                        features_text = ", ".join(features) if isinstance(features, list) else features
                        project_info.append(f"Features: {features_text}")
                    
                    project_info.append("")
                    project_data.append("\n".join(project_info))
                
                # Generate response using LLM
                try:
                    response = self.chain.run(query=sanitized_query, project_data="\n".join(project_data))
                    
                    result = {
                        "query": sanitized_query,
                        "response": response,
                        "projects": projects,
                        "success": True
                    }
                except Exception as e:
                    result = {
                        "query": sanitized_query,
                        "response": "I encountered an error while processing your request about Sundt projects. Please try again.",
                        "success": False,
                        "reason": str(e)
                    }
        
        # Calculate execution time
        execution_time = time.time() - start_time
        result["execution_time"] = execution_time
        
        # Update metrics
        self._update_metrics(query, execution_time, is_injection)
        
        return result


# Example usage for testing
if __name__ == "__main__":
    # Create a .env file with OPENAI_API_KEY=your_api_key before running
    projects_agent = ProjectsAgent()
    
    # Test queries
    test_queries = [
        "Tell me about water treatment projects",
        "What bridge projects has Sundt completed?",
        "Show me hospital construction projects in Arizona"
    ]
    
    for query in test_queries:
        print(f"\nQUERY: {query}")
        result = projects_agent.run(query)
        
        print(f"Success: {result['success']}")
        print(f"Execution time: {result['execution_time']:.2f} seconds")
        print("\nRESPONSE:")
        print(result["response"])
        print("\n" + "="*50)