---
description: Steps to verify the chatbot features and run the automated test suite.
---

# Testing the High-Performance AI ChatBot

This guide explains how to verify the new intelligence, memory, and multi-modal features of the chatbot.

## 1. Prerequisites

Ensure you have the latest dependencies installed:

```bash
pip install -r requirements.txt
```

## 2. Running Automated Tests

Run the complete test suite using `pytest`:

// turbo

```bash
pytest tests/
```

To run specific test categories:

- **Intelligence**: `pytest tests/unit/test_intelligence.py`
- **Memory**: `pytest tests/unit/test_memory.py`
- **MCP Core**: `pytest tests/unit/test_mcp.py`
- **End-to-End Chat**: `pytest tests/integration/test_chat_flow.py`

## 3. Manual Verification (UAT)

### Intent Detection

Ask the bot different types of questions to see it adapt:

- `Can you make a plan for my project?` (Intent: Planning)
- `Write a python script to parse CSV.` (Intent: Coding)

### Fuzzy Tool Matching

Try calling a tool with a slight typo if you have a local tool registered:

- `Can you seaarch for today's weather?` (Corrects `seaarch` to `search`)

### Multi-Modal & OCR

Send an image link or base64 and ask:

- `What is written in this image?`
- `Read this PDF: /path/to/file.pdf`

### Context Distillation

Start a long conversation and check the logs to see if a `Rolling Summary (MCP)` is generated after 10 turns.

## 4. Monitoring

Check the `/metrics` endpoint (Prometheus) to see tool call statistics and performance during your tests.
