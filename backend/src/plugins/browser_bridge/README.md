# Browser Bridge Plugin for ECE

This plugin provides a full-duplex communication channel between web browsers and the Executive Cognitive Enhancement system.

## Features

- **Chat Ingestion**: Save chat conversations from various platforms (Gemini, ChatGPT, Claude) to ECE memory system
- **Context Retrieval**: Get relevant context from ECE memory based on draft prompts
- **Browser Integration**: Chrome extension with popup interface and content scripts

## API Endpoints

- `POST /v1/browser/ingest` - Ingest chat messages into ECE memory system
- `POST /v1/browser/context` - Retrieve relevant context for prompts  
- `GET /v1/browser/health` - Health check for the browser bridge
- `GET /v1/browser/session/current` - Get current session info

## Chrome Extension

The extension includes:
- Popup interface with context retrieval and chat saving
- Content scripts for extracting chat data from various platforms
- Background service for ongoing operations
- Context menus for quick access

## Installation

1. Load the extension in development mode:
   - Go to `chrome://extensions`
   - Enable "Developer mode"
   - Click "Load unpacked"
   - Select the `extension_source` directory

2. The extension will communicate with your ECE server at `http://localhost:8000`

## Usage

- Use the popup to get context for draft prompts
- Click "Save Current Chat" to save conversations to ECE memory
- Use context menus for quick actions on selected text