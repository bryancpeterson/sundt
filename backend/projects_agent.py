import os
import json
import re
from datetime import datetime
import time
from typing import Dict, Any, List
from local_vector_search import LocalVectorSearchEngine
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from dotenv import load_dotenv

# Load environment variables from .env file (contains OPENAI_API_KEY)
load_dotenv()

# Fix HuggingFace tokenizers parallelism warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

class ProjectsAgent:
    """Agent specialized for retrieving project information"""
    
    def __init__(self, model_name="gpt-3.5-turbo", temperature=0.2):
        # Initialize search engine
        self.search_engine = LocalVectorSearchEngine()
        
        # Initialize OpenAI LLM
        self.model_name = model_name
        self.temperature = temperature
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature)
        
        # Set up the enhanced prompt template with better instructions
        self.prompt = PromptTemplate(
            input_variables=["query", "project_data"],
            template="""
            You are the Projects Agent for Sundt Construction. Your role is to provide 
            accurate information about Sundt's past and current construction projects.
            
            USER QUERY: {query}
            
            PROJECT DATA:
            {project_data}
            
            Instructions:
            1. Focus on directly answering the user's question using only the provided project data
            2. If multiple projects are relevant, compare them and highlight key similarities or differences
            3. Include specific details like locations, values, delivery methods, and features when available
            4. If the data doesn't contain information to answer the query, clearly state that
            5. Format your response in a clear, professional manner
            
            RESPONSE:
            """
        )
        
        # Create the runnable chain using modern pattern
        self.chain = (
            {"query": RunnablePassthrough(), "project_data": RunnablePassthrough()}
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
        
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
    
    def _format_project_info(self, project, index):
        """Format project information with all available fields"""
        fields_mapping = {
            "title": "Title",
            "location": "Location",
            "client": "Client", 
            "construction_value": "Construction Value",
            "value": "Value",  # Fallback if construction_value isn't present
            "delivery_method": "Delivery Method",
            "year_completed": "Year Completed",
            "description": "Description",
            "overview": "Overview",  # Fallback if description isn't present
        }
        
        project_info = [f"PROJECT {index}:"]
        
        # Add title first (always)
        project_info.append(f"Title: {project.get('title', 'Untitled')}")
        
        # Add all other available fields in a consistent order
        for field, display_name in fields_mapping.items():
            if field != "title" and field in project and project[field]:
                project_info.append(f"{display_name}: {project[field]}")
        
        # Handle lists like features and specialties
        for list_field in ["features", "specialties"]:
            if list_field in project and project[list_field]:
                items = project[list_field]
                formatted_items = ", ".join(items) if isinstance(items, list) else items
                field_name = list_field.title()
                project_info.append(f"{field_name}: {formatted_items}")
        
        return "\n".join(project_info)
    
    def _process_llm_response(self, response, query, projects):
        """Process LLM response to ensure consistency"""
        # Check if response is empty or error
        if not response or len(response.strip()) < 10:
            return f"I couldn't generate a proper response about Sundt projects related to '{query}'. Please try a different query."
            
        # Add a standard prefix for consistency
        prefix = f"Based on Sundt Construction's project database, here's information about '{query}':\n\n"
        
        # Add project count for transparency
        if projects:
            footer = f"\n\nThis information is based on {len(projects)} relevant Sundt projects."
        else:
            footer = "\n\nI couldn't find specific Sundt projects matching your query in our database."
            
        # Combine parts
        return prefix + response + footer
    
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
                    "projects": [],  # Add empty array to satisfy API validation
                    "success": False,
                    "reason": "No matching projects found"
                }
            else:
                # Format project data for the prompt using the new comprehensive formatter
                project_data = []
                for i, project in enumerate(projects, 1):
                    project_info = self._format_project_info(project, i)
                    project_data.append(project_info)
                
                # Generate response using LLM
                try:
                    # Use the modern chain pattern
                    raw_response = self.chain.invoke({
                        "query": sanitized_query,
                        "project_data": "\n\n".join(project_data)
                    })
                    
                    # With StrOutputParser(), response should always be a string
                    
                    # Process the response for consistency
                    processed_response = self._process_llm_response(raw_response, sanitized_query, projects)
                    
                    result = {
                        "query": sanitized_query,
                        "response": processed_response,
                        "projects": projects,
                        "success": True
                    }
                except Exception as e:
                    print(f"Error processing project query: {e}")
                    result = {
                        "query": sanitized_query,
                        "response": "I encountered an error while processing your request about Sundt projects. Please try again.",
                        "projects": projects,  # Include projects to satisfy API validation
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