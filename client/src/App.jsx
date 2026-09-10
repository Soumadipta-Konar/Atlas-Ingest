import { useState, useEffect } from 'react';
import axios from 'axios';
import './index.css';

const API_BASE = 'http://localhost:5000/api';

function App() {
  const [activeTab, setActiveTab] = useState('startups');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  
  const [runTarget, setRunTarget] = useState('papers');
  const [runTopic, setRunTopic] = useState('');
  const [runMax, setRunMax] = useState('');
  const [running, setRunning] = useState(false);
  const [runLog, setRunLog] = useState('');

  const fetchData = () => {
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
  };

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const handleRun = async () => {
    setRunning(true);
    setRunLog('Executing pipeline...\n');
    try {
      const res = await axios.post(`${API_BASE}/run`, {
        target: runTarget,
        topic: runTopic,
        maxRecords: runMax
      });
      setRunLog(prev => prev + res.data.log + '\nExecution Complete.');
      fetchData();
    } catch (err) {
      setRunLog(prev => prev + '\nError: ' + (err.response?.data?.log || err.message));
    }
    setRunning(false);
  };

  return (
    <div>
      <h1>Atlas Ingest</h1>
      
      <div className="control-panel">
        <h2>Execution Pipeline</h2>
        <div className="control-row">
          <select value={runTarget} onChange={e => setRunTarget(e.target.value)}>
            <option value="papers">Papers (Arxiv)</option>
            <option value="startups">Startups (YC)</option>
            <option value="products">Products (PH)</option>
          </select>
          <input 
            type="text" 
            placeholder="Topic (e.g. AI)" 
            value={runTopic} 
            onChange={e => setRunTopic(e.target.value)}
          />
          <input 
            type="number" 
            placeholder="Max Records" 
            value={runMax} 
            onChange={e => setRunMax(e.target.value)}
            style={{ width: '100px' }}
          />
          <button 
            className="run-button" 
            onClick={handleRun}
            disabled={running}
          >
            {running ? 'Running...' : 'Run Pipeline'}
          </button>
        </div>
        {runLog && (
          <div className="status-log">
            {runLog}
          </div>
        )}
      </div>

      <div className="tabs">
        {['startups', 'papers', 'products', 'news', 'jobs'].map(tab => (
          <button
            key={tab}
            className={`tab-button ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="brutalist-panel">
        {loading ? (
          <div className="loading">Fetching {activeTab}...</div>
        ) : data.length === 0 ? (
          <div className="loading">No records found. Run the pipeline above.</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  {Object.keys(data[0])
                    .filter(key => key !== '_id')
                    .slice(0, 6)
                    .map(key => (
                      <th key={key}>{key}</th>
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
                            <a href={val} target="_blank" rel="noreferrer">LINK</a>
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
