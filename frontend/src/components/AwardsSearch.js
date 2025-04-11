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
    <div className="search-container">
      <h2>Awards Search</h2>
      <p>Ask questions about Sundt Construction awards and recognition</p>
      
      <form className="search-form" onSubmit={handleSubmit}>
        <input 
          type="text" 
          value={query} 
          onChange={(e) => setQuery(e.target.value)}
          placeholder="E.g., What safety awards has Sundt won?"
        />
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Searching...' : 'Search'}
        </button>
      </form>

      {error && <div className="error">{error}</div>}

      {isLoading && <div className="loading">Searching for awards...</div>}

      {result && (
        <div className="results-container">
          <div className="response">
            <h3>Response:</h3>
            <p>{result.response}</p>
          </div>

          {result.awards && result.awards.length > 0 && (
            <>
              <h3>Matching Awards ({result.awards.length})</h3>
              <div className="results-list">
                {result.awards.map((award, index) => (
                  <div className="result-card" key={index}>
                    {award.image_url && (
                      <img src={award.image_url} alt={award.title} />
                    )}
                    <div className="result-card-content">
                      <h3>{award.title}</h3>
                      
                      <div className="result-metadata">
                        {award.organization && <p><strong>Organization:</strong> {award.organization}</p>}
                        {award.category && <p><strong>Category:</strong> {award.category}</p>}
                        {award.date && <p><strong>Date:</strong> {award.date}</p>}
                        {award.year && <p><strong>Year:</strong> {award.year}</p>}
                      </div>
                      
                      {award.description && (
                        <p>{award.description.length > 150 
                          ? `${award.description.substring(0, 150)}...` 
                          : award.description}
                        </p>
                      )}
                      
                      {award.url && (
                        <a href={award.url} target="_blank" rel="noopener noreferrer">
                          View Award
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

export default AwardsSearch;