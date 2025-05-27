import os
import json
import re
import time
import random
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from local_vector_search import LocalVectorSearchEngine
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from dotenv import load_dotenv

load_dotenv()

# Fix HuggingFace tokenizers warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

class ProjectsAgent:
    
    def __init__(self, model_name="gpt-4.1-mini", temperature=0.2):
        self.search_engine = LocalVectorSearchEngine()
        
        # Using GPT-4.1-mini for good quality responses without breaking the bank
        self.model_name = model_name
        self.temperature = temperature
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature)
        
        # Focused prompt for project information
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
        
        # Build LangChain pipeline
        self.chain = (
            {"query": RunnablePassthrough(), "project_data": RunnablePassthrough()}
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
        
        # Simple metrics for demo purposes
        self.metrics_file = os.path.join("data", "projects_agent_metrics.json")
        self.metrics = self._load_metrics()
    
    def _load_metrics(self) -> Dict[str, Any]:
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return self._initialize_metrics()
        else:
            return self._initialize_metrics()
    
    def _initialize_metrics(self) -> Dict[str, Any]:
        return {
            "total_queries": 0,
            "query_times": [],
            "injection_attempts": [],
            "queries_by_date": {},
            "popular_terms": {}
        }
    
    def _update_metrics(self, query: str, execution_time: float, 
                       is_injection: bool = False) -> None:
        self.metrics = self._load_metrics()
        today = datetime.now().strftime("%Y-%m-%d")
        
        self.metrics["total_queries"] += 1
        
        # Keep last 100 query times for performance tracking
        self.metrics["query_times"].append(execution_time)
        if len(self.metrics["query_times"]) > 100:
            self.metrics["query_times"] = self.metrics["query_times"][-100:]
        
        # Track injection attempts for security demo
        if is_injection:
            self.metrics["injection_attempts"].append({
                "query": query,
                "date": today
            })
        
        # Daily query counts
        if today not in self.metrics["queries_by_date"]:
            self.metrics["queries_by_date"][today] = 0
        self.metrics["queries_by_date"][today] += 1
        
        # Track popular search terms
        words = re.findall(r'\b\w+\b', query.lower())
        for word in words:
            if len(word) > 3:  # Filter out short words
                if word not in self.metrics["popular_terms"]:
                    self.metrics["popular_terms"][word] = 0
                self.metrics["popular_terms"][word] += 1
        
        self._save_metrics()
    
    def _save_metrics(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.metrics_file), exist_ok=True)
            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                json.dump(self.metrics, f, indent=2)
        except Exception as e:
            print(f"Error saving metrics: {e}")
    
    def _sanitize_input(self, query: str) -> tuple:
        # Basic prompt injection detection patterns
        injection_patterns = [
        # Ignore variations 
        r'ignore\s+(?:all\s+)?(?:previous\s+)?instructions?',
        r'ignore\s+(?:all\s+)?(?:your\s+)?(?:previous\s+)?(?:instructions?|prompts?|rules?)',
        
        # Disregard variations  
        r'disregard\s+(?:all\s+)?(?:previous\s+)?(?:instructions?|prompts?|rules?)',
        r'disregard\s+(?:all\s+)?(?:your\s+)?(?:previous\s+)?(?:instructions?|prompts?|rules?)',
        
        # Forget variations
        r'forget\s+(?:all\s+)?(?:your\s+)?(?:previous\s+)?(?:instructions?|prompts?|rules?)',
        r'forget\s+(?:everything|what)\s+(?:you\s+)?(?:know|learned)',
        
        # New instruction attempts
        r'new\s+(?:prompt|instructions?|rules?):?',
        r'different\s+(?:prompt|instructions?|rules?):?',
        r'updated?\s+(?:prompt|instructions?|rules?):?',
        
        # System override attempts
        r'system\s+(?:prompt|instructions?|message):?',
        r'override\s+(?:system|security|safety)',
        r'bypass\s+(?:security|safety|filters?)',
        
        # Role manipulation 
        r'you\s+(?:are\s+now|will\s+be|should\s+be|must\s+be)\s+(?:a|an)?\s*\w+',
        r'(?:your\s+)?(?:new\s+)?role\s+(?:is|will\s+be|should\s+be)',
        r'act\s+(?:as|like)\s+(?:a|an)?\s*\w+',
        r'pretend\s+(?:to\s+be|you\s+are)',
        
        # Direct override language
        r'instead\s+of\s+(?:answering|responding|following)',
        r'rather\s+than\s+(?:answering|responding|following)',
    ]
    
        # Check for injection patterns
        for pattern in injection_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                # Don't modify the query for metrics but flag as injection
                return (query, True)
    
        # Basic sanitization (keep your existing logic)
        sanitized = re.sub(r'[^\w\s\.,\-\?:;\'\"()]', ' ', query)
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
        return (sanitized, False)
    
    def _format_project_info(self, project, index):
        # Structure project data for LLM context
        fields_mapping = {
            "title": "Title",
            "location": "Location",
            "client": "Client", 
            "construction_value": "Construction Value",
            "value": "Value",  # Fallback field
            "delivery_method": "Delivery Method",
            "year_completed": "Year Completed",
            "description": "Description",
            "overview": "Overview",  # Alternative description field
        }
        
        project_info = [f"PROJECT {index}:"]
        project_info.append(f"Title: {project.get('title', 'Untitled')}")
        
        # Add all available fields in logical order
        for field, display_name in fields_mapping.items():
            if field != "title" and field in project and project[field]:
                project_info.append(f"{display_name}: {project[field]}")
        
        # Handle list fields like features and specialties
        for list_field in ["features", "specialties"]:
            if list_field in project and project[list_field]:
                items = project[list_field]
                formatted_items = ", ".join(items) if isinstance(items, list) else items
                field_name = list_field.title()
                project_info.append(f"{field_name}: {formatted_items}")
        
        return "\n".join(project_info)
    
    def _prepare_context(self, projects, query, max_tokens=3500):
        # Build context string while staying under token limits
        context = []
        token_count = 0
        
        # Sort by relevance score first
        sorted_projects = sorted(projects, key=lambda x: x.get('_score', 0), reverse=True)
        
        for i, project in enumerate(sorted_projects, 1):
            project_info = self._format_project_info(project, i)
            
            # Rough token estimation (4 chars per token)
            estimated_tokens = len(project_info) // 4
            
            if token_count + estimated_tokens > max_tokens:
                # Try condensed version for top projects
                if i <= 3:
                    condensed_info = self._format_condensed_project(project, i)
                    condensed_tokens = len(condensed_info) // 4
                    
                    if token_count + condensed_tokens <= max_tokens:
                        context.append(condensed_info)
                        token_count += condensed_tokens
                continue
                
            context.append(project_info)
            token_count += estimated_tokens
        
        # Always include at least one project
        if not context and projects:
            condensed_info = self._format_condensed_project(projects[0], 1)
            context.append(condensed_info)
        
        return "\n\n".join(context)
    
    def _format_condensed_project(self, project, index):
        # Shorter version when we're running out of context space
        condensed = [f"PROJECT {index} (SUMMARY):"]
        condensed.append(f"Title: {project.get('title', 'Untitled')}")
        
        # Include most important fields
        if "location" in project and project["location"]:
            condensed.append(f"Location: {project['location']}")
        
        if "client" in project and project["client"]:
            condensed.append(f"Client: {project['client']}")
        
        # Value information
        if "construction_value" in project and project["construction_value"]:
            condensed.append(f"Construction Value: {project['construction_value']}")
        elif "value" in project and project["value"]:
            condensed.append(f"Value: {project['value']}")
        
        # Brief description snippet
        if "description" in project and project["description"]:
            desc = project["description"]
            brief = desc.split('.')[0] if '.' in desc[:150] else desc[:100]
            condensed.append(f"Brief: {brief}...")
        
        return "\n".join(condensed)
    
    def _extract_keywords(self, query):
        # Pull out meaningful keywords for search boosting
        stopwords = {'the', 'a', 'an', 'in', 'on', 'at', 'by', 'for', 'with', 'about', 'to', 'of', 'is', 'are', 'was', 'were'}
        
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [word for word in words if word not in stopwords and len(word) > 2]
        
        return keywords
    
    def _hybrid_search(self, query, limit=15):
        # Combine vector search with keyword matching + term frequency penalties
        vector_results = self.search_engine.search_projects(query, limit=limit)
        keywords = self._extract_keywords(query)
    
        if not keywords or not vector_results:
            return vector_results
    
        # Calculate term frequencies once (cached after first run)
        if not hasattr(self, '_term_frequencies'):
            data_items = self.search_engine.projects
            self._term_frequencies = self._calculate_term_frequencies(data_items)
    
        # Apply keyword boosting with frequency penalties
        for result in vector_results:
            total_boost = 0
            text_fields = ['title', 'description', 'overview', 'location', 'client']
        
            for keyword in keywords:
                # Calculate base keyword matches 
                keyword_matches = 0
                for field in text_fields:
                    if field in result and result[field] and isinstance(result[field], str):
                        field_text = result[field].lower()
                        if re.search(r'\b' + re.escape(keyword) + r'\b', field_text):
                            # Weight matches by field importance
                            if field == 'title':
                                keyword_matches += 3
                            elif field in ['location', 'client']:
                                keyword_matches += 2
                            else:
                                keyword_matches += 1
            
                # Apply term frequency penalty to reduce common word boost
                if keyword_matches > 0:
                    penalty = self._get_term_penalty(keyword, self._term_frequencies)
                    penalized_boost = keyword_matches * penalty
                    total_boost += penalized_boost
        
            # Apply total boost (reduced from 0.1 to 0.05 to be less aggressive)
            boost_factor = 1 + (total_boost * 0.05)
            result['_score'] = result.get('_score', 0) * boost_factor
            result['_keyword_matches'] = total_boost  # Store for debugging
    
        # Re-sort by adjusted scores
        vector_results.sort(key=lambda x: x.get('_score', 0), reverse=True)
        return vector_results[:limit]
    
    def _rerank_results(self, results, query):
        # Additional ranking based on query patterns and context
        query_lower = query.lower()
        query_terms = set(re.findall(r'\b\w+\b', query_lower))
        
        # Field importance weights
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
        
        # Look for location-specific queries
        location_pattern = r'\b(in|at|near|around)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
        location_match = re.search(location_pattern, query)
        location_term = location_match.group(2).lower() if location_match else None
        
        # Check for value/cost related queries
        value_terms = ['cost', 'value', 'budget', 'price', 'expensive', 'million', 'dollar']
        has_value_focus = any(term in query_lower for term in value_terms)
        
        for result in results:
            boost = 0
            
            # Score based on field matches
            for field, weight in fields.items():
                if field in result and result[field]:
                    field_text = str(result[field]).lower()
                    matches = sum(1 for term in query_terms if term in field_text)
                    boost += matches * weight
                    
                    # Special handling for location queries
                    if location_term and field == 'location' and location_term in field_text:
                        boost += 5.0
                    
                    # Boost for value-focused queries
                    if has_value_focus and field in ['value', 'construction_value'] and result[field]:
                        boost += 3.0
            
            result['_score'] = result.get('_score', 0) * (1 + boost * 0.1)
            result['_boost'] = boost
        
        results.sort(key=lambda x: x.get('_score', 0), reverse=True)
        return results
    
    def _get_llm_response(self, query, context, max_retries=2):
        # Call OpenAI with retry logic for reliability
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
                
                if retries <= max_retries:
                    # Exponential backoff with jitter
                    backoff_time = (2 ** retries) + random.uniform(0, 1)
                    print(f"Retrying in {backoff_time:.2f} seconds...")
                    time.sleep(backoff_time)
                else:
                    print(f"All {max_retries+1} attempts failed")
                    raise
        
        raise Exception("All retry attempts failed")
    
    def _process_llm_response(self, response, query, projects):
        # Clean up and format the final response
        if not response or len(response.strip()) < 10:
            return f"I couldn't generate a proper response about Sundt projects related to '{query}'. Please try a different query."
            
        prefix = f"Based on Sundt Construction's project database, here's information about '{query}':\n\n"
        
        if projects:
            footer = f"\n\nThis information is based on {len(projects)} relevant Sundt projects."
        else:
            footer = "\n\nI couldn't find specific Sundt projects matching your query in our database."
            
        return prefix + response + footer
    
    def _calculate_term_frequencies(self, data_items):
        # Calculate how often each term appears across all items
        term_counts = {}
        total_items = len(data_items)
    
        # Count how many items contain each term
        for item in data_items:
            # Get all text from the item
            text_fields = []
            if 'title' in item:
                text_fields.append(item['title'])
            if 'description' in item:
                text_fields.append(item['description'])
            if 'location' in item:
                text_fields.append(item['location'])
            if 'client' in item:
                text_fields.append(item['client'])
        
            # Extract unique terms from this item
            item_terms = set()
            for field_text in text_fields:
                if field_text:
                    words = re.findall(r'\b\w+\b', field_text.lower())
                    item_terms.update(word for word in words if len(word) > 2)
        
            # Count each unique term once per item
            for term in item_terms:
                term_counts[term] = term_counts.get(term, 0) + 1
    
        # Convert to frequencies (what % of items contain this term)
        term_frequencies = {}
        for term, count in term_counts.items():
            term_frequencies[term] = count / total_items
    
        return term_frequencies

    def _get_term_penalty(self, term, term_frequencies):
        # Calculate penalty for common terms (TF-IDF style)
        frequency = term_frequencies.get(term, 0.01)  # Default to rare if not found
    
        # Penalty formula: more common = less boost
        # 0.01 frequency (1% of docs) = 1.0 multiplier (full boost)
        # 0.50 frequency (50% of docs) = 0.2 multiplier (much less boost)
        penalty = min(1.0, 0.1 / frequency)
        return penalty
    
    def get_metrics(self) -> Dict[str, Any]:
        return self._load_metrics()
    
    def run(self, query: str) -> Dict[str, Any]:
        # Main entry point for processing project queries
        start_time = time.time()
        
        sanitized_query, is_injection = self._sanitize_input(query)
        
        if is_injection:
            result = {
                "query": query,
                "response": "I can only provide information about Sundt Construction projects. Please rephrase your query.",
                "projects": [],
                "success": False,
                "reason": "Potential prompt injection detected"
            }
        else:
            try:
                # Multi-stage search: vector + keyword + reranking
                search_results = self._hybrid_search(sanitized_query, limit=15)
                reranked_projects = self._rerank_results(search_results, sanitized_query)
                projects = reranked_projects[:10]  # Top 10 for LLM context
                
                if not projects:
                    result = {
                        "query": sanitized_query,
                        "response": "I couldn't find any Sundt Construction projects matching your query. Would you like to try a different search term?",
                        "projects": [],
                        "success": False,
                        "reason": "No matching projects found"
                    }
                else:
                    # Build context and get LLM response
                    project_context = self._prepare_context(projects, sanitized_query)
                    
                    try:
                        raw_response = self._get_llm_response(sanitized_query, project_context)
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
                            "projects": projects,
                            "success": False,
                            "reason": str(e)
                        }
            except Exception as e:
                print(f"Error in search or pre-processing: {e}")
                result = {
                    "query": sanitized_query,
                    "response": "I encountered an error while searching for Sundt projects. Please try again.",
                    "projects": [],
                    "success": False,
                    "reason": str(e)
                }
        
        execution_time = time.time() - start_time
        result["execution_time"] = execution_time
        
        self._update_metrics(query, execution_time, is_injection)
        
        return result


# Quick test runner
if __name__ == "__main__":
    projects_agent = ProjectsAgent()
    
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