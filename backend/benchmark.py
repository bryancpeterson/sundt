
import os
import time
import shutil
import sys
import numpy as np

def copy_file(src, dst):
    """Copy a file and ensure the destination directory exists"""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    print(f"Copied {src} to {dst}")

def run_benchmark(module_name, test_queries, iterations=3):
    """Run benchmark on a specific vector search module"""
    # Dynamically import the module
    module = __import__(module_name)
    LocalVectorSearchEngine = getattr(module, 'LocalVectorSearchEngine')
    
    # Initialize engine
    print(f"\nInitializing {module_name}...")
    start_time = time.time()
    engine = LocalVectorSearchEngine()
    init_time = time.time() - start_time
    print(f"Initialization time: {init_time:.3f} seconds")
    
    # Run search tests
    query_times = []
    
    for i in range(iterations):
        print(f"\nIteration {i+1}/{iterations}")
        
        for query in test_queries:
            print(f"Query: '{query}'", end='', flush=True)
            
            # Measure search time
            start_time = time.time()
            results = engine.search(query, "all", 5)
            query_time = time.time() - start_time
            query_times.append(query_time)
            
            # Print results summary
            project_count = results.get('project_count', 0)
            award_count = results.get('award_count', 0)
            print(f" - Found {project_count} projects, {award_count} awards in {query_time:.3f}s")
    
    # Calculate statistics
    avg_time = np.mean(query_times)
    min_time = np.min(query_times)
    max_time = np.max(query_times)
    p95_time = np.percentile(query_times, 95)
    
    print(f"\nResults for {module_name} ({len(query_times)} queries):")
    print(f"  Average query time: {avg_time:.3f} seconds")
    print(f"  Min query time:     {min_time:.3f} seconds")
    print(f"  Max query time:     {max_time:.3f} seconds")
    print(f"  95th percentile:    {p95_time:.3f} seconds")
    
    return {
        'module': module_name,
        'init_time': init_time,
        'avg_time': avg_time,
        'min_time': min_time,
        'max_time': max_time,
        'p95_time': p95_time
    }

def main():
    # Test queries to run
    test_queries = [
        "water treatment facilities in Arizona",
        "transportation projects with bridges",
        "hospitals in San Antonio",
        "safety excellence awards 2022",
        "build america awards for bridge construction", 
        "sustainability initiatives in construction",
        "educational facilities built by Sundt",
        "energy sector projects"
    ]
    
    # Paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    original_file = os.path.join(current_dir, 'local_vector_search.py')
    backup_file = os.path.join(current_dir, 'local_vector_search_original.py')
    optimized_file = os.path.join(current_dir, 'local_vector_search_optimized.py')
    
    # Create backup of original file
    if not os.path.exists(backup_file):
        copy_file(original_file, backup_file)
    
    # Check if optimized file exists, if not, create it
    if not os.path.exists(optimized_file):
        print(f"Please create {optimized_file} with the optimized implementation")
        return
        
    try:
        # First test the original implementation
        copy_file(backup_file, original_file)
        original_results = run_benchmark('local_vector_search', test_queries)
        
        # Then test the optimized implementation
        copy_file(optimized_file, original_file)
        optimized_results = run_benchmark('local_vector_search', test_queries)
        
        # Calculate improvement percentage
        improvement = (1 - (optimized_results['avg_time'] / original_results['avg_time'])) * 100
        
        print("\n======== COMPARISON SUMMARY ========")
        print(f"Original avg query time:  {original_results['avg_time']:.3f} seconds")
        print(f"Optimized avg query time: {optimized_results['avg_time']:.3f} seconds")
        print(f"Speed improvement:        {improvement:.1f}%")
        
    finally:
        copy_file(backup_file, original_file)
        print("\nRestored original file.")

if __name__ == "__main__":
    main()