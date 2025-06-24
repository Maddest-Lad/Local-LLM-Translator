# Screen Translator - Web-Based Desktop App

A modern screen translation application built with FastAPI backend and web frontend, packaged as a desktop app using PyWebView.

## Architecture Overview

- **Backend**: FastAPI with Pydantic models for type safety
- **Frontend**: Modern HTML/CSS/JavaScript with real-time WebSocket communication
- **Desktop Integration**: PyWebView for native desktop experience
- **Data Validation**: Shared Pydantic models ensure data consistency between frontend and backend

## Features

- 🖥️ **Modern Web UI**: Clean, responsive interface with dark theme
- 🔄 **Real-time Updates**: WebSocket communication for instant feedback
- 📱 **Cross-platform**: Works on Windows, macOS, and Linux
- 🔒 **Type Safety**: Pydantic models validate all API communication
- ⚙️ **Configurable**: Adjustable settings for monitoring and translation
- 📋 **Copy & Manage**: Easy copying and management of translation results

## File Structure

```
├── models.py           # Pydantic models for API communication
├── api.py              # FastAPI backend server
├── translator.py       # Original translation logic (unchanged)
├── desktop_app.py      # PyWebView desktop wrapper
├── run_app.py          # Application launcher script
├── requirements.txt    # Updated dependencies
├── static/
│   └── index.html      # Web frontend
└── README.md          # This file
```

## Installation

1. **Install Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Verify Installation**
   ```bash
   python run_app.py --check
   ```

## Running the Application

### Desktop App (Recommended)
```bash
python run_app.py
# or
python run_app.py --mode desktop
```

### Web Browser Access
```bash
python run_app.py
