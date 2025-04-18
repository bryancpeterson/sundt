import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ProjectsSearch from './components/ProjectsSearch';
import AwardsSearch from './components/AwardsSearch';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css'; // We'll keep minimal custom CSS

// API URL - update this if your backend runs on a different port
const API_URL = 'http://localhost:8000';

function App() {
  const [activeTab, setActiveTab] = useState('projects');
  const [metrics, setMetrics] = useState(null);
  const [metricsLoading, setMetricsLoading] = useState(false);

  // Fetch metrics when dashboard tab is selected
  useEffect(() => {
    if (activeTab === 'dashboard') {
      fetchMetrics();
    }
  }, [activeTab]);

  const fetchMetrics = async () => {
    setMetricsLoading(true);
    try {
      const response = await axios.get(`${API_URL}/metrics`);
      setMetrics(response.data);
    } catch (error) {
      console.error('Error fetching metrics:', error);
    } finally {
      setMetricsLoading(false);
    }
  };

  return (
    <div className="container-fluid py-4">
      <header className="mb-4 pb-3 border-bottom">
        <h1 className="mb-3">Sundt Construction RAG System</h1>
        <ul className="nav nav-tabs">
          <li className="nav-item">
            <button 
              className={`nav-link ${activeTab === 'projects' ? 'active' : ''}`} 
              onClick={() => setActiveTab('projects')}
            >
              Projects
            </button>
          </li>
          <li className="nav-item">
            <button 
              className={`nav-link ${activeTab === 'awards' ? 'active' : ''}`} 
              onClick={() => setActiveTab('awards')}
            >
              Awards
            </button>
          </li>
          <li className="nav-item">
            <button 
              className={`nav-link ${activeTab === 'dashboard' ? 'active' : ''}`} 
              onClick={() => setActiveTab('dashboard')}
            >
              Dashboard
            </button>
          </li>
        </ul>
      </header>
      
      <main className="mb-5">
        {activeTab === 'projects' ? (
          <ProjectsSearch />
        ) : activeTab === 'awards' ? (
          <AwardsSearch />
        ) : (
          <Dashboard metrics={metrics} isLoading={metricsLoading} />
        )}
      </main>
      
      <footer className="border-top pt-3 mt-5 text-center text-muted">
        <p>Sundt RAG System - Connected to API at {API_URL}</p>
      </footer>
    </div>
  );
}

// Dashboard Component
function Dashboard({ metrics, isLoading }) {
  if (isLoading) {
    return (
      <div className="d-flex justify-content-center py-5">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="card p-4 text-center">
        <p className="text-muted">No metrics data available</p>
      </div>
    );
  }

  // Format project data
  const projectMetrics = metrics.projects || {};
  const projectQueries = projectMetrics.total_queries || 0;
  const projectAvgTime = projectMetrics.query_times && projectMetrics.query_times.length > 0 
    ? (projectMetrics.query_times.reduce((sum, time) => sum + time, 0) / projectMetrics.query_times.length).toFixed(3) 
    : "N/A";
  const projectInjections = projectMetrics.injection_attempts?.length || 0;

  // Format award data
  const awardMetrics = metrics.awards || {};
  const awardQueries = awardMetrics.total_queries || 0;
  const awardAvgTime = awardMetrics.query_times && awardMetrics.query_times.length > 0 
    ? (awardMetrics.query_times.reduce((sum, time) => sum + time, 0) / awardMetrics.query_times.length).toFixed(3) 
    : "N/A";
  const awardInjections = awardMetrics.injection_attempts?.length || 0;

  // Format popular search terms
  const getTopTerms = (terms) => {
    if (!terms) return [];
    return Object.entries(terms)
      .sort((a, b) => b[1] - a[1]) // Sort by count (descending)
      .slice(0, 10); // Get top 10
  };

  const projectTopTerms = getTopTerms(projectMetrics.popular_terms);
  const awardTopTerms = getTopTerms(awardMetrics.popular_terms);

  // Format query dates for visualization
  const getDailyQueries = () => {
    const projectDates = projectMetrics.queries_by_date || {};
    const awardDates = awardMetrics.queries_by_date || {};
    
    // Combine and sort dates
    const allDates = [...new Set([...Object.keys(projectDates), ...Object.keys(awardDates)])];
    return allDates.sort().map(date => ({
      date,
      projects: projectDates[date] || 0,
      awards: awardDates[date] || 0
    }));
  };

  const dailyQueries = getDailyQueries();

  return (
    <div className="dashboard-container">
      <h2 className="mb-4">System Metrics & Monitoring</h2>
      
      {/* Summary Cards */}
      <div className="row mb-4">
        <div className="col-md-3 mb-3">
          <div className="card bg-light h-100">
            <div className="card-body">
              <h5 className="card-title">Project Queries</h5>
              <p className="card-text display-4">{projectQueries}</p>
            </div>
          </div>
        </div>
        <div className="col-md-3 mb-3">
          <div className="card bg-light h-100">
            <div className="card-body">
              <h5 className="card-title">Award Queries</h5>
              <p className="card-text display-4">{awardQueries}</p>
            </div>
          </div>
        </div>
        <div className="col-md-3 mb-3">
          <div className="card bg-light h-100">
            <div className="card-body">
              <h5 className="card-title">Avg Response Time</h5>
              <p className="card-text display-4">{projectAvgTime}s</p>
            </div>
          </div>
        </div>
        <div className="col-md-3 mb-3">
          <div className="card bg-light h-100">
            <div className="card-body">
              <h5 className="card-title">Injection Attempts</h5>
              <p className="card-text display-4">{projectInjections + awardInjections}</p>
            </div>
          </div>
        </div>
      </div>
      
      <div className="row mb-4">
        {/* Query History */}
        <div className="col-md-6 mb-4">
          <div className="card h-100">
            <div className="card-header bg-light">
              <h5 className="card-title mb-0">Query History</h5>
            </div>
            <div className="card-body">
              <div className="table-responsive">
                <table className="table table-striped table-hover">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Projects</th>
                      <th>Awards</th>
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dailyQueries.map(day => (
                      <tr key={day.date}>
                        <td>{day.date}</td>
                        <td>{day.projects}</td>
                        <td>{day.awards}</td>
                        <td>{day.projects + day.awards}</td>
                      </tr>
                    ))}
                    {dailyQueries.length === 0 && (
                      <tr>
                        <td colSpan="4" className="text-center">No query history available</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
        
        {/* Popular Search Terms */}
        <div className="col-md-6 mb-4">
          <div className="card h-100">
            <div className="card-header bg-light">
              <h5 className="card-title mb-0">Popular Search Terms</h5>
            </div>
            <div className="card-body">
              <div className="row">
                <div className="col-md-6">
                  <h6 className="border-bottom pb-2 mb-3">Projects</h6>
                  <ul className="list-group">
                    {projectTopTerms.map(([term, count]) => (
                      <li key={term} className="list-group-item d-flex justify-content-between align-items-center">
                        {term}
                        <span className="badge bg-primary rounded-pill">{count}</span>
                      </li>
                    ))}
                    {projectTopTerms.length === 0 && (
                      <li className="list-group-item text-muted">No data available</li>
                    )}
                  </ul>
                </div>
                <div className="col-md-6">
                  <h6 className="border-bottom pb-2 mb-3">Awards</h6>
                  <ul className="list-group">
                    {awardTopTerms.map(([term, count]) => (
                      <li key={term} className="list-group-item d-flex justify-content-between align-items-center">
                        {term}
                        <span className="badge bg-primary rounded-pill">{count}</span>
                      </li>
                    ))}
                    {awardTopTerms.length === 0 && (
                      <li className="list-group-item text-muted">No data available</li>
                    )}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* Injection Attempts */}
      <div className="card mb-4">
        <div className="card-header bg-light">
          <h5 className="card-title mb-0">Prompt Injection Attempts</h5>
        </div>
        <div className="card-body">
          <div className="table-responsive">
            <table className="table table-striped table-hover">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Agent</th>
                  <th>Query</th>
                </tr>
              </thead>
              <tbody>
                {projectMetrics.injection_attempts?.map((attempt, i) => (
                  <tr key={`project-${i}`}>
                    <td>{attempt.date}</td>
                    <td><span className="badge bg-info">Projects</span></td>
                    <td>{attempt.query}</td>
                  </tr>
                ))}
                {awardMetrics.injection_attempts?.map((attempt, i) => (
                  <tr key={`award-${i}`}>
                    <td>{attempt.date}</td>
                    <td><span className="badge bg-warning text-dark">Awards</span></td>
                    <td>{attempt.query}</td>
                  </tr>
                ))}
                {(projectMetrics.injection_attempts?.length === 0 &&
                  awardMetrics.injection_attempts?.length === 0) && (
                  <tr>
                    <td colSpan="3" className="text-center">No injection attempts detected</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;