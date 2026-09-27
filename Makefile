.PHONY: help install run clean

# Default target
help:
	@echo "AI Harness - Makefile"
	@echo "====================="
	@echo "Available commands:"
	@echo "  make install    - Install Python dependencies"
	@echo "  make setup      - Create the Workspace directory and .env file"
	@echo "  make run        - Start the FastAPI server"
	@echo "  make clean      - Remove __pycache__ and runtime artifacts"

install:
	pip install -r requirements.txt

setup:
	mkdir -p ../Workspace
	@if [ ! -f .env ]; then \
		echo "OPENAI_API_KEY=sk-your-key-here" > .env; \
		echo "Created .env file. Please add your OpenAI API key."; \
	else \
		echo ".env file already exists."; \
	fi

run:
	python server.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .agents/sessions/*
	rm -rf .agents/checkpoints/*
	@echo "Cleaned up cache and runtime state."
