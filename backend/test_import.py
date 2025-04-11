# Save this as test_import.py
try:
    from sentence_transformers import SentenceTransformer
    print("Successfully imported sentence_transformers")
    
    # Try to load a model to make sure the installation is complete
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Successfully loaded model")
    
    # Try a basic embedding
    embedding = model.encode("Test sentence")
    print(f"Generated embedding of size {len(embedding)}")
    
except Exception as e:
    print(f"Error: {e}")