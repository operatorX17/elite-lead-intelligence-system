# Pinecone Index Setup Guide for ZRAI Lead OS

## Overview

The Pinecone vector database is used in ZRAI Lead OS for **Playbook RAG** (Retrieval Augmented Generation). It stores:
- Outreach message examples
- Objection handling snippets
- Niche-specific guidance
- Best practices and templates

## Quick Setup (Manual via UI)

### Step 1: Go to Pinecone Console
Visit: https://app.pinecone.io/

### Step 2: Create New Index
Click the **"Create Index"** button

### Step 3: Configure Index Settings

Based on your screenshot, fill in:

| Setting | Value | Why |
|---------|-------|-----|
| **Index name** | `zrai-playbooks` | Matches `.env.example` config |
| **Dimensions** | `768` | For Google text-embedding-004 model |
| **Metric** | `cosine` | Best for text similarity search |
| **Capacity mode** | `Serverless` | Pay-per-use, scales automatically |
| **Cloud provider** | `AWS` (or your preference) | Choose based on your region |
| **Region** | `us-east-1` (Virginia) | Choose closest to your app |

### Step 4: Create Index
Click **"Create Index"** button at the bottom

### Step 5: Wait for Initialization
The index will take 1-2 minutes to initialize. You'll see a status indicator.

### Step 6: Get Your Configuration
Once created, note down:
- Index name: `zrai-playbooks`
- Environment/Region: `us-east-1` (or whatever you chose)
- API Key: (already have this)

## Configuration in .env File

Add these to your `.env` file:

```bash
# Pinecone Configuration
PINECONE_API_KEY=your-pinecone-api-key-here
PINECONE_ENVIRONMENT=us-east-1
PINECONE_INDEX_NAME=zrai-playbooks
```

## Embedding Model Dimensions Reference

**Important:** The dimension MUST match your embedding model!

| Embedding Model | Dimensions | Provider |
|----------------|------------|----------|
| `text-embedding-004` | **768** | Google (Recommended for Gemini) |
| `text-embedding-3-small` | 1536 | OpenAI |
| `text-embedding-3-large` | 3072 | OpenAI |
| `text-embedding-ada-002` | 1536 | OpenAI (Legacy) |

Since you're using **Gemini/Google**, use **768 dimensions** with Google's embedding model.

## Automated Setup (Optional)

If you prefer to create the index programmatically:

```bash
# Set your API key
export PINECONE_API_KEY=your-actual-key

# Run the setup script
python setup_pinecone_index.py
```

## Verify Setup

After creating the index, you can verify it's working:

```python
from pinecone import Pinecone

pc = Pinecone(api_key="your-api-key")
index = pc.Index("zrai-playbooks")

# Check stats
stats = index.describe_index_stats()
print(f"Total vectors: {stats['total_vector_count']}")
print(f"Dimension: {stats['dimension']}")
```

## Cost Considerations

**Serverless Pricing (Recommended):**
- Pay only for what you use
- No idle costs
- Scales automatically
- Perfect for development and production

**Starter Plan:**
- Free tier available
- Good for testing and small projects
- Check current limits at: https://www.pinecone.io/pricing/

## Troubleshooting

### Error: "Dimension mismatch"
- Make sure your embedding model dimension matches the index dimension
- Google embeddings = 768
- OpenAI embeddings = 1536 or 3072

### Error: "Index already exists"
- Good news! Your index is already created
- Just use the existing one

### Error: "Invalid API key"
- Check your API key in Pinecone console
- Make sure it's copied correctly to `.env`

## Next Steps

After creating the index:

1. ✅ Update your `.env` file with the configuration
2. ✅ Test the connection with the verification script
3. ✅ Start building the playbook ingestion system (Task 25 in tasks.md)
4. ✅ Populate with initial playbook content

## Architecture Notes

From the ZRAI design document:

> The playbooks table + vector store (e.g., Pinecone) is used to:
> - Retrieve outreach examples
> - Objection handling snippets  
> - Niche-specific notes
> 
> For any generated outreach or conversation:
> - Retrieve relevant chunks first
> - Condition the LLM on these chunks (RAG)
> - Version playbooks and link to run_id for reproducibility

This ensures all AI-generated content is grounded in proven examples and best practices.
