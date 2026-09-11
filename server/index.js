const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const { spawn } = require('child_process');

const app = express();
const PORT = process.env.PORT || 5000;

// Fix #13: Restrict CORS to configured origin instead of permissive wildcard
const CORS_ORIGIN = process.env.CORS_ORIGIN || 'http://localhost:5173';
app.use(cors({ origin: CORS_ORIGIN }));
app.use(express.json());

const MONGODB_URI = process.env.MONGO_URI || 'mongodb://localhost:27017/atlas_ingest';

mongoose.connect(MONGODB_URI)
  .then(() => console.log('MongoDB Connected'))
  .catch(err => console.log(err));

app.get('/api/papers', async (req, res) => {
  try {
    const db = mongoose.connection.db;
    const items = await db.collection('research_papers').find().sort({_id: -1}).toArray();
    res.json(items);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/startups', async (req, res) => {
  try {
    const db = mongoose.connection.db;
    const items = await db.collection('startups').find().sort({_id: -1}).toArray();
    res.json(items);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/products', async (req, res) => {
  try {
    const db = mongoose.connection.db;
    const items = await db.collection('products').find().sort({_id: -1}).toArray();
    res.json(items);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/news', async (req, res) => {
  try {
    const db = mongoose.connection.db;
    const items = await db.collection('news').find().sort({_id: -1}).toArray();
    res.json(items);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/jobs', async (req, res) => {
  try {
    const db = mongoose.connection.db;
    const items = await db.collection('jobs').find().sort({_id: -1}).toArray();
    res.json(items);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Fix #13: Auth middleware for pipeline execution endpoint
const VALID_TARGETS = ['papers', 'startups', 'products', 'live'];
const MAX_RECORDS_LIMIT = 5000;

function authMiddleware(req, res, next) {
  const apiSecret = process.env.API_SECRET;
  if (!apiSecret) {
    // If no API_SECRET is configured, allow requests (dev mode)
    return next();
  }
  const authHeader = req.headers.authorization;
  if (!authHeader || authHeader !== `Bearer ${apiSecret}`) {
    return res.status(401).json({ error: 'Unauthorized: invalid or missing API_SECRET' });
  }
  next();
}

app.post('/api/run', authMiddleware, (req, res) => {
  const { topic, maxRecords, target } = req.body;

  // Validate target against allowlist
  if (!target || !VALID_TARGETS.includes(target)) {
    return res.status(400).json({ error: `Invalid target. Must be one of: ${VALID_TARGETS.join(', ')}` });
  }

  // Sanitize topic: alphanumeric + spaces only
  let safeTopic = '';
  if (topic) {
    safeTopic = String(topic).replace(/[^a-zA-Z0-9 ]/g, '').substring(0, 100);
  }

  // Sanitize maxRecords: integer, capped
  let safeMaxRecords = '';
  if (maxRecords) {
    const parsed = parseInt(maxRecords, 10);
    if (!isNaN(parsed) && parsed > 0) {
      safeMaxRecords = String(Math.min(parsed, MAX_RECORDS_LIMIT));
    }
  }

  let args;
  if (target === 'live') {
    args = ['main.py', 'live-monitor'];
  } else {
    args = ['main.py', 'batch-extract'];
    if (target === 'papers') args.push('--run-papers');
    if (target === 'startups') args.push('--run-startups');
    if (target === 'products') args.push('--run-products');
    
    if (safeTopic) {
      args.push('--topic');
      args.push(safeTopic);
    }
    
    if (safeMaxRecords) {
      args.push('--max-records');
      args.push(safeMaxRecords);
    }
  }

  const pyProcess = spawn('python', args, { cwd: path.join(__dirname, '..') });
  
  let output = '';
  pyProcess.stdout.on('data', (data) => { output += data.toString(); });
  pyProcess.stderr.on('data', (data) => { output += data.toString(); });
  
  pyProcess.on('close', (code) => {
    if (code === 0) {
      res.json({ success: true, log: output });
    } else {
      res.status(500).json({ success: false, error: 'Pipeline failed', log: output });
    }
  });
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

