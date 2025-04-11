import React, { useState } from 'react';
import './App.css';
import ProjectsSearch from './components/ProjectsSearch';
import AwardsSearch from './components/AwardsSearch';

function App() {
  const [activeTab, setActiveTab] = useState('projects');

  return (
    <div className="App">
      <header className="App-header">
        <h1>Sundt Construction RAG System</h1>
        <div className="tabs">
          <button 
            className={activeTab === 'projects' ? 'active' : ''} 
            onClick={() => setActiveTab('projects')}
          >
            Projects
          </button>
          <button 
            className={activeTab === 'awards' ? 'active' : ''} 
            onClick={() => setActiveTab('awards')}
          >
            Awards
          </button>
        </div>
      </header>
      <main>
        {activeTab === 'projects' ? (
          <ProjectsSearch />
        ) : (
          <AwardsSearch />
        )}
      </main>
      <footer>
        <p>Sundt RAG System - Connected to API at http://localhost:8000</p>
      </footer>
    </div>
  );
}

export default App;