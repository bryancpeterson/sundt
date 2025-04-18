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
    
    def _prepare_context(self, awards, query, max_tokens=3500):
        """Dynamically prepare context based on token count and relevance"""
        context = []
        token_count = 0
        
        # Prioritize awards based on relevance score
        sorted_awards = sorted(awards, key=lambda x: x.get('_score', 0), reverse=True)
        
        for i, award in enumerate(sorted_awards, 1):
            # Format the award info
            award_info = self._format_award_info(award, i)
            
            # Estimate token count (approximation: 1 token ≈ 4 chars in English)
            estimated_tokens = len(award_info) // 4
            
            # Check if adding this would exceed our limit
            if token_count + estimated_tokens > max_tokens:
                # Try a condensed version for important awards
                if i <= 3:  # First 3 awards are most relevant
                    condensed_info = self._format_condensed_award(award, i)
                    condensed_tokens = len(condensed_info) // 4
                    
                    if token_count + condensed_tokens <= max_tokens:
                        context.append(condensed_info)
                        token_count += condensed_tokens
                continue
                
            # Add the full award info
            context.append(award_info)
            token_count += estimated_tokens
        
        # If we couldn't add any awards (very unlikely), add at least one in condensed form
        if not context and awards:
            condensed_info = self._format_condensed_award(awards[0], 1)
            context.append(condensed_info)
        
        return "\n\n".join(context)
    
    def _format_condensed_award(self, award, index):
        """Create a condensed version of award info with only essential fields"""
        # Include only the most important fields for condensed view
        essential_fields = ["title", "organization", "category", "date", "year"]
        
        condensed = [f"AWARD {index} (SUMMARY):"]
        condensed.append(f"Title: {award.get('title', 'Untitled')}")
        
        # Add organization if available
        if "organization" in award and award["organization"]:
            condensed.append(f"Organization: {award['organization']}")
        
        # Add category if available
        if "category" in award and award["category"]:
            condensed.append(f"Category: {award['category']}")
        
        # Add date or year if available
        if "date" in award and award["date"]:
            condensed.append(f"Date: {award['date']}")
        elif "year" in award and award["year"]:
            condensed.append(f"Year: {award['year']}")
        
        # Add a very brief description snippet if available
        if "description" in award and award["description"]:
            desc = award["description"]
            # Get first sentence or first 100 chars
            brief = desc.split('.')[0] if '.' in desc[:150] else desc[:100]
            condensed.append(f"Brief: {brief}...")
        
        return "\n".join(condensed)
    
    def _extract_keywords(self, query):
        """
        PHASE 3: Extract important keywords from query for hybrid search
        """
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
        vector_results = self.search_engine.search_awards(query, limit=limit)
        
        # Extract key terms for keyword matching
        keywords = self._extract_keywords(query)
        
        if not keywords or not vector_results:
            return vector_results
        
        # Boost scores for keyword matches
        for result in vector_results:
            keyword_matches = 0
            text_fields = ['title', 'description', 'organization', 'category']
            
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
                            # Organization and category are secondary
                            elif field in ['organization', 'category']:
                                keyword_matches += 2
                            # Description is tertiary
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
            'organization': 2.5,
            'category': 2.0,
            'description': 1.0,
            'date': 1.5,
            'year': 1.5
        }
        
        # Look for special award types/organizations
        award_types = ["safety", "quality", "environmental", "innovation", "excellence"]
        has_award_type_focus = any(term in query_lower for term in award_types)
        
        # Look for date/year patterns
        year_pattern = r'\b(19|20)\d{2}\b'
        year_match = re.search(year_pattern, query)
        year_term = year_match.group(0) if year_match else None
        
        # Look for organization names
        org_pattern = r'\b(ENR|Associated Builders|ABC|AGC|DBIA|OSHA)\b'
        org_match = re.search(org_pattern, query, re.IGNORECASE)
        org_term = org_match.group(0).lower() if org_match else None
        
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
                    
                    # Special handling for year focus
                    if year_term and field in ['date', 'year'] and year_term in field_text:
                        boost += 5.0  # Strong boost for year matches
                    
                    # Special handling for organization focus
                    if org_term and field == 'organization' and org_term in field_text:
                        boost += 4.0  # Strong boost for organization matches
                    
                    # Special handling for award type focus
                    if has_award_type_focus and field in ['title', 'category']:
                        for award_type in award_types:
                            if award_type in field_text:
                                boost += 3.0  # Strong boost for matching award types
                                break
            
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
                    "award_data": context
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
                "awards": [],  # Add empty array to satisfy API validation
                "success": False,
                "reason": "Potential prompt injection detected"
            }
        else:
            try:
                # PHASE 3: Use hybrid search and re-ranking instead of simple search
                search_results = self._hybrid_search(sanitized_query, limit=15)
                
                # Apply re-ranking to further improve relevance
                reranked_awards = self._rerank_results(search_results, sanitized_query)
                
                # Take the top 10 after re-ranking
                awards = reranked_awards[:10]
                
                if not awards:
                    result = {
                        "query": sanitized_query,
                        "response": "I couldn't find any Sundt Construction awards matching your query. Would you like to try a different search term?",
                        "awards": [],  # Add empty array to satisfy API validation
                        "success": False,
                        "reason": "No matching awards found"
                    }
                else:
                    # Format award data using dynamic context management
                    award_context = self._prepare_context(awards, sanitized_query)
                    
                    # PHASE 4: Use the retry mechanism for LLM calls
                    try:
                        raw_response = self._get_llm_response(sanitized_query, award_context)
                        
                        # Process the response for consistency
                        processed_response = self._process_llm_response(raw_response, sanitized_query, awards)
                        
                        result = {
                            "query": sanitized_query,
                            "response": processed_response,
                            "awards": awards,
                            "success": True
                        }
                    except Exception as e:
                        print(f"Error processing award query after retries: {e}")
                        result = {
                            "query": sanitized_query,
                            "response": "I encountered an error while processing your request about Sundt awards. Please try again.",
                            "awards": awards,  # Include awards to satisfy API validation
                            "success": False,
                            "reason": str(e)
                        }
            except Exception as e:
                print(f"Error in search or pre-processing: {e}")
                result = {
                    "query": sanitized_query,
                    "response": "I encountered an error while searching for Sundt awards. Please try again.",
                    "awards": [],  # Empty array for API validation
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