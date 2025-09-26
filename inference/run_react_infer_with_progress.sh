#!/bin/bash
# Full config from original run_react_infer.sh
export TORCHDYNAMO_VERBOSE=1
export TORCHDYNAMO_DISABLE=1
export QWEN_DOC_PARSER_USE_IDP=false
export QWEN_IDP_ENABLE_CSI=false
export NLP_WEB_SEARCH_ONLY_CACHE=false
export NLP_WEB_SEARCH_ENABLE_READPAGE=false
export NLP_WEB_SEARCH_ENABLE_SFILTER=false
export QWEN_SEARCH_ENABLE_CSI=false
export SPECIAL_CODE_MODE=false
export PYTHONDONTWRITEBYTECODE=1

##############hyperparams################
export MODEL_PATH="${MODEL_PATH:-http://localhost:8080/v1}" # Main research model
export READERLM_ENDPOINT="${READERLM_ENDPOINT:-http://localhost:8081/v1}" # ReaderLM for web extraction
export PLANNING_PORT=8080  # Main model port
export READERLM_PORT=8081  # ReaderLM port
export DATASET="${DATASET:-test_questions}"
export OUTPUT_PATH="${OUTPUT_PATH:-../outputs}"
export ROLLOUT_COUNT=1
export TEMPERATURE="${TEMPERATURE:-0.85}"
export PRESENCE_PENALTY="${PRESENCE_PENALTY:-1.1}"
export MAX_WORKERS=1

## API keys - Updated for local setup
export SERPER_KEY_ID="${SERPER_KEY_ID:-c9}"
# REMOVED: Jina API key (using local ReaderLM instead)
export JINA_API_KEYS=""  # Disable external Jina API
export API_KEY="${API_KEY:-dummy-key}"
export API_BASE="${API_BASE:-http://localhost:8080/v1}"
export SUMMARY_MODEL_NAME="${SUMMARY_MODEL_NAME:-deepresearch}"

## Dummy keys for unused services
export DASHSCOPE_API_KEY="${DASHSCOPE_API_KEY:-dummy_key}"
export DASHSCOPE_API_BASE="${DASHSCOPE_API_BASE:-dummy_base}"
export VIDEO_MODEL_NAME="${VIDEO_MODEL_NAME:-dummy_model}"
export VIDEO_ANALYSIS_MODEL_NAME="${VIDEO_ANALYSIS_MODEL_NAME:-dummy_model}"
export SANDBOX_FUSION_ENDPOINT="${SANDBOX_FUSION_ENDPOINT:-dummy_endpoint}"
export TORCH_COMPILE_CACHE_DIR="${TORCH_COMPILE_CACHE_DIR:-./cache}"
export USE_IDP="${USE_IDP:-False}"
export IDP_KEY_ID="${IDP_KEY_ID:-dummy_key}"
export IDP_KEY_SECRET="${IDP_KEY_SECRET:-dummy_secret}"

######################################
### 1. Check dependencies and servers ###
######################################

# Check if BeautifulSoup is installed
echo "Checking Python dependencies..."
python3 -c "from bs4 import BeautifulSoup; print('✓ BeautifulSoup4 is installed')" 2>/dev/null || {
    echo "⚠ BeautifulSoup4 not found. Installing..."
    pip install beautifulsoup4
    echo "✓ BeautifulSoup4 installed"
}

echo "Checking main research server at localhost:8080..."
if ! curl -s -f http://localhost:8080/v1/models > /dev/null 2>&1; then
    echo "Error: Main llama.cpp server not running at localhost:8080"
    echo "Please start your main research server first:"
    echo "cd /path/to/llama.cpp && ./llama-server -m /path/to/main-model.gguf --host 0.0.0.0 --port 8080"
    exit 1
fi
echo "✓ Main research server is ready!"

echo "Checking ReaderLM server at localhost:8081..."
if ! curl -s -f http://localhost:8081/v1/models > /dev/null 2>&1; then
    echo "Warning: ReaderLM server not running at localhost:8081"
    echo "ReaderLM server is recommended for better web extraction."
    echo "To start ReaderLM server:"
    echo "cd /path/to/llama.cpp && ./llama-server -m /path/to/reader-lm.gguf --host 0.0.0.0 --port 8081"
    echo "Continuing with fallback web extraction..."
    export READERLM_AVAILABLE=false
else
    echo "✓ ReaderLM server is ready!"
    export READERLM_AVAILABLE=true
fi

#######################################################
### 2. Display configuration ###
#######################################################
echo "===== DeepResearch Configuration ====="
echo "Main Research Model: $MODEL_PATH"
echo "ReaderLM Endpoint: $READERLM_ENDPOINT"
echo "ReaderLM Available: $READERLM_AVAILABLE"
echo "Dataset: $DATASET"
echo "Output: $OUTPUT_PATH"
echo "Serper API: ${SERPER_KEY_ID:0:10}..."
echo "====================================="

# Create output directory
mkdir -p "$OUTPUT_PATH"

# Use backend-created dataset
DATASET_FILE="/home/gopi/DeepResearch/inference/eval_data/${DATASET}.jsonl"
if [ ! -f "$DATASET_FILE" ]; then
    echo "Error: Dataset not found at $DATASET_FILE"
    exit 1
else
    echo "Using dataset: $DATASET_FILE"
fi

# Progress tracking function
log_progress() {
    local step="$1"
    local action="$2"
    local description="$3"
    echo "PROGRESS: {\"step\": $step, \"action\": \"$action\", \"description\": \"$description\", \"timestamp\": \"$(date -Iseconds)\"}"
}

# Start research with progress logging
log_progress 1 "initialization" "Initializing DeepResearch environment with local models"
log_progress 2 "query_analysis" "Analyzing research query and planning approach"
log_progress 3 "web_search" "Performing web search and content extraction"

#####################################
### 3. Start inference ####
#####################################
echo "==== Starting inference with local models... ===="
cd "$( dirname -- "${BASH_SOURCE[0]}" )"
log_progress 4 "document_analysis" "Analyzing retrieved documents with local ReaderLM"

python -u run_multi_react.py \
    --dataset "$DATASET" \
    --output "$OUTPUT_PATH" \
    --max_workers $MAX_WORKERS \
    --model "$MODEL_PATH" \
    --temperature $TEMPERATURE \
    --presence_penalty $PRESENCE_PENALTY \
    --total_splits ${WORLD_SIZE:-1} \
    --worker_split $((${RANK:-0} + 1)) \
    --roll_out_count $ROLLOUT_COUNT

log_progress 5 "synthesis" "Synthesizing final research results"
echo "COMPLETE: Research finished successfully with local models"####################################
### 3. Start inference ####
#####################################
echo "==== Starting inference with local models... ===="
cd "$( dirname -- "${BASH_SOURCE[0]}" )"
log_progress 4 "document_analysis" "Analyzing retrieved documents with local ReaderLM"

python -u run_multi_react.py \
    --dataset "$DATASET" \
    --output "$OUTPUT_PATH" \
    --max_workers $MAX_WORKERS \
    --model "$MODEL_PATH" \
    --temperature $TEMPERATURE \
    --presence_penalty $PRESENCE_PENALTY \
    --total_splits ${WORLD_SIZE:-1} \
    --worker_split $((${RANK:-0} + 1)) \
    --roll_out_count $ROLLOUT_COUNT

log_progress 5 "synthesis" "Synthesizing final research results"
echo "COMPLETE: Research finished successfully with local models"
