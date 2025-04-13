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

class AwardsAgent:
    """Agent specialized for retrieving award information"""
    
    def __init__(self, model_name="gpt-3.5-turbo", temperature=0.2):
        # Initialize search engine
        self.search_engine = LocalVectorSearchEngine()
        
        # Initialize OpenAI LLM
        self.model_name = model_name
        self.temperature = temperature
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature)
        
        # Set up the enhanced prompt template with better instructions
        self.prompt = PromptTemplate(
            input_variables=["query", "award_data"],
            template="""
            You are the Awards Agent for Sundt Construction. Your role is to provide 
            accurate information about awards and recognition received by Sundt.
            
            USER QUERY: {query}
            
            AWARD DATA:
            {award_data}
            
            Instructions:
            1. Focus on directly answering the user's question using only the provided award data
            2. If multiple awards are relevant, organize them chronologically or by significance
            3. Include specific details like organizations, dates, and categories when available
            4. Highlight any patterns in Sundt's recognition (e.g., recurring awards in safety)
            5. If the provided data doesn't contain relevant information to answer the query,
               clearly state that you don't have that specific information
            6. Format your response in a clear, professional manner
            
            RESPONSE:
            """
        )
        
        # Create the runnable chain using modern pattern
        self.chain = (
            {"query": RunnablePassthrough(), "award_data": RunnablePassthrough()}
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
        
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
    
    def _format_award_info(self, award, index):
        """Format award information with all available fields"""
        fields_mapping = {
            "title": "Title",
            "organization": "Organization",
            "category": "Category",
            "award_type": "Award Type",
            "description": "Description",
            "location": "Location",
            "date": "Date",
            "year": "Year",
        }
        
        award_info = [f"AWARD {index}:"]
        
        # Add title first (always)
        award_info.append(f"Title: {award.get('title', 'Untitled')}")
        
        # Add all other available fields in a consistent order
        for field, display_name in fields_mapping.items():
            if field != "title" and field in award and award[field]:
                award_info.append(f"{display_name}: {award[field]}")
        
        # Add project information if available
        if "projects" in award and award["projects"]:
            projects = award.get("projects")
            if isinstance(projects, list):
                project_titles = [p.get("title", "Unnamed Project") for p in projects]
                award_info.append(f"Related Projects: {', '.join(project_titles)}")
        
        return "\n".join(award_info)
    
    def _process_llm_response(self, response, query, awards):
        """Process LLM response to ensure consistency"""
        # Check if response is empty or error
        if not response or len(response.strip()) < 10:
            return f"I couldn't generate a proper response about Sundt awards related to '{query}'. Please try a different query."
            
        # Add a standard prefix for consistency
        prefix = f"Based on Sundt Construction's awards database, here's information about '{query}':\n\n"
        
        # Add award count for transparency
        if awards:
            footer = f"\n\nThis information is based on {len(awards)} relevant awards in Sundt's history."
        else:
            footer = "\n\nI couldn't find specific Sundt awards matching your query in our database."
            
        # Combine parts
        return prefix + response + footer
    
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
                    "awards": [],  # Add empty array to satisfy API validation
                    "success": False,
                    "reason": "No matching awards found"
                }
            else:
                # Format award data for the prompt using the new comprehensive formatter
                award_data = []
                for i, award in enumerate(awards, 1):
                    award_info = self._format_award_info(award, i)
                    award_data.append(award_info)
                
                # Generate response using LLM
                try:
                    # Use the modern chain pattern
                    raw_response = self.chain.invoke({
                        "query": sanitized_query,
                        "award_data": "\n\n".join(award_data)
                    })
                    
                    # With StrOutputParser(), response should always be a string
                    
                    # Process the response for consistency
                    processed_response = self._process_llm_response(raw_response, sanitized_query, awards)
                    
                    result = {
                        "query": sanitized_query,
                        "response": processed_response,
                        "awards": awards,
                        "success": True
                    }
                except Exception as e:
                    print(f"Error processing award query: {e}")
                    result = {
                        "query": sanitized_query,
                        "response": "I encountered an error while processing your request about Sundt awards. Please try again.",
                        "awards": awards,  # Include awards to satisfy API validation
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