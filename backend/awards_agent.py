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

class AwardsAgent:
    """Agent specialized for retrieving award information"""
    
    def __init__(self, model_name="gpt-3.5-turbo", temperature=0.2):
        # Initialize search engine
        self.search_engine = LocalVectorSearchEngine()
        
        # Initialize OpenAI LLM
        self.model_name = model_name
        self.temperature = temperature
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature)
        
        # Set up the prompt template
        self.prompt_template = PromptTemplate(
            input_variables=["query", "award_data"],
            template="""
            You are the Awards Agent for Sundt Construction. Your role is to provide 
            accurate information about awards and recognition received by Sundt.
            
            USER QUERY: {query}
            
            AWARD DATA:
            {award_data}
            
            Based on the information provided, respond to the user's query about Sundt's awards.
            Present the information in a clear, concise, and helpful manner.
            If the provided data doesn't contain relevant information to answer the query,
            say that you don't have that specific information about Sundt's awards.
            
            RESPONSE:
            """
        )
        
        # Create the chain
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt_template)
        
        # Set up metrics tracking
        self.metrics_file = os.path.join("data", "awards_agent_metrics.json")
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
        """Process an award-related query"""
        start_time = time.time()
        
        # Sanitize input
        sanitized_query, is_injection = self._sanitize_input(query)
        
        if is_injection:
            result = {
                "query": query,
                "response": "I can only provide information about Sundt Construction awards. Please rephrase your query.",
                "success": False,
                "reason": "Potential prompt injection detected"
            }
        else:
            # Search for relevant awards
            search_results = self.search_engine.search(sanitized_query, "awards", limit=5)
            awards = search_results.get("awards", [])
            
            if not awards:
                result = {
                    "query": sanitized_query,
                    "response": "I couldn't find any Sundt Construction awards matching your query. Would you like to try a different search term?",
                    "success": False,
                    "reason": "No matching awards found"
                }
            else:
                # Format award data for the prompt
                award_data = []
                for i, award in enumerate(awards, 1):
                    award_info = [f"AWARD {i}:"]
                    award_info.append(f"Title: {award.get('title', 'Untitled')}")
                    
                    for field in ["organization", "category", "award_type", "description", "location"]:
                        if field in award and award[field]:
                            award_info.append(f"{field.title()}: {award.get(field)}")
                    
                    # Add date/year if available
                    if "date" in award:
                        award_info.append(f"Date: {award.get('date')}")
                    elif "year" in award:
                        award_info.append(f"Year: {award.get('year')}")
                    
                    # Add project information if available
                    if "projects" in award and award["projects"]:
                        projects = award.get("projects")
                        if isinstance(projects, list):
                            project_titles = [p.get("title", "Unnamed Project") for p in projects]
                            award_info.append(f"Related Projects: {', '.join(project_titles)}")
                    
                    award_info.append("")
                    award_data.append("\n".join(award_info))
                
                # Generate response using LLM
                try:
                    response = self.chain.run(query=sanitized_query, award_data="\n".join(award_data))
                    
                    result = {
                        "query": sanitized_query,
                        "response": response,
                        "awards": awards,
                        "success": True
                    }
                except Exception as e:
                    result = {
                        "query": sanitized_query,
                        "response": "I encountered an error while processing your request about Sundt awards. Please try again.",
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
    awards_agent = AwardsAgent()
    
    # Test queries
    test_queries = [
        "What safety awards has Sundt received?",
        "Tell me about Build America awards",
        "Has Sundt won any ENR awards in 2022?"
    ]
    
    for query in test_queries:
        print(f"\nQUERY: {query}")
        result = awards_agent.run(query)
        
        print(f"Success: {result['success']}")
        print(f"Execution time: {result['execution_time']:.2f} seconds")
        print("\nRESPONSE:")
        print(result["response"])
        print("\n" + "="*50)