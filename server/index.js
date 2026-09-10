const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const { spawn } = require('child_process');

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
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

app.post('/api/run', (req, res) => {
  const { topic, maxRecords, target } = req.body;
  const args = ['main.py', 'batch-extract'];
  
  if (target === 'papers') args.push('--run-papers');
  if (target === 'startups') args.push('--run-startups');
  if (target === 'products') args.push('--run-products');
  
  if (topic) {
    args.push('--topic');
    args.push(topic);
  }
  
  if (maxRecords) {
    args.push('--max-records');
    args.push(maxRecords);
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
