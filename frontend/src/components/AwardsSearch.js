import React, { useState } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:8000';

function AwardsSearch() {
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
      const response = await axios.post(`${API_URL}/awards`, {
        query: query
      });
      
      setResult(response.data);
    } catch (err) {
      console.error('Error searching awards:', err);
      setError(err.response?.data?.detail || 'An error occurred while searching awards');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container">
      <div className="row mb-4">
        <div className="col-lg-12">
          <h2>Awards Search</h2>
          <p className="text-muted">Ask questions about Sundt Construction awards and recognition</p>
          
          <form onSubmit={handleSubmit}>
            <div className="input-group mb-3">
              <input 
                type="text" 
                className="form-control"
                value={query} 
                onChange={(e) => setQuery(e.target.value)}
                placeholder="E.g., What safety awards has Sundt won?"
                aria-label="Search query"
              />
              <button 
                className="btn btn-success" 
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
              <div className="spinner-border text-success" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
            </div>
          )}

          {result && (
            <div className="mt-4">
              <div className="card mb-4">
                <div className="card-header bg-success text-white">
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

              {result.awards && result.awards.length > 0 && (
                <>
                  <h4 className="mb-3">Matching Awards ({result.awards.length})</h4>
                  <div className="row">
                    {result.awards.map((award, index) => (
                      <div className="col-md-6 col-lg-4 mb-4" key={index}>
                        <div className="card h-100 shadow-sm">
                          {award.image_url && (
                            <img 
                              src={award.image_url} 
                              className="card-img-top"
                              alt={award.title} 
                              style={{height: '200px', objectFit: 'cover'}}
                            />
                          )}
                          <div className="card-body">
                            <h5 className="card-title">{award.title}</h5>
                            <div className="card-text">
                              <div className="mb-2">
                                {award.organization && (
                                  <p className="mb-1"><strong>Organization:</strong> {award.organization}</p>
                                )}
                                {award.category && (
                                  <p className="mb-1"><strong>Category:</strong> {award.category}</p>
                                )}
                                {award.date && (
                                  <p className="mb-1"><strong>Date:</strong> {award.date}</p>
                                )}
                                {award.year && !award.date && (
                                  <p className="mb-1"><strong>Year:</strong> {award.year}</p>
                                )}
                              </div>
                              
                              {award.description && (
                                <p className="text-muted">
                                  {award.description.length > 150 
                                    ? `${award.description.substring(0, 150)}...` 
                                    : award.description}
                                </p>
                              )}
                              
                              {award.projects && award.projects.length > 0 && (
                                <div className="mt-2">
                                  <p className="mb-1"><strong>Related Projects:</strong></p>
                                  <ul className="list-group list-group-flush">
                                    {award.projects.slice(0, 3).map((project, idx) => (
                                      <li key={idx} className="list-group-item py-1 px-0 border-0">
                                        {project.url ? (
                                          <a 
                                            href={project.url} 
                                            target="_blank" 
                                            rel="noopener noreferrer"
                                            className="text-decoration-none"
                                          >
                                            {project.title}
                                          </a>
                                        ) : (
                                          project.title
                                        )}
                                      </li>
                                    ))}
                                    {award.projects.length > 3 && (
                                      <li className="list-group-item py-1 px-0 border-0 text-success">
                                        +{award.projects.length - 3} more projects
                                      </li>
                                    )}
                                  </ul>
                                </div>
                              )}
                            </div>
                          </div>
                          {award.url && (
                            <div className="card-footer bg-white border-top-0">
                              <a 
                                href={award.url} 
                                className="btn btn-outline-success btn-sm"
                                target="_blank" 
                                rel="noopener noreferrer"
                              >
                                View award details →
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

export default AwardsSearch;