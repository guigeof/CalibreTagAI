# Calibre AI Tagger
A Python script to automatically tag your Calibre e-book library using the Google Gemini AI. It reads your book's metadata, generates relevant tags based on the title and description, and applies them directly to your Calibre database.

# Features
Automated Tagging: Intelligently generates tags for genre, themes, setting, and more.

Direct Calibre Integration: Uses Calibre's own command-line tools (calibredb) to read and write metadata safely.

Flexible Tagging: Choose to append new tags to existing ones or overwrite them completely.

Safety First: Includes a --dry-run mode to preview changes without modifying your library.

Configurable: Easily limit the number of books processed for quick tests.

# How It Works
Fetch Books: The script calls calibredb to fetch a list of your books, retrieving each book's ID, title, existing tags, and comments (which typically contain the book's summary).

Generate Tags: For each book, the title and comments are sent to the Gemini AI with a prompt asking it to generate a list of relevant tags.

Apply Tags: The script takes the AI-generated tags and uses calibredb again to write them to the book's metadata in your library.

# Prerequisites
Before you begin, ensure you have the following:

- Python 3: You can download it from python.org.

- Calibre: The e-book manager must be installed. You can get it from calibre-ebook.com.

- Calibre Command-Line Tools: You must have Calibre's command-line tools installed and available in your system's PATH.

  - macOS: In Calibre, go to ```Preferences -> Miscellaneous -> Install command-line tools```.
  - Windows: The installer typically adds this to the PATH automatically. Test by running ```calibredb --version``` in Command Prompt.
  - Linux: Usually handled by your package manager during installation.

- Google AI API Key: The script requires a free API key for the Gemini model. You can obtain one from Google AI Studio.

# Setup and Usage
## 1. Save the Script

Save the Python code from the project into a file named ```calibre_tagger.py```.

## 2. Install Dependencies

Open your terminal or command prompt and run the following command to install the necessary Python libraries:

```pip install google-generativeai python-dotenv```

## 3. Create Environment File

In the same directory as your script, create a file named .env. Add your Google AI API key to this file:

```GOOGLE_API_KEY="YOUR_API_KEY_HERE"```

Replace ```YOUR_API_KEY_HERE``` with your actual key.

## 4. Run a Test (Dry Run)

IMPORTANT: Always perform a dry run first to preview the tags without changing your library. This example processes the first 5 books it finds.

Replace ```/path/to/your/Calibre Library``` with the actual path to your library.

```python calibre_tagger.py --library-path "/path/to/your/Calibre Library" --dry-run --limit 5 ```

## 5. Run the Tagger

Once you are satisfied with the dry run results, you can run the script on your entire library.

```python calibre_tagger.py --library-path "/path/to/your/Calibre Library"```

To replace all existing tags with the new AI-generated ones, add the ```--overwrite``` flag:

```python calibre_tagger.py --library-path "/path/to/your/Calibre Library" --overwrite```

# ⚠️ Safety and Backup
Before running any script that modifies your data, always back up your Calibre library. The easiest way to do this is to make a copy of your entire Calibre Library folder and store it in a safe location.

##Command-Line Arguments
```--library-path```: (Required) The full path to your Calibre library folder.

```--limit```: (Optional) An integer to limit the number of books to process. Useful for testing.

```--dry-run```: (Optional) If included, the script will only print the tags it would apply without making any changes.

```--overwrite```: (Optional) If included, existing tags on a book will be replaced. By default, new tags are appended.

# License
This project is licensed under the MIT License.


# Attribution
This script was created by Gemini, a large language model trained by Google.

