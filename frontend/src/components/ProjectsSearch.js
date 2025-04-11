import React, { useState } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:8000';

function ProjectsSearch() {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!query.trim()) {
      setError('Please enter a search query');
      return;
    }

    setIsLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await axios.post(`${API_URL}/projects`, {
        query: query
      });
      
      setResult(response.data);
    } catch (err) {
      console.error('Error searching projects:', err);
      setError(err.response?.data?.detail || 'An error occurred while searching projects');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="search-container">
      <h2>Projects Search</h2>
      <p>Ask questions about Sundt Construction projects</p>
      
      <form className="search-form" onSubmit={handleSubmit}>
        <input 
          type="text" 
          value={query} 
          onChange={(e) => setQuery(e.target.value)}
          placeholder="E.g., Tell me about water treatment projects"
        />
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Searching...' : 'Search'}
        </button>
      </form>

      {error && <div className="error">{error}</div>}

      {isLoading && <div className="loading">Searching for projects...</div>}

      {result && (
        <div className="results-container">
          <div className="response">
            <h3>Response:</h3>
            <p>{result.response}</p>
          </div>

          {result.projects && result.projects.length > 0 && (
            <>
              <h3>Matching Projects ({result.projects.length})</h3>
              <div className="results-list">
                {result.projects.map((project, index) => (
                  <div className="result-card" key={index}>
                    {project.image_url && (
                      <img src={project.image_url} alt={project.title} />
                    )}
                    <div className="result-card-content">
                      <h3>{project.title}</h3>
                      
                      <div className="result-metadata">
                        {project.location && <p><strong>Location:</strong> {project.location}</p>}
                        {project.client && <p><strong>Client:</strong> {project.client}</p>}
                        {project.value && <p><strong>Value:</strong> {project.value}</p>}
                      </div>
                      
                      {project.description && (
                        <p>{project.description.length > 150 
                          ? `${project.description.substring(0, 150)}...` 
                          : project.description}
                        </p>
                      )}
                      
                      {project.url && (
                        <a href={project.url} target="_blank" rel="noopener noreferrer">
                          View Project
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default ProjectsSearch;