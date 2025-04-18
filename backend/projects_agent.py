import os
import json
import re
import time
import random
from datetime import datetime
from typing import Dict, Any, List, Optional
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
    
    def _prepare_context(self, projects, query, max_tokens=3500):
        """Dynamically prepare context based on token count and relevance"""
        context = []
        token_count = 0
        
        # Prioritize projects based on relevance score
        sorted_projects = sorted(projects, key=lambda x: x.get('_score', 0), reverse=True)
        
        for i, project in enumerate(sorted_projects, 1):
            # Format the project info
            project_info = self._format_project_info(project, i)
            
            # Estimate token count (approximation: 1 token ≈ 4 chars in English)
            estimated_tokens = len(project_info) // 4
            
            # Check if adding this would exceed our limit
            if token_count + estimated_tokens > max_tokens:
                # Try a condensed version for important projects
                if i <= 3:  # First 3 projects are most relevant
                    condensed_info = self._format_condensed_project(project, i)
                    condensed_tokens = len(condensed_info) // 4
                    
                    if token_count + condensed_tokens <= max_tokens:
                        context.append(condensed_info)
                        token_count += condensed_tokens
                continue
                
            # Add the full project info
            context.append(project_info)
            token_count += estimated_tokens
        
        # If we couldn't add any projects (very unlikely), add at least one in condensed form
        if not context and projects:
            condensed_info = self._format_condensed_project(projects[0], 1)
            context.append(condensed_info)
        
        return "\n\n".join(context)
    
    def _format_condensed_project(self, project, index):
        """Create a condensed version of project info with only essential fields"""
        # Include only the most important fields for condensed view
        essential_fields = ["title", "location", "client", "construction_value", "value"]
        
        condensed = [f"PROJECT {index} (SUMMARY):"]
        condensed.append(f"Title: {project.get('title', 'Untitled')}")
        
        # Add location and client if available
        if "location" in project and project["location"]:
            condensed.append(f"Location: {project['location']}")
        
        if "client" in project and project["client"]:
            condensed.append(f"Client: {project['client']}")
        
        # Add construction value or value if available
        if "construction_value" in project and project["construction_value"]:
            condensed.append(f"Construction Value: {project['construction_value']}")
        elif "value" in project and project["value"]:
            condensed.append(f"Value: {project['value']}")
        
        # Add a very brief description snippet if available
        if "description" in project and project["description"]:
            desc = project["description"]
            # Get first sentence or first 100 chars
            brief = desc.split('.')[0] if '.' in desc[:150] else desc[:100]
            condensed.append(f"Brief: {brief}...")
        
        return "\n".join(condensed)
    
    def _extract_keywords(self, query):
        """Extract important keywords from query for hybrid search"""
        # Remove common stopwords
        stopwords = {'the', 'a', 'an', 'in', 'on', 'at', 'by', 'for', 'with', 'about', 'to', 'of', 'is', 'are', 'was', 'were'}
        
        # Extract words and convert to lowercase
        words = re.findall(r'\b\w+\b', query.lower())
        
        # Filter out stopwords and short words
        keywords = [word for word in words if word not in stopwords and len(word) > 2]
        
        return keywords
    
    def _hybrid_search(self, query, limit=15):
        """
        PHASE 3: Hybrid Search
        Combine vector search with keyword matching for better relevance
        """
        # Get vector search results with higher limit to provide more candidates for re-ranking
        vector_results = self.search_engine.search_projects(query, limit=limit)
        
        # Extract key terms for keyword matching
        keywords = self._extract_keywords(query)
        
        if not keywords or not vector_results:
            return vector_results
        
        # Boost scores for keyword matches
        for result in vector_results:
            keyword_matches = 0
            text_fields = ['title', 'description', 'overview', 'location', 'client']
            
            # Check each keyword against each field
            for keyword in keywords:
                for field in text_fields:
                    if field in result and result[field] and isinstance(result[field], str):
                        field_text = result[field].lower()
                        # Exact match gets more points than partial match
                        if re.search(r'\b' + re.escape(keyword) + r'\b', field_text):
                            # Title matches are most important
                            if field == 'title':
                                keyword_matches += 3
                            # Location and client are secondary
                            elif field in ['location', 'client']:
                                keyword_matches += 2
                            # Description/overview are tertiary
                            else:
                                keyword_matches += 1
            
            # Apply keyword boost (10% per match)
            boost_factor = 1 + (keyword_matches * 0.1)
            result['_score'] = result.get('_score', 0) * boost_factor
            # Add a keyword_matches field for debugging
            result['_keyword_matches'] = keyword_matches
        
        # Re-sort by adjusted scores
        vector_results.sort(key=lambda x: x.get('_score', 0), reverse=True)
        return vector_results[:limit]
    
    def _rerank_results(self, results, query):
        """
        PHASE 3: Result Re-ranking
        Re-rank search results based on query terms and metadata
        """
        # Convert query to lowercase for matching
        query_lower = query.lower()
        query_terms = set(re.findall(r'\b\w+\b', query_lower))
        
        # Define important fields with weights
        fields = {
            'title': 3.0,
            'location': 2.0, 
            'description': 1.0,
            'client': 1.5,
            'features': 1.2,
            'specialties': 1.2,
            'value': 1.0,
            'construction_value': 1.0,
            'delivery_method': 0.8
        }
        
        # Look for special term patterns
        location_pattern = r'\b(in|at|near|around)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
        location_match = re.search(location_pattern, query)
        location_term = location_match.group(2).lower() if location_match else None
        
        # Look for cost/value related terms
        value_terms = ['cost', 'value', 'budget', 'price', 'expensive', 'million', 'dollar']
        has_value_focus = any(term in query_lower for term in value_terms)
        
        for result in results:
            # Start with base score
            boost = 0
            
            # Check for exact matches in each field
            for field, weight in fields.items():
                if field in result and result[field]:
                    field_text = str(result[field]).lower()
                    # Count matching terms
                    matches = sum(1 for term in query_terms if term in field_text)
                    boost += matches * weight
                    
                    # Special handling for location focus
                    if location_term and field == 'location' and location_term in field_text:
                        boost += 5.0  # Strong boost for location matches
                    
                    # Special handling for value/cost focus
                    if has_value_focus and field in ['value', 'construction_value'] and result[field]:
                        boost += 3.0  # Strong boost for value when query asks about cost
            
            # Apply boost to score
            result['_score'] = result.get('_score', 0) * (1 + boost * 0.1)
            # Store the boost amount for debugging
            result['_boost'] = boost
        
        # Re-sort by adjusted score
        results.sort(key=lambda x: x.get('_score', 0), reverse=True)
        return results
    
    def _get_llm_response(self, query, context, max_retries=2):
        """
        PHASE 4: Error Handling with Retry Logic
        Retry mechanism for LLM calls with exponential backoff
        """
        retries = 0
        while retries <= max_retries:
            try:
                response = self.chain.invoke({
                    "query": query,
                    "project_data": context
                })
                return response
            except Exception as e:
                retries += 1
                print(f"LLM error (attempt {retries}/{max_retries+1}): {e}")
                
                # Only retry if we haven't exceeded max_retries
                if retries <= max_retries:
                    # Exponential backoff with jitter
                    backoff_time = (2 ** retries) + random.uniform(0, 1)
                    print(f"Retrying in {backoff_time:.2f} seconds...")
                    time.sleep(backoff_time)
                else:
                    # Log the failure after all retries are exhausted
                    print(f"All {max_retries+1} attempts failed")
                    raise
        
        # This should not be reached due to the raise above, but just in case
        raise Exception("All retry attempts failed")
    
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
                "projects": [],  # Add empty array to satisfy API validation
                "success": False,
                "reason": "Potential prompt injection detected"
            }
        else:
            try:
                # PHASE 3: Use hybrid search and re-ranking instead of simple search
                search_results = self._hybrid_search(sanitized_query, limit=15)
                
                # Apply re-ranking to further improve relevance
                reranked_projects = self._rerank_results(search_results, sanitized_query)
                
                # Take the top 10 after re-ranking
                projects = reranked_projects[:10]
                
                if not projects:
                    result = {
                        "query": sanitized_query,
                        "response": "I couldn't find any Sundt Construction projects matching your query. Would you like to try a different search term?",
                        "projects": [],  # Add empty array to satisfy API validation
                        "success": False,
                        "reason": "No matching projects found"
                    }
                else:
                    # Format project data using dynamic context management
                    project_context = self._prepare_context(projects, sanitized_query)
                    
                    # PHASE 4: Use the retry mechanism for LLM calls
                    try:
                        raw_response = self._get_llm_response(sanitized_query, project_context)
                        
                        # Process the response for consistency
                        processed_response = self._process_llm_response(raw_response, sanitized_query, projects)
                        
                        result = {
                            "query": sanitized_query,
                            "response": processed_response,
                            "projects": projects,
                            "success": True
                        }
                    except Exception as e:
                        print(f"Error processing project query after retries: {e}")
                        result = {
                            "query": sanitized_query,
                            "response": "I encountered an error while processing your request about Sundt projects. Please try again.",
                            "projects": projects,  # Include projects to satisfy API validation
                            "success": False,
                            "reason": str(e)
                        }
            except Exception as e:
                print(f"Error in search or pre-processing: {e}")
                result = {
                    "query": sanitized_query,
                    "response": "I encountered an error while searching for Sundt projects. Please try again.",
                    "projects": [],  # Empty array for API validation
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