import React, { useState, useEffect } from 'react';
import { Search, Award, Building2, BarChart3, Clock, AlertCircle, CheckCircle, Shield, AlertTriangle, ExternalLink } from 'lucide-react';

// API base URL - adjust if neededß
const API_BASE = 'http://localhost:8000';

const App = () => {
  const [currentPage, setCurrentPage] = useState('search');
  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState('projects');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [injectionBlocked, setInjectionBlocked] = useState(false);
  const [crawlerLoading, setCrawlerLoading] = useState({ projects: false, awards: false });
  const [embeddingsLoading, setEmbeddingsLoading] = useState(false);
  const [systemMessage, setSystemMessage] = useState(null);

  // Search function
  const handleSearch = async () => {
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setInjectionBlocked(false);
    
    try {
      let endpoint;
      let body = null;
      let method = 'GET';
      
      if (searchType === 'projects') {
        endpoint = `${API_BASE}/projects`;
        method = 'POST';
        body = JSON.stringify({ query });
      } else if (searchType === 'awards') {
        endpoint = `${API_BASE}/awards`;
        method = 'POST';
        body = JSON.stringify({ query });
      }

      const response = await fetch(endpoint, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body,
      });

      if (response.status === 400) {
        // Check if it's an injection attempt
        const errorData = await response.text();
        if (errorData.includes('injection')) {
          setInjectionBlocked(true);
          setResults(null);
          return;
        }
        throw new Error(`Search failed: ${response.status}`);
      }

      if (!response.ok) {
        throw new Error(`Search failed: ${response.status}`);
      }

      const data = await response.json();
      
      // Check if the response indicates an injection attempt was detected
      if (!data.success && data.reason && data.reason.toLowerCase().includes('injection')) {
        setInjectionBlocked(true);
        setResults(null);
      } else {
        setResults(data);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Handle Enter key press
  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  // Run crawler function
  const runCrawler = async (type) => {
    setCrawlerLoading(prev => ({ ...prev, [type]: true }));
    setSystemMessage(null);
    
    try {
      const response = await fetch(`${API_BASE}/admin/crawl/${type}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to run ${type} crawler: ${response.status}`);
      }

      const data = await response.json();
      setSystemMessage({
        type: 'success',
        message: `${type.charAt(0).toUpperCase() + type.slice(1)} crawler completed successfully! Found ${data.count || 0} items.`
      });
      
      // Refresh metrics if we're on the metrics page
      if (currentPage === 'metrics') {
        fetchMetrics();
      }
    } catch (err) {
      setSystemMessage({
        type: 'error',
        message: `Error running ${type} crawler: ${err.message}`
      });
    } finally {
      setCrawlerLoading(prev => ({ ...prev, [type]: false }));
    }
  };

  // Generate embeddings function
  const generateEmbeddings = async () => {
    setEmbeddingsLoading(true);
    setSystemMessage(null);
    
    try {
      const response = await fetch(`${API_BASE}/admin/generate-embeddings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to generate embeddings: ${response.status}`);
      }

      const data = await response.json();
      setSystemMessage({
        type: 'success',
        message: `Embeddings generated successfully! Processed ${data.projects_count || 0} projects and ${data.awards_count || 0} awards.`
      });
    } catch (err) {
      setSystemMessage({
        type: 'error',
        message: `Error generating embeddings: ${err.message}`
      });
    } finally {
      setEmbeddingsLoading(false);
    }
  };
  const fetchMetrics = async () => {
    try {
      const response = await fetch(`${API_BASE}/metrics`);
      if (response.ok) {
        const data = await response.json();
        setMetrics(data);
      }
    } catch (err) {
      console.error('Failed to fetch metrics:', err);
    }
  };

  useEffect(() => {
    if (currentPage === 'metrics') {
      fetchMetrics();
    }
  }, [currentPage]);

  // Simple markdown renderer for basic formatting
  const renderMarkdown = (text) => {
    if (!text) return text;
    
    return text
      // Headers: ### text
      .replace(/^### (.*$)/gm, '<h3 class="text-lg font-semibold text-gray-900 mt-4 mb-2">$1</h3>')
      .replace(/^## (.*$)/gm, '<h2 class="text-xl font-semibold text-gray-900 mt-4 mb-2">$1</h2>')
      .replace(/^# (.*$)/gm, '<h1 class="text-2xl font-bold text-gray-900 mt-4 mb-2">$1</h1>')
      // Bold text: **text** or __text__
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/__(.*?)__/g, '<strong>$1</strong>')
      // Italic text: *text* or _text_
      .replace(/(?<!\*)\*([^*]+?)\*(?!\*)/g, '<em>$1</em>')
      .replace(/(?<!_)_([^_]+?)_(?!_)/g, '<em>$1</em>')
      // Line breaks
      .replace(/\n/g, '<br/>');
  };
  const getTotalInjectionAttempts = () => {
    if (!metrics) return 0;
    const projectsAttempts = metrics.projects.injection_attempts?.length || 0;
    const awardsAttempts = metrics.awards.injection_attempts?.length || 0;
    return projectsAttempts + awardsAttempts;
  };

  // Helper function to get recent injection attempts
  const getRecentInjectionAttempts = () => {
    if (!metrics) return [];
    
    const allAttempts = [
      ...(metrics.projects.injection_attempts || []).map(attempt => ({...attempt, agent: 'Projects'})),
      ...(metrics.awards.injection_attempts || []).map(attempt => ({...attempt, agent: 'Awards'}))
    ];
    
    // Sort by date (most recent first) and take top 10
    // First sort by date, then by array index (most recent entries last in array)
    return allAttempts
      .map((attempt, originalIndex) => ({...attempt, originalIndex}))
      .sort((a, b) => {
        // First compare dates
        const dateComparison = new Date(b.date) - new Date(a.date);
        if (dateComparison !== 0) return dateComparison;
        
        // If dates are the same, sort by original index (most recent last)
        return b.originalIndex - a.originalIndex;
      })
      .slice(0, 10);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Building2 className="h-8 w-8 text-blue-600" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Sundt Construction</h1>
                <p className="text-sm text-gray-600">Project &amp; Awards Intelligence</p>
              </div>
            </div>
            <nav className="flex space-x-1">
              <button
                onClick={() => setCurrentPage('search')}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  currentPage === 'search'
                    ? 'bg-blue-100 text-blue-700 font-medium'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                <Search className="h-4 w-4 inline mr-2" />
                Search
              </button>
              <button
                onClick={() => setCurrentPage('metrics')}
                className={`px-4 py-2 rounded-lg transition-colors relative ${
                  currentPage === 'metrics'
                    ? 'bg-blue-100 text-blue-700 font-medium'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                <BarChart3 className="h-4 w-4 inline mr-2" />
                Metrics
                {getTotalInjectionAttempts() > 0 && (
                  <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
                    {getTotalInjectionAttempts()}
                  </span>
                )}
              </button>
              <button
                onClick={() => setCurrentPage('admin')}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  currentPage === 'admin'
                    ? 'bg-blue-100 text-blue-700 font-medium'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                <Building2 className="h-4 w-4 inline mr-2" />
                Admin
              </button>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      {currentPage === 'search' ? (
        <div className="max-w-4xl mx-auto px-6 py-8">
          {/* System Message */}
          {systemMessage && (
            <div className={`mb-6 p-4 rounded-lg border ${
              systemMessage.type === 'success' 
                ? 'bg-green-50 border-green-200 text-green-700' 
                : 'bg-red-50 border-red-200 text-red-700'
            }`}>
              <div className="flex items-center">
                {systemMessage.type === 'success' ? (
                  <CheckCircle className="h-5 w-5 mr-2" />
                ) : (
                  <AlertCircle className="h-5 w-5 mr-2" />
                )}
                <span>{systemMessage.message}</span>
              </div>
            </div>
          )}
          {/* Search Input */}
          <div className="mb-8">
            <div className="space-y-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-5 w-5" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Search for Sundt projects and awards..."
                  className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-lg"
                />
              </div>
              
              <div className="flex items-center space-x-4">
                <div className="flex space-x-2">
                  <button
                    type="button"
                    onClick={() => setSearchType('projects')}
                    className={`px-4 py-2 rounded-lg border transition-colors ${
                      searchType === 'projects'
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    <Building2 className="h-4 w-4 inline mr-2" />
                    Projects
                  </button>
                  <button
                    type="button"
                    onClick={() => setSearchType('awards')}
                    className={`px-4 py-2 rounded-lg border transition-colors ${
                      searchType === 'awards'
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    <Award className="h-4 w-4 inline mr-2" />
                    Awards
                  </button>
                </div>
                
                <button
                  onClick={handleSearch}
                  disabled={loading || !query.trim()}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? 'Searching...' : 'Search'}
                </button>
              </div>
            </div>
          </div>

          {/* Injection Attempt Blocked Alert */}
          {injectionBlocked && (
            <div className="mb-6 p-6 bg-red-50 border-2 border-red-200 rounded-lg">
              <div className="flex items-start space-x-3">
                <Shield className="h-6 w-6 text-red-600 mt-0.5 flex-shrink-0" />
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-red-800 mb-2">
                    Security Alert: Potential Prompt Injection Detected
                  </h3>
                  <p className="text-red-700 mb-3">
                    Your query appears to contain instructions that could be attempting to override the system's normal operation. 
                    For security reasons, this type of query has been blocked.
                  </p>
                  <div className="mt-3 text-sm text-red-700">
                    <p className="font-medium">Please try searching with:</p>
                    <ul className="list-disc list-inside mt-1 space-y-1">
                      <li>Specific project names or locations</li>
                      <li>Award types or organizations</li>
                      <li>Construction industry terms</li>
                      <li>Years or time periods</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Error State */}
          {error && !injectionBlocked && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <div className="flex items-center">
                <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
                <span className="text-red-700">Error: {error}</span>
              </div>
            </div>
          )}

          {/* Loading State */}
          {loading && (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Searching Sundt database...</p>
            </div>
          )}

          {/* Results */}
          {results && !loading && !injectionBlocked && (
            <div className="space-y-6">
              {/* Results Summary */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <CheckCircle className="h-5 w-5 text-blue-600 mr-2" />
                    <span className="text-blue-700 font-medium">
                      Search completed successfully
                    </span>
                  </div>
                  {results.execution_time && (
                    <span className="text-sm text-blue-600">
                      <Clock className="h-4 w-4 inline mr-1" />
                      {(results.execution_time * 1000).toFixed(0)}ms
                    </span>
                  )}
                </div>
              </div>

              {/* AI Response */}
              {results.response && (
                <div className="bg-white border border-gray-200 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">Response</h3>
                  <div 
                    className="text-gray-700 leading-relaxed prose max-w-none"
                    dangerouslySetInnerHTML={{ 
                      __html: renderMarkdown(results.response) 
                    }}
                  />
                </div>
              )}

              {/* Projects Results */}
              {results.projects && results.projects.length > 0 && (
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">
                    Projects ({results.project_count || results.projects.length})
                  </h3>
                  <div className="grid gap-4">
                    {results.projects.map((project, index) => (
                      <div key={index} className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow">
                        <div className="flex justify-between items-start mb-3">
                          <h4 className="text-lg font-semibold text-gray-900">{project.title}</h4>
                          {project._score && (
                            <div className="relative group">
                              <span className="text-sm text-blue-600 bg-blue-100 px-2 py-1 rounded cursor-help">
                                Score: {(project._score * 100).toFixed(0)}%
                              </span>
                              <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-800 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-10 min-w-64">
                                <div className="text-left">
                                  <div className="font-medium mb-2 text-center">Score Calculation Details</div>
                                  <div className="space-y-1">
                                    <div>Base Vector Score: {((project._score || 0) / (1 + (project._boost || 0) * 0.1)).toFixed(3)}</div>
                                    {project._keyword_matches > 0 && (
                                      <div>Keyword Matches: {project._keyword_matches} ({(project._keyword_matches * 0.1 * 100).toFixed(0)}% boost)</div>
                                    )}
                                    {project._boost > 0 && (
                                      <div>Field Boosts: +{project._boost.toFixed(1)} ({(project._boost * 0.1 * 100).toFixed(0)}% boost)</div>
                                    )}
                                    <div className="border-t border-gray-600 pt-1 mt-2">
                                      <div className="font-medium">Final Score: {(project._score * 100).toFixed(1)}%</div>
                                    </div>
                                  </div>
                                </div>
                                <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-800"></div>
                              </div>
                            </div>
                          )}
                        </div>
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-gray-600 mb-4">
                          {project.location && (
                            <div><span className="font-medium">Location:</span> {project.location}</div>
                          )}
                          {project.client && (
                            <div><span className="font-medium">Client:</span> {project.client}</div>
                          )}
                          {project.value && (
                            <div><span className="font-medium">Value:</span> {project.value}</div>
                          )}
                          {project.delivery_method && (
                            <div><span className="font-medium">Delivery Method:</span> {project.delivery_method}</div>
                          )}
                        </div>

                        {project.description && (
                          <p className="text-gray-700 text-sm leading-relaxed">
                            {project.description.length > 200 
                              ? `${project.description.slice(0, 200)}...` 
                              : project.description}
                          </p>
                        )}

                        {project.features && project.features.length > 0 && (
                          <div className="mt-3">
                            <span className="text-sm font-medium text-gray-900">Key Features:</span>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {project.features.slice(0, 3).map((feature, i) => (
                                <span key={i} className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded">
                                  {feature}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {project.url && (
                          <a
                            href={project.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 text-sm flex items-center mt-2"
                            title="View full project details"
                          >
                            <ExternalLink className="h-4 w-4 mr-1" />
                            View Project Details
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Awards Results */}
              {results.awards && results.awards.length > 0 && (
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">
                    Awards ({results.award_count || results.awards.length})
                  </h3>
                  <div className="grid gap-4">
                    {results.awards.map((award, index) => (
                      <div key={index} className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow">
                        <div className="flex justify-between items-start mb-3">
                          <h4 className="text-lg font-semibold text-gray-900">{award.title}</h4>
                          {award._score && (
                            <div className="relative group">
                              <span className="text-sm text-blue-600 bg-blue-100 px-2 py-1 rounded cursor-help">
                                Score: {(award._score * 100).toFixed(0)}%
                              </span>
                              <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-800 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-10 min-w-64">
                                <div className="text-left">
                                  <div className="font-medium mb-2 text-center">Score Calculation Details</div>
                                  <div className="space-y-1">
                                    <div>Base Vector Score: {((award._score || 0) / (1 + (award._boost || 0) * 0.1)).toFixed(3)}</div>
                                    {award._keyword_matches > 0 && (
                                      <div>Keyword Matches: {award._keyword_matches} ({(award._keyword_matches * 0.1 * 100).toFixed(0)}% boost)</div>
                                    )}
                                    {award._boost > 0 && (
                                      <div>Field Boosts: +{award._boost.toFixed(1)} ({(award._boost * 0.1 * 100).toFixed(0)}% boost)</div>
                                    )}
                                    <div className="border-t border-gray-600 pt-1 mt-2">
                                      <div className="font-medium">Final Score: {(award._score * 100).toFixed(1)}%</div>
                                    </div>
                                  </div>
                                </div>
                                <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-800"></div>
                              </div>
                            </div>
                          )}
                        </div>
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-gray-600 mb-4">
                          {award.organization && (
                            <div><span className="font-medium">Organization:</span> {award.organization}</div>
                          )}
                          {award.category && (
                            <div><span className="font-medium">Category:</span> {award.category}</div>
                          )}
                          {award.date && (
                            <div><span className="font-medium">Date:</span> {award.date}</div>
                          )}
                          {award.year && !award.date && (
                            <div><span className="font-medium">Year:</span> {award.year}</div>
                          )}
                        </div>

                        {award.description && (
                          <p className="text-gray-700 text-sm leading-relaxed">
                            {award.description.length > 200 
                              ? `${award.description.slice(0, 200)}...` 
                              : award.description}
                          </p>
                        )}

                        {award.projects && award.projects.length > 0 && (
                          <div className="mt-3">
                            <span className="text-sm font-medium text-gray-900">Related Projects:</span>
                            <div className="mt-1">
                              {award.projects.map((project, i) => (
                                <span key={i} className="text-sm text-blue-600 hover:text-blue-800 cursor-pointer mr-3">
                                  {project.title}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {award.url && (
                          <a
                            href={award.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-yellow-600 hover:text-yellow-800 text-sm flex items-center mt-2"
                            title="View full award details"
                          >
                            <ExternalLink className="h-4 w-4 mr-1" />
                            View Award Details
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* No Results */}
              {((results.projects && results.projects.length === 0) || 
                (results.awards && results.awards.length === 0)) && 
               !results.response && (
                <div className="text-center py-12">
                  <Search className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">No results found for "{query}"</p>
                  <p className="text-sm text-gray-500 mt-2">Try different search terms</p>
                </div>
              )}
            </div>
          )}
        </div>
      ) : currentPage === 'admin' ? (
        /* Admin Page */
        <div className="max-w-4xl mx-auto px-6 py-8">
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">System Administration</h2>
            <p className="text-gray-600">Manage crawlers and system data</p>
          </div>

          {/* System Message */}
          {systemMessage && (
            <div className={`mb-6 p-4 rounded-lg border ${
              systemMessage.type === 'success' 
                ? 'bg-green-50 border-green-200 text-green-700' 
                : 'bg-red-50 border-red-200 text-red-700'
            }`}>
              <div className="flex items-center">
                {systemMessage.type === 'success' ? (
                  <CheckCircle className="h-5 w-5 mr-2" />
                ) : (
                  <AlertCircle className="h-5 w-5 mr-2" />
                )}
                <span>{systemMessage.message}</span>
              </div>
            </div>
          )}

          <div className="space-y-6">
            {/* Data Collection Section */}
            <div className="bg-white border border-gray-200 rounded-lg p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                <Search className="h-5 w-5 mr-2 text-blue-600" />
                Data Collection
              </h3>
              <p className="text-gray-600 mb-6">
                Run crawlers to collect the latest projects and awards data from Sundt's website.
              </p>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="border border-gray-200 rounded-lg p-4">
                  <h4 className="font-medium text-gray-900 mb-2 flex items-center">
                    <Building2 className="h-4 w-4 mr-2 text-blue-600" />
                    Projects Crawler
                  </h4>
                  <p className="text-sm text-gray-600 mb-4">
                    Collect project information, details, and metadata from Sundt's projects pages.
                  </p>
                  <button
                    onClick={() => runCrawler('projects')}
                    disabled={crawlerLoading.projects}
                    className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {crawlerLoading.projects ? (
                      <div className="flex items-center justify-center">
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                        Running...
                      </div>
                    ) : (
                      'Run Projects Crawler'
                    )}
                  </button>
                </div>

                <div className="border border-gray-200 rounded-lg p-4">
                  <h4 className="font-medium text-gray-900 mb-2 flex items-center">
                    <Award className="h-4 w-4 mr-2 text-yellow-600" />
                    Awards Crawler
                  </h4>
                  <p className="text-sm text-gray-600 mb-4">
                    Collect awards and recognition data from Sundt's awards and recognition pages.
                  </p>
                  <button
                    onClick={() => runCrawler('awards')}
                    disabled={crawlerLoading.awards}
                    className="w-full px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {crawlerLoading.awards ? (
                      <div className="flex items-center justify-center">
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                        Running...
                      </div>
                    ) : (
                      'Run Awards Crawler'
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Search System Section */}
            <div className="bg-white border border-gray-200 rounded-lg p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                <BarChart3 className="h-5 w-5 mr-2 text-green-600" />
                Search System
              </h3>
              <p className="text-gray-600 mb-6">
                Generate vector embeddings for improved search performance. Run this after updating the data with crawlers.
              </p>
              
              <div className="border border-gray-200 rounded-lg p-4">
                <h4 className="font-medium text-gray-900 mb-2 flex items-center">
                  <Search className="h-4 w-4 mr-2 text-green-600" />
                  Vector Embeddings
                </h4>
                <p className="text-sm text-gray-600 mb-4">
                  Generate embeddings for all projects and awards to enable semantic search. This process may take a few minutes.
                </p>
                <button
                  onClick={generateEmbeddings}
                  disabled={embeddingsLoading}
                  className="w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {embeddingsLoading ? (
                    <div className="flex items-center justify-center">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      Generating Embeddings...
                    </div>
                  ) : (
                    'Generate Embeddings'
                  )}
                </button>
              </div>
            </div>

            {/* System Status */}
            <div className="bg-white border border-gray-200 rounded-lg p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                <Clock className="h-5 w-5 mr-2 text-purple-600" />
                System Status
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-blue-50 p-4 rounded-lg">
                  <div className="text-lg font-bold text-blue-600">
                    {metrics?.projects?.total_queries || 0}
                  </div>
                  <div className="text-sm text-blue-700">Total Queries</div>
                </div>
                <div className="bg-green-50 p-4 rounded-lg">
                  <div className="text-lg font-bold text-green-600">
                    Online
                  </div>
                  <div className="text-sm text-green-700">System Status</div>
                </div>
                <div className="bg-purple-50 p-4 rounded-lg">
                  <div className="text-lg font-bold text-purple-600">
                    {getTotalInjectionAttempts()}
                  </div>
                  <div className="text-sm text-purple-700">Security Blocks</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Metrics Page */
        <div className="max-w-6xl mx-auto px-6 py-8">
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">System Metrics</h2>
            <p className="text-gray-600">Real-time analytics and performance data</p>
          </div>

          {metrics ? (
            <div className="space-y-6">
              {/* Security Overview */}
              <div className="bg-white border border-gray-200 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                  <Shield className="h-5 w-5 mr-2 text-red-600" />
                  Security Overview
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                  <div className="bg-red-50 p-4 rounded-lg border border-red-200">
                    <div className="text-2xl font-bold text-red-600">
                      {getTotalInjectionAttempts()}
                    </div>
                    <div className="text-sm text-red-700">Total Injection Attempts</div>
                  </div>
                  <div className="bg-yellow-50 p-4 rounded-lg border border-yellow-200">
                    <div className="text-2xl font-bold text-yellow-600">
                      {metrics.projects.injection_attempts?.length || 0}
                    </div>
                    <div className="text-sm text-yellow-700">Projects Agent Blocks</div>
                  </div>
                  <div className="bg-orange-50 p-4 rounded-lg border border-orange-200">
                    <div className="text-2xl font-bold text-orange-600">
                      {metrics.awards.injection_attempts?.length || 0}
                    </div>
                    <div className="text-sm text-orange-700">Awards Agent Blocks</div>
                  </div>
                </div>

                {/* Recent Injection Attempts */}
                {getRecentInjectionAttempts().length > 0 && (
                  <div>
                    <h4 className="text-md font-semibold text-gray-900 mb-3 flex items-center">
                      <AlertTriangle className="h-4 w-4 mr-2 text-red-500" />
                      Recent Injection Attempts
                    </h4>
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {getRecentInjectionAttempts().map((attempt, index) => (
                        <div key={index} className="bg-gray-50 p-3 rounded border border-gray-200">
                          <div className="flex justify-between items-start mb-1">
                            <span className="text-sm font-medium text-gray-900">
                              {attempt.agent} Agent
                            </span>
                            <span className="text-xs text-gray-500">{attempt.date}</span>
                          </div>
                          <div className="text-sm text-gray-700 font-mono bg-white p-2 rounded border border-gray-200">
                            "{attempt.query}"
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Projects Metrics */}
              <div className="bg-white border border-gray-200 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                  <Building2 className="h-5 w-5 mr-2 text-blue-600" />
                  Projects Agent
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-blue-600">
                      {metrics.projects.total_queries || 0}
                    </div>
                    <div className="text-sm text-blue-700">Total Queries</div>
                  </div>
                  <div className="bg-green-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-green-600">
                      {metrics.projects.query_times && metrics.projects.query_times.length > 0
                        ? `${(metrics.projects.query_times.reduce((a, b) => a + b, 0) / metrics.projects.query_times.length).toFixed(2)}s`
                        : '0s'}
                    </div>
                    <div className="text-sm text-green-700">Avg Response Time</div>
                  </div>
                  <div className="bg-yellow-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-yellow-600">
                      {metrics.projects.injection_attempts ? metrics.projects.injection_attempts.length : 0}
                    </div>
                    <div className="text-sm text-yellow-700">Injection Attempts</div>
                  </div>
                  <div className="bg-purple-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-purple-600">
                      {Object.keys(metrics.projects.queries_by_date || {}).length}
                    </div>
                    <div className="text-sm text-purple-700">Active Days</div>
                  </div>
                </div>
              </div>

              {/* Awards Metrics */}
              <div className="bg-white border border-gray-200 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                  <Award className="h-5 w-5 mr-2 text-yellow-600" />
                  Awards Agent
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-blue-600">
                      {metrics.awards.total_queries || 0}
                    </div>
                    <div className="text-sm text-blue-700">Total Queries</div>
                  </div>
                  <div className="bg-green-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-green-600">
                      {metrics.awards.query_times && metrics.awards.query_times.length > 0
                        ? `${(metrics.awards.query_times.reduce((a, b) => a + b, 0) / metrics.awards.query_times.length).toFixed(2)}s`
                        : '0s'}
                    </div>
                    <div className="text-sm text-green-700">Avg Response Time</div>
                  </div>
                  <div className="bg-yellow-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-yellow-600">
                      {metrics.awards.injection_attempts ? metrics.awards.injection_attempts.length : 0}
                    </div>
                    <div className="text-sm text-yellow-700">Injection Attempts</div>
                  </div>
                  <div className="bg-purple-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-purple-600">
                      {Object.keys(metrics.awards.queries_by_date || {}).length}
                    </div>
                    <div className="text-sm text-purple-700">Active Days</div>
                  </div>
                </div>
              </div>

              {/* Popular Terms */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white border border-gray-200 rounded-lg p-6">
                  <h4 className="text-md font-semibold text-gray-900 mb-3">Popular Project Terms</h4>
                  <div className="space-y-2">
                    {Object.entries(metrics.projects.popular_terms || {})
                      .sort(([,a], [,b]) => b - a)
                      .slice(0, 8)
                      .map(([term, count]) => (
                        <div key={term} className="flex justify-between items-center">
                          <span className="text-sm text-gray-700">{term}</span>
                          <span className="text-sm font-medium text-blue-600">{count}</span>
                        </div>
                      ))}
                  </div>
                </div>

                <div className="bg-white border border-gray-200 rounded-lg p-6">
                  <h4 className="text-md font-semibold text-gray-900 mb-3">Popular Award Terms</h4>
                  <div className="space-y-2">
                    {Object.entries(metrics.awards.popular_terms || {})
                      .sort(([,a], [,b]) => b - a)
                      .slice(0, 8)
                      .map(([term, count]) => (
                        <div key={term} className="flex justify-between items-center">
                          <span className="text-sm text-gray-700">{term}</span>
                          <span className="text-sm font-medium text-yellow-600">{count}</span>
                        </div>
                      ))}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-12">
              <div className="animate-pulse space-y-4">
                <div className="h-4 bg-gray-200 rounded w-1/4 mx-auto"></div>
                <div className="h-4 bg-gray-200 rounded w-1/2 mx-auto"></div>
              </div>
              <p className="text-gray-600 mt-4">Loading metrics...</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default App;