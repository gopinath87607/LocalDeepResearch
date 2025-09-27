# LocalDeepResearch

A comprehensive AI-powered research platform that combines autonomous research agents with interactive chat capabilities.

## Features

- 🔍 **Autonomous Research**: AI agents conduct multi-step research using web search, document analysis, and academic sources
- 💬 **Interactive Chat**: Chat with your research results using local LLMs
- 🔗 **URL Tracking**: Automatically collects and organizes all website links found during research
- 📊 **Real-time Monitoring**: Live view of research process, server logs, and agent intelligence
- 🎯 **Local First**: Runs entirely on your hardware with local LLMs via llama.cpp

## Demo

### Video Demo
![Demo Video](https://github.com/gopinath87607/LocalDeepResearch/blob/main/Screencast%20from%202025-09-26%2020-11-24.webm)

*Note: If the video doesn't play directly in GitHub, you can [view it here](https://github.com/gopinath87607/LocalDeepResearch/blob/main/Screencast%20from%202025-09-26%2020-11-24.webm)*

### Screenshots

**Main Dashboard**
![Dashboard Screenshot](https://github.com/gopinath87607/LocalDeepResearch/blob/main/Screenshot%20from%202025-09-26%2020-49-33.png)

**Research Interface**
![Research Interface](https://github.com/gopinath87607/LocalDeepResearch/blob/main/Screenshot%20from%202025-09-26%2020-51-17.png)

**Chat Interface**
![Chat Interface](https://github.com/gopinath87607/LocalDeepResearch/blob/main/Screenshot%20from%202025-09-26%2020-51-22.png)

## Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- [llama.cpp](https://github.com/ggerganov/llama.cpp) server
- Research-capable LLM model (e.g., Qwen, Llama, etc.)

### 1. Clone and Setup
```bash
git clone https://github.com/gopinath87607/LocalDeepResearch.git
cd LocalDeepResearch

# Create isolated environment with Python 3.10.0
conda create -n LocalDeepResearch_env python=3.10.0
conda activate LocalDeepResearch_env

# Or using virtualenv
python3.10 -m venv LocalDeepResearch_env
source LocalDeepResearch_env/bin/activate  # On Windows: deepresearch_env\Scripts\activate

pip install -r requirements.txt

# Backend setup
cd backend
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install
```

### 2. Start LLM Servers
```bash
# Main research model (port 8080)
./llama-server -m path/to/your-model.gguf --host 0.0.0.0 --port 8080

# ReaderLM for web extraction (port 8081) - optional
./llama-server -m path/to/reader-lm.gguf --host 0.0.0.0 --port 8081
```

### 3. Configure Environment
```bash
export SERPER_KEY_ID="your-serper-api-key"
export API_BASE="http://localhost:8080/v1"
export READERLM_ENDPOINT="http://localhost:8081/v1"
```

### 4. Run the Application
```bash
# Start backend
cd backend
python main.py

# Start frontend (new terminal)
cd frontend
npm start
```

Visit `http://localhost:3000` and start researching!

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend│    │  Flask Backend  │    │  llama.cpp      │
│                 │◄──►│                 │◄──►│  LLM Servers    │
│  - Dashboard    │    │  - Research API │    │                 │
│  - Chat UI      │    │  - WebSocket    │    │  Main: :8080    │
│  - URL Display  │    │  - URL Tracking │    │  Reader: :8081  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  Research Tools │
                       │                 │
                       │  - Web Search   │
                       │  - Visit Pages  │
                       │  - Scholar      │
                       │  - Python Code  │
                       └─────────────────┘
```

## Configuration

### API Keys
- **Serper API**: Required for web search - get free key at [serper.dev](https://serper.dev)
- **Other APIs**: Optional depending on tools used

### Models
- **Main Model**: Any instruction-following model ([Qwen-2.5, Llama-3.1](https://huggingface.co/Alibaba-NLP/Tongyi-DeepResearch-30B-A3B), [Jan-v1-2509-gguf](https://huggingface.co/janhq/Jan-v1-2509-gguf), etc.)
- **ReaderLM**: [jinaai/ReaderLM-v2](https://huggingface.co/jinaai/ReaderLM-v2) for better web content extraction
- **Tongyi-DeepResearch-30B-A3B**: Available at [🤗 HuggingFace](https://huggingface.co/Alibaba-NLP/Tongyi-DeepResearch-30B-A3B) or [🤖 ModelScope](https://modelscope.cn/models/iic/Tongyi-DeepResearch-30B-A3B)

## Usage

### Basic Research
1. Enter your research question
2. Watch real-time progress in the monitoring panels
3. Review collected URLs and research intelligence
4. Read comprehensive results

### Chat with Results
After research completes:
1. Chat interface appears below results
2. Ask follow-up questions about findings
3. Get clarifications and deeper insights
4. Context-aware responses based on research

## Development

### Project Structure
- `backend/`: Flask API server and research orchestration
- `frontend/`: React dashboard and user interface  
- `inference/`: Research agent scripts and tools
- `tools/`: Individual research capability modules

### Adding New Tools
1. Create tool in `backend/tools/tool_name.py`
2. Register in research agent configuration
3. Test with isolated queries

### API Documentation
See `docs/api.md` for detailed API reference.

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [DeepResearch by Alibaba-NLP](https://github.com/Alibaba-NLP/DeepResearch) for the core research agent implementation and methodologies
- [llama.cpp](https://github.com/ggerganov/llama.cpp) for local LLM inference
- [Serper](https://serper.dev) for web search API
- Research methodologies inspired by various AI research frameworks

## Support

- 📖 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/gopinath87607/LocalDeepResearch/issues)
- 💬 [Discussions](https://github.com/gopinath87607/LocalDeepResearch/discussions)

---

**⭐ Star this repo if you find it useful!**
