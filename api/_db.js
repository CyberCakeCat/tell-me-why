// Atlas connection and keys. On Vercel they come from environment variables; locally from git-ignored files.
const fs = require('fs'), path = require('path');
const { MongoClient } = require('mongodb');
const root = path.join(__dirname, '..');
const local = f => { try { return fs.readFileSync(path.join(root, f), 'utf8').trim(); } catch { return null; } };

function mongoUri() {
  if (process.env.MONGODB_URI) return process.env.MONGODB_URI;
  const u = local('atlas_user.txt'), p = local('atlas_password.txt');
  if (!u || !p) throw new Error('MONGODB_URI is not configured');
  return `mongodb+srv://${encodeURIComponent(u)}:${encodeURIComponent(p)}@cluster0.kkky9y1.mongodb.net/`;
}
const geminiKey = () => process.env.GEMINI_API_KEY || local('gemini_key.txt');

let client;
async function db() {
  if (!client) client = new MongoClient(mongoUri(), { serverSelectionTimeoutMS: 10000 });
  await client.connect();
  return client.db('deadspot');
}
module.exports = { db, geminiKey };
