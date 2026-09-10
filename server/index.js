require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');

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
    const items = await db.collection('research_papers').find().toArray();
    res.json(items);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/startups', async (req, res) => {
  try {
    const db = mongoose.connection.db;
    const items = await db.collection('startups').find().toArray();
    res.json(items);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/products', async (req, res) => {
  try {
    const db = mongoose.connection.db;
    const items = await db.collection('products').find().toArray();
    res.json(items);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/news', async (req, res) => {
  try {
    const db = mongoose.connection.db;
    const items = await db.collection('news').find().toArray();
    res.json(items);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/jobs', async (req, res) => {
  try {
    const db = mongoose.connection.db;
    const items = await db.collection('jobs').find().toArray();
    res.json(items);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
