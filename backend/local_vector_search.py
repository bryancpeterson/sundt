import os
import json
import numpy as np
from typing import List, Dict, Any, Union, Optional
import re
import time

class LocalVectorSearchEngine:
    """
    Vector-based search engine for Sundt data using local embeddings
    Uses sentence-transformers for generating embeddings locally without API costs
    """
    
    def __init__(self, data_dir="data", use_cached_embeddings=True):
        self.data_dir = data_dir
        self.projects_file = os.path.join(data_dir, "projects.json")
        self.awards_file = os.path.join(data_dir, "awards.json")
        self.embeddings_file = os.path.join(data_dir, "local_embeddings.json")
        
        # Import the sentence_transformers library (only when needed)
        # This allows the file to be imported even if the library isn't installed yet
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer('all-MiniLM-L6-v2')  # Small, fast model (384 dimensions)
            self.embedding_available = True
        except ImportError:
            print("Warning: sentence-transformers library not installed. Run: pip install sentence-transformers==2.2.2")
            self.embedding_available = False
        
        # Load data
        self.projects = self._load_json_data(self.projects_file, "projects")
        self.awards = self._load_json_data(self.awards_file, "awards")
        
        # Generate or load embeddings
        if self.embedding_available:
            self.embeddings = self._load_or_generate_embeddings(use_cached_embeddings)
        else:
            # Dummy embeddings for testing if library isn't available
            self.embeddings = {"projects": [], "awards": [], "created_at": 0}
    
    def _load_json_data(self, file_path: str, key: str) -> List[Dict[str, Any]]:
        """Load JSON data from file"""
        if not os.path.exists(file_path):
            print(f"Warning: {file_path} does not exist")
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get(key, [])
        except Exception as e:
            print(f"Error loading data from {file_path}: {e}")
            return []
    
    def _load_or_generate_embeddings(self, use_cached=True) -> Dict[str, Any]:
        """Load existing embeddings or generate new ones"""
        # Check if embeddings already exist and we should use them
        if use_cached and os.path.exists(self.embeddings_file):
            try:
                with open(self.embeddings_file, 'r', encoding='utf-8') as f:
                    print(f"Loading cached embeddings from {self.embeddings_file}")
                    data = json.load(f)
                    
                    # Convert lists back to numpy arrays for efficiency
                    data["projects"] = [np.array(vec) for vec in data["projects"]]
                    data["awards"] = [np.array(vec) for vec in data["awards"]]
                    
                    return data
            except Exception as e:
                print(f"Error loading embeddings: {e}")
        
        # Generate new embeddings
        print("Generating new embeddings...")
        start_time = time.time()
        embeddings = {
            "projects": [],
            "awards": [],
            "created_at": time.time()
        }
        
        # Generate project embeddings
        project_texts = []
        for project in self.projects:
            text = self._prepare_text_for_embedding(project, "project")
            project_texts.append(text)
        
        # Batch processing for efficiency
        print(f"Generating embeddings for {len(project_texts)} projects...")
        embeddings["projects"] = self.model.encode(project_texts)
        
        # Generate award embeddings
        award_texts = []
        for award in self.awards:
            text = self._prepare_text_for_embedding(award, "award")
            award_texts.append(text)
        
        # Batch processing for efficiency
        print(f"Generating embeddings for {len(award_texts)} awards...")
        embeddings["awards"] = self.model.encode(award_texts)
        
        # Convert numpy arrays to lists for JSON serialization
        serializable_embeddings = {
            "projects": [vec.tolist() for vec in embeddings["projects"]],
            "awards": [vec.tolist() for vec in embeddings["awards"]],
            "created_at": embeddings["created_at"]
        }
        
        # Save embeddings to file
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.embeddings_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_embeddings, f)
        
        print(f"Embeddings generated in {time.time() - start_time:.2f} seconds")
        return embeddings
    
    def _prepare_text_for_embedding(self, item: Dict[str, Any], item_type: str) -> str:
        """Prepare text representation of an item for embedding"""
        if item_type == "project":
            # Combine relevant fields for projects
            parts = [
                f"Title: {item.get('title', '')}",
                f"Description: {item.get('description', item.get('overview', ''))}",
                f"Location: {item.get('location', '')}",
                f"Client: {item.get('client', '')}"
            ]
            
            # Add features if available
            if "features" in item and item["features"]:
                features = item["features"]
                if isinstance(features, list):
                    features_text = ", ".join(features)
                else:
                    features_text = str(features)
                parts.append(f"Features: {features_text}")
            
            # Add specialties if available
            if "specialties" in item and item["specialties"]:
                specialties = item["specialties"]
                if isinstance(specialties, list):
                    specialties_text = ", ".join(specialties)
                else:
                    specialties_text = str(specialties)
                parts.append(f"Specialties: {specialties_text}")
            
        elif item_type == "award":
            # Combine relevant fields for awards
            parts = [
                f"Title: {item.get('title', '')}",
                f"Organization: {item.get('organization', '')}",
                f"Category: {item.get('category', '')}",
                f"Description: {item.get('description', '')}",
                f"Year: {item.get('year', item.get('date', ''))}"
            ]
            
            # Add related projects if available
            if "projects" in item and item["projects"]:
                projects = item["projects"]
                if isinstance(projects, list):
                    project_titles = [p.get("title", "") for p in projects]
                    parts.append(f"Projects: {', '.join(project_titles)}")
        
        # Join all parts with newlines and clean up any empty lines
        text = "\n".join(part for part in parts if part.strip())
        return text
    
    def search_projects(self, query: str, limit: int = 10, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Search for projects using vector similarity"""
        if not self.embedding_available:
            print("Warning: Vector search unavailable without sentence-transformers library")
            return []
            
        # Get embedding for query
        query_vector = self.model.encode(query)
        
        # Calculate similarity with all projects
        similarities = []
        for project_vector in self.embeddings["projects"]:
            # Calculate cosine similarity
            similarity = np.dot(query_vector, project_vector) / (np.linalg.norm(query_vector) * np.linalg.norm(project_vector))
            similarities.append(float(similarity))
        
        # Create list of (index, similarity) tuples
        project_scores = [(i, score) for i, score in enumerate(similarities)]
        
        # Sort by similarity (descending)
        project_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Filter by threshold and get top results
        results = []
        for i, score in project_scores:
            if score >= threshold and len(results) < limit:
                project = self.projects[i].copy()
                project['_score'] = score  # Add score for debugging
                results.append(project)
        
        return results
    
    def search_awards(self, query: str, limit: int = 10, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Search for awards using vector similarity"""
        if not self.embedding_available:
            print("Warning: Vector search unavailable without sentence-transformers library")
            return []
            
        # Get embedding for query
        query_vector = self.model.encode(query)
        
        # Calculate similarity with all awards
        similarities = []
        for award_vector in self.embeddings["awards"]:
            # Calculate cosine similarity
            similarity = np.dot(query_vector, award_vector) / (np.linalg.norm(query_vector) * np.linalg.norm(award_vector))
            similarities.append(float(similarity))
        
        # Create list of (index, similarity) tuples
        award_scores = [(i, score) for i, score in enumerate(similarities)]
        
        # Sort by similarity (descending)
        award_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Filter by threshold and get top results
        results = []
        for i, score in award_scores:
            if score >= threshold and len(results) < limit:
                award = self.awards[i].copy()
                award['_score'] = score  # Add score for debugging
                results.append(award)
        
        return results
    
    def search(self, query: str, type: str = "all", limit: int = 10) -> Dict[str, Union[List[Dict[str, Any]], int]]:
        """
        Search for projects and/or awards matching the query
        
        Args:
            query: Search terms
            type: "projects", "awards", or "all"
            limit: Maximum number of results to return for each type
            
        Returns:
            Dictionary with results and timing info
        """
        start_time = time.time()
        
        results = {
            "query": query,
            "type": type,
        }
        
        if type == "projects" or type == "all":
            projects = self.search_projects(query, limit)
            results["projects"] = projects
            results["project_count"] = len(projects)
            
        if type == "awards" or type == "all":
            awards = self.search_awards(query, limit)
            results["awards"] = awards
            results["award_count"] = len(awards)
        
        # Add timing information
        results["execution_time"] = time.time() - start_time
            
        return results


# Example usage
if __name__ == "__main__":
    print("Initializing local vector search engine...")
    engine = LocalVectorSearchEngine()
    
    # Test searches
    test_queries = [
        "water treatment facilities in Arizona",
        "transportation projects with bridges",
        "hospitals in San Antonio",
        "safety excellence awards 2022",
        "build america awards for bridge construction"
    ]
    
    for query in test_queries:
        print(f"\nSearch query: '{query}'")
        results = engine.search(query, "all", 3)
        
        print(f"Found {results.get('project_count', 0)} projects and {results.get('award_count', 0)} awards")
        print(f"Search time: {results.get('execution_time', 0):.3f} seconds")
        
        print("\nTop Projects:")
        for i, project in enumerate(results.get("projects", [])):
            print(f"  {i+1}. {project.get('title', 'Untitled')}")
            if "location" in project:
                print(f"     Location: {project['location']}")
            if "_score" in project:
                print(f"     Score: {project['_score']:.3f}")
        
        print("\nTop Awards:")
        for i, award in enumerate(results.get("awards", [])):
            print(f"  {i+1}. {award.get('title', 'Untitled')}")
            if "organization" in award:
                print(f"     Organization: {award['organization']}")
            if "_score" in award:
                print(f"     Score: {award['_score']:.3f}")