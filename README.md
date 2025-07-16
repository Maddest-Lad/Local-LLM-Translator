# Local LLM Translator

A local application for translating text from images using local LLMs.

## Features

- Screen capture and OCR for text extraction
- Translation using local LLMs
- Real-time translation with streaming updates
- WebSocket support for real-time updates
- Window selection for targeted translation
- Configurable settings for OCR and translation models

## Project Structure

```
Local-LLM-Translator/
├── app/
│   ├── models/           # Data models
│   ├── routers/          # API routes
│   │   └── endpoints/    # API endpoints
│   ├── services/         # Business logic
│   ├── utils/            # Utility functions
│   └── main.py           # FastAPI application
├── static/               # Static files (HTML, CSS, JS)
├── logs/                 # Log files
├── requirements.txt      # Dependencies
├── run_app.py            # Application entry point
└── README.md             # Project documentation
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/Local-LLM-Translator.git
cd Local-LLM-Translator
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage
1. Start an OpenAI-compatible server, this was built for LM Studio + SSE Streaming
2. Set the Local or Remote LLM URL in the settings
3. Start the application and select the VLM, LLM and endpoint in the settings:
```bash
python run_app.py
```
