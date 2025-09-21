#!/bin/bash

# Exit on any stupid error
set -e

# llm_model="${LLM_MODEL:-qwen3:1.7b}"
llm_model="${LLM_MODEL:-qwen2.5:1.5b}"


# Start Ollama server in the background
echo "Starting Ollama server..."
ollama serve &
OLLAMA_PID=$!

# Function to check if Ollama API is responsive
api_ready() {
    curl -s http://localhost:11434/api/tags > /dev/null 2>&1
}

# Function to check if the model exists
model_exists() {
    curl -s http://localhost:11434/api/tags | grep -q "\"name\":\"${llm_model}\""
}

# Wait for the Ollama server to start
echo "Waiting for Ollama server to start..."
max_attempts=30
attempt=1
until api_ready; do
    if [ $attempt -ge $max_attempts ]; then
        echo "Ollama server failed to start after $max_attempts attempts"
        exit 1
    fi
    echo "Attempt $attempt/$max_attempts: Ollama server not ready yet..."
    sleep 2
    attempt=$((attempt+1))
done

echo "Ollama server is running"

# Check if the model exists and pull if necessary
if model_exists; then
    echo "Model ${llm_model} already exists. Skipping pull."
else
    echo "Model not found. Pulling ${llm_model}..."
    ollama pull "${llm_model}"
    echo "Model pull completed"
fi

# Wait for the Ollama process
wait $OLLAMA_PID