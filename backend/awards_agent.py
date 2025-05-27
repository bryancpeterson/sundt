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

# Suppress HuggingFace tokenizer warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

class AwardsAgent:
    
    def __init__(self, model_name="gpt-4.1-mini", temperature=0.2):
        self.search_engine = LocalVectorSearchEngine()
        
        # Using the newer GPT model for better responses
        self.model_name = model_name
        self.temperature = temperature
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature)
        
        # Simple prompt that focuses on awards info
        self.prompt = PromptTemplate(
            input_variables=["query", "award_data"],
            template="""
            You are the Awards Agent for Sundt Construction. Your role is to answer 
            questions using only the provided award data.

            USER QUERY: {query}

            AWARD DATA:
            {award_data}

            Instructions:
            1. Only use the provided award data.
            2. Organize multiple awards if needed.
            3. Include details like organization names, dates, categories.
            4. Mention any patterns if relevant (e.g., repeated awards in safety).
            5. If no information matches, say so clearly.
            6. Format the response professionally.

            RESPONSE:
            """
        )
        
        # Build LangChain pipeline
        self.chain = (
            {"query": RunnablePassthrough(), "award_data": RunnablePassthrough()}
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
        
        # Basic metrics tracking for the demo
        self.metrics_file = os.path.join("data", "awards_agent_metrics.json")
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
    
    def _update_metrics(self, query: str, execution_time: float, is_injection: bool = False) -> None:
        self.metrics = self._load_metrics()
        today = datetime.now().strftime("%Y-%m-%d")
        
        self.metrics["total_queries"] += 1
        self.metrics["query_times"].append(execution_time)
        if len(self.metrics["query_times"]) > 100:
            self.metrics["query_times"] = self.metrics["query_times"][-100:]
        
        if is_injection:
            self.metrics["injection_attempts"].append({
                "query": query,
                "date": today
            })
        
        if today not in self.metrics["queries_by_date"]:
            self.metrics["queries_by_date"][today] = 0
        self.metrics["queries_by_date"][today] += 1
        
        # Track popular search terms
        words = re.findall(r'\b\w+\b', query.lower())
        for word in words:
            if len(word) > 3:
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
        # Basic prompt injection detection
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
                return (query, True)
        
        # Clean up the query a bit
        sanitized = re.sub(r'[^\w\s\.,\-\?:;\'\"()]', ' ', query)
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        return (sanitized, False)
    
    def _format_award_info(self, award, index):
        # Format award data for the LLM context
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
        award_info.append(f"Title: {award.get('title', 'Untitled')}")
        
        for field, display_name in fields_mapping.items():
            if field != "title" and field in award and award[field]:
                award_info.append(f"{display_name}: {award[field]}")
        
        # Include related projects if any
        if "projects" in award and award["projects"]:
            projects = award.get("projects")
            if isinstance(projects, list):
                project_titles = [p.get("title", "Unnamed Project") for p in projects]
                award_info.append(f"Related Projects: {', '.join(project_titles)}")
        
        return "\n".join(award_info)
    
    def _prepare_context(self, awards, query, max_tokens=3500):
        # Build context string for the LLM, keeping under token limit
        context = []
        token_count = 0
        
        # Sort by relevance score
        sorted_awards = sorted(awards, key=lambda x: x.get('_score', 0), reverse=True)
        
        for i, award in enumerate(sorted_awards, 1):
            award_info = self._format_award_info(award, i)
            estimated_tokens = len(award_info) // 4  # Rough token estimation
            
            if token_count + estimated_tokens > max_tokens:
                # Try condensed version for important awards
                if i <= 3:
                    condensed_info = self._format_condensed_award(award, i)
                    condensed_tokens = len(condensed_info) // 4
                    if token_count + condensed_tokens <= max_tokens:
                        context.append(condensed_info)
                        token_count += condensed_tokens
                continue
            
            context.append(award_info)
            token_count += estimated_tokens
        
        # Always include at least one award
        if not context and awards:
            condensed_info = self._format_condensed_award(awards[0], 1)
            context.append(condensed_info)
        
        return "\n\n".join(context)
    
    def _format_condensed_award(self, award, index):
        # Shorter version when we're running out of context space
        condensed = [f"AWARD {index} (SUMMARY):"]
        condensed.append(f"Title: {award.get('title', 'Untitled')}")
        
        if "organization" in award and award["organization"]:
            condensed.append(f"Organization: {award['organization']}")
        
        if "category" in award and award["category"]:
            condensed.append(f"Category: {award['category']}")
        
        if "date" in award and award["date"]:
            condensed.append(f"Date: {award['date']}")
        elif "year" in award and award["year"]:
            condensed.append(f"Year: {award['year']}")
        
        if "description" in award and award["description"]:
            desc = award["description"]
            brief = desc.split('.')[0] if '.' in desc[:150] else desc[:100]
            condensed.append(f"Brief: {brief}...")
        
        return "\n".join(condensed)
    
    def _extract_keywords(self, query):
        # Pull out important keywords for boosting search results
        stopwords = {'the', 'a', 'an', 'in', 'on', 'at', 'by', 'for', 'with', 'about', 'to', 'of', 'is', 'are', 'was', 'were'}
        
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [word for word in words if word not in stopwords and len(word) > 2]
        
        return keywords
    
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
            if 'organization' in item:
                text_fields.append(item['organization'])
            if 'category' in item:
                text_fields.append(item['category'])
            
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
    
    def _hybrid_search(self, query, limit=15):
        # Combine vector search with keyword matching + term frequency penalties
        vector_results = self.search_engine.search_awards(query, limit=limit)
        keywords = self._extract_keywords(query)
        
        if not keywords or not vector_results:
            return vector_results
        
        # Calculate term frequencies once (cached after first run)
        if not hasattr(self, '_term_frequencies'):
            data_items = self.search_engine.awards
            self._term_frequencies = self._calculate_term_frequencies(data_items)
        
        # Apply keyword boosting with frequency penalties
        for result in vector_results:
            total_boost = 0
            text_fields = ['title', 'description', 'organization', 'category']
            
            for keyword in keywords:
                # Calculate base keyword matches 
                keyword_matches = 0
                for field in text_fields:
                    if field in result and result[field] and isinstance(result[field], str):
                        field_text = result[field].lower()
                        if re.search(r'\b' + re.escape(keyword) + r'\b', field_text):
                            # Weight title matches higher
                            if field == 'title':
                                keyword_matches += 3
                            elif field in ['organization', 'category']:
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
        # Additional ranking based on query patterns
        query_lower = query.lower()
        query_terms = set(re.findall(r'\b\w+\b', query_lower))
        
        fields = {
            'title': 3.0,
            'organization': 2.5,
            'category': 2.0,
            'description': 1.0,
            'date': 1.5,
            'year': 1.5
        }
        
        # Look for specific award types
        award_types = ["safety", "quality", "environmental", "innovation", "excellence"]
        has_award_type_focus = any(term in query_lower for term in award_types)
        
        # Check for year mentions
        year_pattern = r'\b(19|20)\d{2}\b'
        year_match = re.search(year_pattern, query)
        year_term = year_match.group(0) if year_match else None
        
        # Common organization abbreviations
        org_pattern = r'\b(ENR|Associated Builders|ABC|AGC|DBIA|OSHA)\b'
        org_match = re.search(org_pattern, query, re.IGNORECASE)
        org_term = org_match.group(0).lower() if org_match else None
        
        for result in results:
            boost = 0
            
            # Score based on field matches
            for field, weight in fields.items():
                if field in result and result[field]:
                    field_text = str(result[field]).lower()
                    matches = sum(1 for term in query_terms if term in field_text)
                    boost += matches * weight
                    
                    # Specific boosts for targeted searches
                    if year_term and field in ['date', 'year'] and year_term in field_text:
                        boost += 5.0
                        
                    if org_term and field == 'organization' and org_term in field_text:
                        boost += 4.0
                        
                    if has_award_type_focus and field in ['title', 'category']:
                        for award_type in award_types:
                            if award_type in field_text:
                                boost += 3.0
                                break
            
            result['_score'] = result.get('_score', 0) * (1 + boost * 0.1)
            result['_boost'] = boost
        
        results.sort(key=lambda x: x.get('_score', 0), reverse=True)
        return results
    
    def _get_llm_response(self, query, context, max_retries=2):
        # Call OpenAI with retry logic
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
                
                if retries <= max_retries:
                    # Exponential backoff with some randomness
                    backoff_time = (2 ** retries) + random.uniform(0, 1)
                    print(f"Retrying in {backoff_time:.2f} seconds...")
                    time.sleep(backoff_time)
                else:
                    print(f"All {max_retries+1} attempts failed")
                    raise
        
        raise Exception("All retry attempts failed")
    
    def _process_llm_response(self, response, query, awards):
        # Clean up and format the LLM response
        if not response or len(response.strip()) < 10:
            return f"I couldn't generate a proper response about Sundt awards related to '{query}'. Please try a different query."
            
        prefix = f"Based on Sundt Construction's awards database, here's information about '{query}':\n\n"
        
        if awards:
            footer = f"\n\nThis information is based on {len(awards)} relevant awards in Sundt's history."
        else:
            footer = "\n\nI couldn't find specific Sundt awards matching your query in our database."
        
        return prefix + response + footer
    
    def get_metrics(self) -> Dict[str, Any]:
        return self._load_metrics()
    
    def run(self, query: str) -> Dict[str, Any]:
        # Main entry point for processing queries
        start_time = time.time()
        
        sanitized_query, is_injection = self._sanitize_input(query)
        
        if is_injection:
            result = {
                "query": query,
                "response": "I can only provide information about Sundt Construction awards. Please rephrase your query.",
                "awards": [],
                "success": False,
                "reason": "Potential prompt injection detected"
            }
        else:
            try:
                # Search and rank awards
                search_results = self._hybrid_search(sanitized_query, limit=15)
                reranked_awards = self._rerank_results(search_results, sanitized_query)
                awards = reranked_awards[:10]
                
                if not awards:
                    result = {
                        "query": sanitized_query,
                        "response": "I couldn't find any Sundt Construction awards matching your query. Would you like to try a different search term?",
                        "awards": [],
                        "success": False,
                        "reason": "No matching awards found"
                    }
                else:
                    # Build context and get LLM response
                    award_context = self._prepare_context(awards, sanitized_query)
                    try:
                        raw_response = self._get_llm_response(sanitized_query, award_context)
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
                            "awards": awards,
                            "success": False,
                            "reason": str(e)
                        }
            except Exception as e:
                print(f"Error in search or pre-processing: {e}")
                result = {
                    "query": sanitized_query,
                    "response": "I encountered an error while searching for Sundt awards. Please try again.",
                    "awards": [],
                    "success": False,
                    "reason": str(e)
                }
        
        execution_time = time.time() - start_time
        result["execution_time"] = execution_time
        
        self._update_metrics(query, execution_time, is_injection)
        
        return result

# Quick test if running directly
if __name__ == "__main__":
    awards_agent = AwardsAgent()
    
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