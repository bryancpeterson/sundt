import sys
import time
from local_vector_search import LocalVectorSearchEngine

def test_vector_search():
    # Initialize the vector search engine
    print("Initializing local vector search engine...")
    engine = LocalVectorSearchEngine()
    
    # Print counts of loaded data
    print(f"Loaded {len(engine.projects)} projects")
    print(f"Loaded {len(engine.awards)} awards")
    
    # Test searches that keyword search had trouble with
    print("\n--- SEMANTIC SEARCH TESTS ---")
    test_queries = [
        "San Antonio projects",  # Should find actual San Antonio projects
        "2022 awards",           # Should be better at finding date-based content
        "Engineering News-Record awards",  # Should find all ENR mentions even if abbreviated
        "water treatment in Arizona",     # Location-aware searching
        "Bridge construction with safety focus"  # Conceptual matching
    ]
    
    total_time = 0
    
    for query in test_queries:
        print(f"\nSearch query: '{query}'")
        start_time = time.time()
        results = engine.search(query, "all", 3)
        query_time = time.time() - start_time
        total_time += query_time
        
        print(f"Found {results.get('project_count', 0)} projects and {results.get('award_count', 0)} awards")
        print(f"Search time: {query_time:.3f} seconds")
        
        # Print project results
        print("\nTop Projects:")
        for i, project in enumerate(results.get("projects", [])):
            print(f"  {i+1}. {project.get('title', 'Untitled')}")
            if "location" in project:
                print(f"     Location: {project['location']}")
            if "_score" in project:
                print(f"     Relevance: {project['_score']:.2f}")
        
        # Print award results
        print("\nTop Awards:")
        for i, award in enumerate(results.get("awards", [])):
            print(f"  {i+1}. {award.get('title', 'Untitled')}")
            if "organization" in award:
                print(f"     Organization: {award['organization']}")
            if "_score" in award:
                print(f"     Relevance: {award['_score']:.2f}")
    
    print(f"\nTotal search time for {len(test_queries)} queries: {total_time:.3f} seconds")
    print(f"Average search time: {total_time/len(test_queries):.3f} seconds per query")
    
    # Compare with specific problem cases from keyword search
    print("\n--- TARGETED COMPARISON TESTS ---")
    comparison_queries = [
        "San Antonio",           # Previously matched San Diego
        "ENR",                  # Previously found only one match
        "2022"                  # Previously found no awards
    ]
    
    for query in comparison_queries:
        print(f"\nQuery: '{query}'")
        results = engine.search(query, "all", 3)
        
        print(f"Found {results.get('project_count', 0)} projects and {results.get('award_count', 0)} awards")
        
        print("Top matches:")
        for i, project in enumerate(results.get("projects", [])[:2]):
            print(f"  Project: {project.get('title', 'Untitled')}")
        
        for i, award in enumerate(results.get("awards", [])[:2]):
            print(f"  Award: {award.get('title', 'Untitled')}")

if __name__ == "__main__":
    test_vector_search()