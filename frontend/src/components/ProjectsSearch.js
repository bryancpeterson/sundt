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
    <div className="container">
      <div className="row mb-4">
        <div className="col-lg-12">
          <h2>Projects Search</h2>
          <p className="text-muted">Ask questions about Sundt Construction projects</p>
          
          <form onSubmit={handleSubmit}>
            <div className="input-group mb-3">
              <input 
                type="text" 
                className="form-control"
                value={query} 
                onChange={(e) => setQuery(e.target.value)}
                placeholder="E.g., Tell me about water treatment projects in Arizona"
                aria-label="Search query"
              />
              <button 
                className="btn btn-primary" 
                type="submit" 
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                    <span className="ms-2">Searching...</span>
                  </>
                ) : 'Search'}
              </button>
            </div>
          </form>

          {error && (
            <div className="alert alert-danger" role="alert">
              {error}
            </div>
          )}

          {isLoading && !error && (
            <div className="d-flex justify-content-center my-5">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
            </div>
          )}

          {result && (
            <div className="mt-4">
              <div className="card mb-4">
                <div className="card-header bg-primary text-white">
                  <h4 className="mb-0">Response</h4>
                </div>
                <div className="card-body">
                  <p className="card-text">{result.response}</p>
                  <div className="d-flex justify-content-end">
                    <small className="text-muted">
                      Query time: {result.execution_time.toFixed(2)} seconds
                    </small>
                  </div>
                </div>
              </div>

              {result.projects && result.projects.length > 0 && (
                <>
                  <h4 className="mb-3">Matching Projects ({result.projects.length})</h4>
                  <div className="row">
                    {result.projects.map((project, index) => (
                      <div className="col-md-6 col-lg-4 mb-4" key={index}>
                        <div className="card h-100 shadow-sm">
                          {project.image_url && (
                            <img 
                              src={project.image_url} 
                              className="card-img-top"
                              alt={project.title} 
                              style={{height: '200px', objectFit: 'cover'}}
                            />
                          )}
                          <div className="card-body">
                            <h5 className="card-title">{project.title}</h5>
                            <div className="card-text">
                              <div className="mb-2">
                                {project.location && (
                                  <p className="mb-1"><strong>Location:</strong> {project.location}</p>
                                )}
                                {project.client && (
                                  <p className="mb-1"><strong>Client:</strong> {project.client}</p>
                                )}
                                {project.value && (
                                  <p className="mb-1"><strong>Value:</strong> {project.value}</p>
                                )}
                                {project.delivery_method && (
                                  <p className="mb-1"><strong>Delivery Method:</strong> {project.delivery_method}</p>
                                )}
                              </div>
                              
                              {project.description && (
                                <p className="text-muted">
                                  {project.description.length > 150 
                                    ? `${project.description.substring(0, 150)}...` 
                                    : project.description}
                                </p>
                              )}
                              
                              {project.features && project.features.length > 0 && (
                                <div className="mt-2">
                                  <p className="mb-1"><strong>Features:</strong></p>
                                  <ul className="list-group list-group-flush">
                                    {Array.isArray(project.features) 
                                      ? project.features.slice(0, 3).map((feature, idx) => (
                                          <li key={idx} className="list-group-item py-1 px-0 border-0">{feature}</li>
                                        ))
                                      : <li className="list-group-item py-1 px-0 border-0">{project.features}</li>
                                    }
                                    {Array.isArray(project.features) && project.features.length > 3 && (
                                      <li className="list-group-item py-1 px-0 border-0 text-primary">
                                        +{project.features.length - 3} more features
                                      </li>
                                    )}
                                  </ul>
                                </div>
                              )}
                            </div>
                          </div>
                          {project.url && (
                            <div className="card-footer bg-white border-top-0">
                              <a 
                                href={project.url} 
                                className="btn btn-outline-primary btn-sm"
                                target="_blank" 
                                rel="noopener noreferrer"
                              >
                                View project details →
                              </a>
                            </div>
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
      </div>
    </div>
  );
}

export default ProjectsSearch;