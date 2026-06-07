# ⚡ RAGNAROK
### Multi-Document Intelligence Engine

> *"Where knowledge meets the end of ignorance."*

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![LangChain](https://img.shields.io/badge/LangChain-LCEL-1C3C3C?style=flat-square)](https://langchain.com)
[![OpenAI](https://img.shields.io/badge/GPT--4o-OpenAI-412991?style=flat-square&logo=openai&logoColor=white)](https://openai.com)
[![Pinecone](https://img.shields.io/badge/Pinecone-Serverless-13AEA7?style=flat-square)](https://pinecone.io)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.38-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![RAGAS](https://img.shields.io/badge/RAGAS-Evaluation-F97316?style=flat-square)](https://docs.ragas.io)
[![Deploy](https://img.shields.io/badge/HuggingFace-Spaces-FFD21E?style=flat-square&logo=huggingface)](https://huggingface.co/spaces/DeepDobariya307/RAGNAROK)

---

**RAGNAROK** is a production-grade Retrieval-Augmented Generation (RAG) system that enables intelligent, cited conversations across multiple PDF documents simultaneously. Upload research papers, reports, contracts — ask questions across all of them. Every answer cites the exact source and page number.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     PDF Documents                        │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              Document Processor (PyPDF)                  │
│   Text extraction → RecursiveCharacterTextSplitter       │
│   Chunk size: 1000 tokens | Overlap: 200 tokens          │
│   Metadata: filename + page number per chunk             │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│           OpenAI text-embedding-3-large                  │
│              3072-dimensional vectors                    │
│          Industry's highest-quality embeddings           │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              Pinecone Serverless Index                   │
│     Cosine similarity | Session-namespaced storage       │
│        MMR retrieval (k=6, fetch_k=20, λ=0.7)           │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              LangChain LCEL RAG Chain                    │
│  1. Contextualize question using chat history            │
│  2. Retrieve diverse chunks via MMR                      │
│  3. Format context with [Source N: file, Page X]         │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                 GPT-4o Generation                        │
│   Streaming token-by-token | Grounded in context only   │
│   Sliding window memory (last 5 turns retained)         │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              Streamlit Chat Interface                    │
│   Real-time streaming | Source citation expanders        │
│   Export to Markdown | RAGAS evaluation dashboard        │
└─────────────────────────────────────────────────────────┘
```

---

## ✨ Features

| Feature | Description |
|---|---|
| 🗂️ **Multi-Document RAG** | Upload and query across multiple PDFs simultaneously |
| ⚡ **Streaming Responses** | Real-time token streaming — feels like ChatGPT |
| 📖 **Source Citations** | Every answer references `[Source N: filename, Page X]` |
| 🔍 **MMR Retrieval** | Maximal Marginal Relevance avoids redundant context chunks |
| 🧠 **Conversation Memory** | 5-turn sliding window for natural multi-turn dialogue |
| 📊 **RAGAS Evaluation** | Built-in pipeline quality dashboard (Faithfulness, Relevancy) |
| 💾 **Session Isolation** | Pinecone namespaces keep your docs private per session |
| 📥 **Export** | Download full conversations as Markdown |
| 🚀 **Railway Deploy** | One-click deployment with Docker |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- OpenAI API key ([platform.openai.com](https://platform.openai.com))
- Pinecone API key ([pinecone.io](https://pinecone.io))

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/RAGNAROK.git
cd RAGNAROK

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Open `.env` and fill in:
```
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=pcsk_...
```

### 3. Run

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) — you're live.

---

## 📊 Evaluation

Navigate to **Pages → Evaluation** in the Streamlit sidebar.

Enter test questions, hit **Run Evaluation**, and get RAGAS metrics:

- **Faithfulness** — Are answers factually consistent with retrieved context?
- **Answer Relevancy** — Does the answer address the question?
- **Context Relevancy** — Is the retrieved context on-point?

All metrics work **without ground-truth answers**.

---

## 🗂️ Project Structure

```
RAGNAROK/
├── app.py                       # Main Streamlit application
├── config.py                    # All tunable parameters (one place)
├── pages/
│   └── 2_Evaluation.py          # RAGAS evaluation dashboard
├── core/
│   ├── document_processor.py    # PDF ingestion + chunking
│   ├── vector_store.py          # Pinecone index lifecycle
│   └── rag_chain.py             # LangChain LCEL RAG pipeline
├── ui/
│   └── styles.py                # Custom dark Norse theme CSS
├── utils/
│   └── helpers.py               # Export + formatting utilities
├── requirements.txt
├── .env.example
├── Dockerfile
└── railway.toml
```

---

## ☁️ Live Demo

👉 **[Try RAGNAROK live on HuggingFace Spaces](https://huggingface.co/spaces/DeepDobariya307/RAGNAROK)**

## ☁️ Deploy Your Own

1. Fork this repo
2. Go to [huggingface.co/spaces](https://huggingface.co/spaces) → New Space → Docker
3. Push your code
4. Add `OPENAI_API_KEY` and `PINECONE_API_KEY` as Secrets in Space Settings
5. Done — your own instance is live!
---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| LLM | GPT-4o (OpenAI) |
| Embeddings | text-embedding-3-large |
| Vector DB | Pinecone Serverless |
| RAG Framework | LangChain LCEL |
| Frontend | Streamlit |
| Evaluation | RAGAS |
| Deployment | HuggingFace Spaces (Docker) |

---

## 📝 License

MIT — use freely, build on it, give credit if you'd like.

---

*Built by **Deep Prakashbhai Dobariya** — MSc Artificial Intelligence, BTU Cottbus-Senftenberg*
