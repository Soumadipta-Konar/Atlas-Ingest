import { useState, useEffect } from 'react';
import axios from 'axios';
import './index.css';

const API_BASE = 'http://localhost:5000/api';

function App() {
  const [activeTab, setActiveTab] = useState('startups');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    axios.get(`${API_BASE}/${activeTab}`)
      .then(res => {
        setData(res.data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, [activeTab]);

  return (
    <div>
      <h1>Atlas Ingest Explorer</h1>
      
      <div className="tabs">
        {['startups', 'papers', 'products', 'news', 'jobs'].map(tab => (
          <button
            key={tab}
            className={`tab-button ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      <div className="glass-panel">
        {loading ? (
          <div className="loading">Loading {activeTab}...</div>
        ) : data.length === 0 ? (
          <div className="loading">No data found. Ensure the pipeline has run.</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  {Object.keys(data[0])
                    .filter(key => key !== '_id')
                    .slice(0, 6)
                    .map(key => (
                      <th key={key}>{key.replace(/([A-Z])/g, ' $1').trim()}</th>
                    ))}
                </tr>
              </thead>
              <tbody>
                {data.map((item, i) => (
                  <tr key={i}>
                    {Object.entries(item)
                      .filter(([key]) => key !== '_id')
                      .slice(0, 6)
                      .map(([key, val], j) => (
                        <td key={j}>
                          {typeof val === 'string' && val.startsWith('http') ? (
                            <a href={val} target="_blank" rel="noreferrer">Link</a>
                          ) : (
                            String(val).length > 60 ? String(val).substring(0, 60) + '...' : String(val)
                          )}
                        </td>
                      ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
