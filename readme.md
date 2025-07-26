# Calibre AI Tagger

Automatically tag your Calibre e-book library using AI. Currently supports:

- Google Gemini AI
- Local Ollama models
- In near future - OpenAI GPT

## Features


- 🔄 Smart tag merging with existing tags
- 🔍 Dry-run mode for preview

- 🌐 Local AI support with Ollama
- 🤖 Multiple AI providers support

## Prerequisites

- Python 3.8+
- Calibre with command-line tools
- At least one of:
  - Google Gemini API key
  - OpenAI API key
  - Ollama installed locally

## Quick Start

1. Install dependencies:

```bash
pip install -r requirements.txt
```

1. Set up your .env file:

```env
# Use any or all of these:
GOOGLE_API_KEYS=your-gemini-key-1,your-gemini-key-2
OPENAI_API_KEYS=your-openai-key-1,your-openai-key-2
OLLAMA_MODEL=mistral:latest  # or any other model you have
```

1. Run a test:

```bash
python CalibreAi.py --library-path "path/to/calibre/library"  --dry-run --limit 3 --dry-run
```

## Usage

Basic usage with default settings:

✅✅✅✅✅✅✅✅✅✅✅✅ Normal Use:
```bash
python CalibreAi.py --library-path "path/to/calibre/library" --provider ollama
```


```bash
python CalibreAi.py --library-path "path/to/calibre/library" 
```

Choose a specific AI provider:

```bash
python CalibreAi.py --library-path "path/to/calibre/library" --provider [gemini|openai|ollama]
```

🚩🚧🏴‍☠️⚠🛑Replace existing tags instead of merging:

```bash
python CalibreAi.py --library-path "path/to/calibre/library" --provider ollama --overwrite
```

## Command-Line Arguments

- `--library-path`: Path to Calibre library [--library-path "C:\calibre\library"](required)
- `--provider`: AI provider to use `[--provider] [gemini|openai|ollama|all] (default: all)
- `--limit`: Number of books to process [--limit 3] ( leave empty to go through all)
- `--dry-run`: Preview changes without applying them [--dry-run] (empty to apply)
- `--overwrite`: 🚩🚧🏴‍☠️⚠🛑 Replace existing tags instead of merging [--overwrite] (leave empty to append/merge)

## ⚠️ Backup Reminder

Always backup your Calibre library before making changes!
