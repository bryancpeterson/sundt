import os
import json
import numpy as np
from typing import List, Dict, Any, Union, Optional
import re
import time

class LocalVectorSearchEngine:
    """
    Local vector search using sentence-transformers - keeps everything offline and fast
    """
    
    def __init__(self, data_dir="data", use_cached_embeddings=True):
        self.data_dir = data_dir
        self.projects_file = os.path.join(data_dir, "projects.json")
        self.awards_file = os.path.join(data_dir, "awards.json")
        self.embeddings_file = os.path.join(data_dir, "local_embeddings.json")
        
        # Import sentence-transformers only when we need it
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer('all-MiniLM-L6-v2')  # Small, fast, decent quality
            self.embedding_available = True
        except ImportError:
            print("Warning: sentence-transformers library not working properly, try using sentence-transformers==2.2.2")
            self.embedding_available = False
        
        # Load data first
        self.projects = self._load_json_data(self.projects_file, "projects")
        self.awards = self._load_json_data(self.awards_file, "awards")
        
        # Generate or load embeddings
        if self.embedding_available:
            self.embeddings = self._load_or_generate_embeddings(use_cached_embeddings)
        else:
            # Dummy embeddings for when library isn't available
            self.embeddings = {"projects": np.array([]), "awards": np.array([]), "created_at": 0}
    
    def _load_json_data(self, file_path: str, key: str) -> List[Dict[str, Any]]:
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
        # Try to load existing embeddings first
        if use_cached and os.path.exists(self.embeddings_file):
            try:
                with open(self.embeddings_file, 'r', encoding='utf-8') as f:
                    print(f"Loading cached embeddings from {self.embeddings_file}")
                    data = json.load(f)
                    
                    # Convert back to numpy arrays for efficient computation
                    data["projects"] = np.array(data["projects"])
                    data["awards"] = np.array(data["awards"])
                    
                    return data
            except Exception as e:
                print(f"Error loading embeddings: {e}")
        
        # Generate new embeddings
        print("Generating new embeddings...")
        start_time = time.time()
        embeddings = {
            "projects": None,
            "awards": None,
            "created_at": time.time()
        }
        
        # Process projects
        project_texts = []
        for project in self.projects:
            text = self._prepare_text_for_embedding(project, "project")
            project_texts.append(text)
        
        # Batch encode for efficiency, normalize for cosine similarity
        print(f"Generating embeddings for {len(project_texts)} projects...")
        embeddings["projects"] = self.model.encode(project_texts, normalize_embeddings=True)
        
        # Process awards
        award_texts = []
        for award in self.awards:
            text = self._prepare_text_for_embedding(award, "award")
            award_texts.append(text)
        
        print(f"Generating embeddings for {len(award_texts)} awards...")
        embeddings["awards"] = self.model.encode(award_texts, normalize_embeddings=True)
        
        # Save to cache for next time
        serializable_embeddings = {
            "projects": embeddings["projects"].tolist(),
            "awards": embeddings["awards"].tolist(),
            "created_at": embeddings["created_at"]
        }
        
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.embeddings_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_embeddings, f)
        
        print(f"Embeddings generated in {time.time() - start_time:.2f} seconds")
        return embeddings
    
    def _prepare_text_for_embedding(self, item: Dict[str, Any], item_type: str) -> str:
        # Create searchable text representation for each item
        if item_type == "project":
            parts = [
                f"Title: {item.get('title', '')}",
                f"Description: {item.get('description', item.get('overview', ''))}",
                f"Location: {item.get('location', '')}",
                f"Client: {item.get('client', '')}"
            ]
            
            # Add features if they exist
            if "features" in item and item["features"]:
                features = item["features"]
                if isinstance(features, list):
                    features_text = ", ".join(features)
                else:
                    features_text = str(features)
                parts.append(f"Features: {features_text}")
            
            # Add specialties too
            if "specialties" in item and item["specialties"]:
                specialties = item["specialties"]
                if isinstance(specialties, list):
                    specialties_text = ", ".join(specialties)
                else:
                    specialties_text = str(specialties)
                parts.append(f"Specialties: {specialties_text}")
            
        elif item_type == "award":
            parts = [
                f"Title: {item.get('title', '')}",
                f"Organization: {item.get('organization', '')}",
                f"Category: {item.get('category', '')}",
                f"Description: {item.get('description', '')}",
                f"Year: {item.get('year', item.get('date', ''))}"
            ]
            
            # Include related projects if available
            if "projects" in item and item["projects"]:
                projects = item["projects"]
                if isinstance(projects, list):
                    project_titles = [p.get("title", "") for p in projects]
                    parts.append(f"Projects: {', '.join(project_titles)}")
        
        # Clean up and join
        text = "\n".join(part for part in parts if part.strip())
        return text
    
    def search_projects(self, query: str, limit: int = 10, threshold: float = 0.3) -> List[Dict[str, Any]]:
        if not self.embedding_available:
            print("Warning: Vector search unavailable without sentence-transformers library")
            return []
            
        # Get query embedding (normalized for cosine similarity)
        query_vector = self.model.encode(query, normalize_embeddings=True)
        
        # Compute similarity with all projects (dot product = cosine similarity when normalized)
        similarities = np.dot(query_vector, self.embeddings["projects"].T)
        
        # Get indices and sort by similarity
        indices = np.arange(len(similarities))
        project_scores = list(zip(indices, similarities))
        project_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Filter and format results
        results = []
        for i, score in project_scores:
            if score >= threshold and len(results) < limit:
                project = self.projects[i].copy()
                project['_score'] = float(score)  # For debugging/ranking
                project['_rank'] = len(results) + 1
                results.append(project)
        
        return results
    
    def search_awards(self, query: str, limit: int = 10, threshold: float = 0.3) -> List[Dict[str, Any]]:
        if not self.embedding_available:
            print("Warning: Vector search unavailable without sentence-transformers library")
            return []
            
        query_vector = self.model.encode(query, normalize_embeddings=True)
        similarities = np.dot(query_vector, self.embeddings["awards"].T)
        
        indices = np.arange(len(similarities))
        award_scores = list(zip(indices, similarities))
        award_scores.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for i, score in award_scores:
            if score >= threshold and len(results) < limit:
                award = self.awards[i].copy()
                award['_score'] = float(score)
                award['_rank'] = len(results) + 1
                results.append(award)
        
        return results
    
    def search(self, query: str, type: str = "all", limit: int = 10, threshold: float = 0.3) -> Dict[str, Union[List[Dict[str, Any]], int]]:
        """
        Main search interface - handles projects, awards, or both
        """
        start_time = time.time()
        
        results = {
            "query": query,
            "type": type,
        }
        
        if type == "projects" or type == "all":
            projects = self.search_projects(query, limit, threshold)
            results["projects"] = projects
            results["project_count"] = len(projects)
            
        if type == "awards" or type == "all":
            awards = self.search_awards(query, limit, threshold)
            results["awards"] = awards
            results["award_count"] = len(awards)
        
        results["execution_time"] = time.time() - start_time
            
        return results


# Quick test when running directly
if __name__ == "__main__":
    print("Initializing local vector search engine...")
    engine = LocalVectorSearchEngine()
    
    # Some test queries to show it works
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