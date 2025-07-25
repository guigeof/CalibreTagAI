import os
import subprocess
import json
import argparse
import shlex
from dotenv import load_dotenv
import random

# --- Attempt to import AI libraries ---
try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    import openai
except ImportError:
    openai = None

try:
    import requests
except ImportError:
    requests = None


# --- Configuration ---

class AIProvider:
    """A class to manage configuration for a single AI provider."""

    def __init__(self, name, key_env_var):
        self.name = name
        self.key_env_var = key_env_var
        self.is_configured = False
        self.api_keys = []

    def configure(self, api_keys):
        """Configure the provider with a list of keys."""
        if not api_keys:
            return False
        self.api_keys = api_keys
        self.is_configured = True
        return True

    def get_shuffled_keys(self):
        """Get a shuffled list of API keys to iterate through."""
        keys = self.api_keys[:]
        random.shuffle(keys)
        return keys


class AIProviders:
    """A class to hold instances of AI providers."""
    GEMINI = AIProvider("Gemini", "GOOGLE_API_KEYS")
    OPENAI = AIProvider("OpenAI", "OPENAI_API_KEYS")
    OLLAMA = AIProvider("Ollama", "OLLAMA_MODEL")


def parse_keys_from_env(env_var):
    """Parse comma-separated API keys from an environment variable."""
    keys = os.getenv(env_var, "").strip()
    return [k.strip() for k in keys.split(",") if k.strip()]


def configure_ai():
    """
    Loads environment variables and configures AI APIs.
    Returns a list of configured providers.
    """
    load_dotenv()
    configured_providers = []

    # Configure Gemini
    if genai:
        gemini_keys = parse_keys_from_env(AIProviders.GEMINI.key_env_var)
        if AIProviders.GEMINI.configure(gemini_keys):
            configured_providers.append(AIProviders.GEMINI)
            print("✅ Gemini configured.")

    # Configure OpenAI
    if openai:
        openai_keys = parse_keys_from_env(AIProviders.OPENAI.key_env_var)
        if AIProviders.OPENAI.configure(openai_keys):
            configured_providers.append(AIProviders.OPENAI)
            print("✅ OpenAI configured.")

    # Configure Ollama
    if requests:
        try:
            # Check if Ollama is running and the model is available
            model = os.getenv("OLLAMA_MODEL", "mistral:latest")
            response = requests.get(
                f'http://localhost:11434/api/tags', timeout=2)
            if response.status_code == 200:
                # Verify if the model exists
                models = response.json().get("models", [])
                if any(m.get("name") == model for m in models):
                    AIProviders.OLLAMA.configure([model])
                    configured_providers.append(AIProviders.OLLAMA)
                    print(f"✅ Ollama configured with model: {model}")
                else:
                    print(
                        f"⚠️ Warning: Model '{model}' not found in Ollama. Available models: {', '.join(m.get('name', '') for m in models)}")
            else:
                print(
                    "⚠️ Warning: Could not verify Ollama models. Status code:", response.status_code)
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Warning: Ollama not available: {str(e)}")
            print("    Make sure Ollama is running with 'ollama serve' command")

    if not configured_providers:
        print("❌ Error: No AI providers configured.")
        print("Please configure at least one of:")
        print("1. Add Google API keys to .env: GOOGLE_API_KEYS=key1,key2,key3")
        print("2. Add OpenAI API keys to .env: OPENAI_API_KEYS=key1,key2,key3")
        print("3. Run Ollama locally and set model in .env: OLLAMA_MODEL=mistral")
        exit(1)

    return configured_providers


# --- Calibre Interaction Functions ---

def get_books_from_calibre(library_path, limit=None):
    """Fetches book data from the Calibre library using calibredb."""
    print(f"📚 Accessing Calibre library at: {library_path}")
    command = [
        "calibredb", "list",
        "--for-machine",
        "--fields", "id,title,comments,tags",
        "--with-library", library_path
    ]
    if limit:
        command.extend(["--limit", str(limit)])

    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=True, encoding='utf-8')
        books = json.loads(result.stdout)
        print(f"✅ Found {len(books)} books to process.")
        return books
    except FileNotFoundError:
        print("❌ Error: 'calibredb' command not found.")
        print("Please ensure Calibre is installed and its command-line tools are in your system's PATH.")
        return []
    except subprocess.CalledProcessError as e:
        print(f"❌ Error executing calibredb command: {e}")
        print(f"Stderr: {e.stderr}")
        return []
    except json.JSONDecodeError:
        print("❌ Error: Could not parse the output from calibredb. Is the library empty?")
        return []


def set_tags_in_calibre(library_path, book_id, new_tags, overwrite=False):
    """Sets tags for a specific book in the Calibre library."""
    tags_to_apply = new_tags

    # If not overwriting, merge with existing tags
    if not overwrite:
        try:
            get_command = [
                "calibredb", "list",
                "--for-machine",
                "--fields", "tags",
                "--search", f"id:{book_id}",
                "--with-library", library_path
            ]
            result = subprocess.run(
                get_command, capture_output=True, text=True, check=True, encoding='utf-8')
            existing_data = json.loads(result.stdout)
            if existing_data and existing_data[0].get('tags'):
                # Handle both string (comma-separated) and list formats
                existing_tags = existing_data[0]['tags']
                if isinstance(existing_tags, str):
                    existing_tags = [tag.strip()
                                     for tag in existing_tags.split(',')]
                elif isinstance(existing_tags, list):
                    existing_tags = [tag.strip() for tag in existing_tags]
                # Combine, remove duplicates, and sort
                tags_to_apply = sorted(list(set(existing_tags + new_tags)))
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            print(
                f"   ⚠️ Could not read existing tags for book {book_id}. Appending may not be perfect. Error: {e}")

    tags_str = ",".join(tags_to_apply)
    print(f"   🏷️ Applying tags: {tags_str}")

    command = [
        "calibredb", "set_metadata",
        "--field", f"tags:\"{tags_str}\"",
        str(book_id),
        "--with-library", library_path
    ]

    try:
        subprocess.run(command, capture_output=True,
                       text=True, check=True, encoding='utf-8')
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Error setting metadata for book ID {book_id}.")
        print(f"   Stderr: {e.stderr}")


# --- AI Tag Generation prompt ---

def get_prompt(title, description, existing_tags=None, additional_prompt=None):
    """Creates the prompt for the AI based on available book info.

    Args:
        title (str): The book title
        description (str): The book description
        existing_tags (list|str, optional): Existing tags to consider
        additional_prompt (str, optional): Additional custom instructions to add to the prompt
    """
    # Format existing tags if present
    existing_tags_str = ""
    if existing_tags:
        if isinstance(existing_tags, list):
            existing_tags_str = ", ".join(existing_tags)
        else:
            existing_tags_str = str(existing_tags)
        if existing_tags_str:
            existing_tags_str = f"\nCURRENT TAGS: {existing_tags_str}"

    # Check for numerical patterns or unusual formatting in title
    import re
    # Check for various problematic patterns
    patterns = [
        r'^\d{10,13}',  # ISBN-like numbers at start
        r'\.\w+$',      # File extensions
        r'^\d+[_-]',    # Starting with numbers and underscore/dash
        r'[A-Z]{2,}-[A-Z]{2,}',  # Multiple uppercase sequences with dash
        r'\d{6,}',      # Long number sequences
        r'_\d[A-Z]_',   # Patterns like _6E_
        r'\d+\.\.\d+',  # Ranges like 1..3
    ]

    title_has_series = bool(re.search(
        r'(?:^|\s)(\d+(?:\.\d+)?|\d+[a-z]|[A-Z]\d+|\d+[A-Z]|[vV]\d+)', title))
    title_needs_rename = any(bool(re.search(pattern, title))
                             for pattern in patterns)

    # Add appropriate notes based on the title analysis
    notes = []
    if title_has_series:
        notes.append(
            "Add 'series' if the title contains unusual numbering or format (volume numbers, episode numbers, etc)")
    if title_needs_rename:
        notes.append(
            "Add tag 'rename' as this appears to be a non-standard or system-generated title")

    # Combine formatting notes with additional prompt if provided
    extra_notes = []
    if notes:
        extra_notes.extend([f"{i+6}. {note}" for i, note in enumerate(notes)])
    if additional_prompt:
        extra_notes.append(f"{len(extra_notes)+6}. {additional_prompt}")
    formatting_notes = "\n" + "\n".join(extra_notes) if extra_notes else ""

    if description and description.strip():
        return f"""
You are a precise book cataloging assistant. Generate 4-6 high-quality, focused tags for this book.{existing_tags_str}

RULES:
1. Return ONLY a comma-separated tag, nothing else
2. Try to include:
   - 1 main genre or category
   - 1 theme or subject
   - 1 target sphere (age, audience, etc)
3. Use library tags as dictionary if provided
4. No compound words or concatenated terms (e.g., 'EarthquakeEngineering' → 'earthquake, engineering')
5. Split multi-concept terms into separate tags
6. Each tag must be a single, simple word without concatenation
7. No duplicates or near-synonyms{formatting_notes}

BOOK: "{title}"
DESCRIPTION: "{description}"

TAGS:
"""
    else:
        return f"""
You are a precise book cataloging assistant. Generate 3-4 high-quality, focused tags from this title.{existing_tags_str}

RULES:
1. Return ONLY a comma-separated tag, nothing else
2. Try to include:
   - 1 main genre or category
   - 1 theme or subject
   - 1 target sphere (age, audience, etc)
3. Use library tags as dictionary if provided
4. No compound words or concatenated terms (e.g., 'EarthquakeEngineering' → 'earthquake, engineering')
5. Split multi-concept terms into separate tags
6. Each tag must be a single, simple word without concatenation
7. No duplicates or near-synonyms{formatting_notes}

BOOK: "{title}"

TAGS:
"""


def generate_tags_with_gemini(title, description, provider, existing_tags=None, additional_prompt=None):
    """Generate tags using Google's Gemini AI."""
    import time
    prompt = get_prompt(title, description, existing_tags, additional_prompt)
    for key in provider.get_shuffled_keys():
        try:
            genai.configure(api_key=key)
            # --- ✅ CORRECTED LINE ---
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            response = model.generate_content(prompt)
            return response.text.strip().replace('\n', ',')
        except Exception as e:
            print(f"   ⚠️ Gemini Error: {str(e)}")
            time.sleep(4)  # Wait before trying the next key
            continue
    return None


def generate_tags_with_openai(title, description, provider, existing_tags=None, additional_prompt=None):
    """Generate tags using OpenAI's GPT models."""
    import time
    prompt = get_prompt(title, description, existing_tags, additional_prompt)
    for key in provider.get_shuffled_keys():
        try:
            openai.api_key = key
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates a comma-separated list of tags for books."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=100
            )
            return response.choices[0].message.content.strip().replace('\n', ',')
        except Exception as e:
            print(f"   ⚠️ OpenAI Error: {str(e)}")
            time.sleep(4)  # Wait before trying the next key
            continue
    return None


def generate_tags_with_ollama(title, description, provider, existing_tags=None, additional_prompt=None):
    """Generate tags using a local Ollama model."""
    import time
    model_name = provider.api_keys[0]  # The model name is stored as the "key"
    prompt = get_prompt(title, description, existing_tags, additional_prompt)

    try:
        # First verify the model is still available
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        response.raise_for_status()
        models = response.json().get("models", [])
        if not any(m.get("name") == model_name for m in models):
            print(
                f"   ⚠️ Ollama Error: Model '{model_name}' not found. Available models: {', '.join(m.get('name', '') for m in models)}")
            return None

        # Generate tags using the model
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9
                }
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        if "response" not in result:
            print(f"   ⚠️ Ollama Error: Unexpected response format: {result}")
            return None
        return result["response"].strip().replace('\n', ',')
    except requests.exceptions.ConnectionError:
        print("   ⚠️ Ollama Error: Could not connect to Ollama service. Is it running?")
        print("       Try running 'ollama serve' in a terminal")
    except requests.exceptions.HTTPError as e:
        print(f"   ⚠️ Ollama Error: HTTP error {e.response.status_code}")
        if e.response.status_code == 404:
            print("       Ensure Ollama is running and the model is downloaded")
            print(f"       Try running: ollama pull {model_name}")
    except Exception as e:
        print(f"   ⚠️ Ollama Error: {str(e)}")
    time.sleep(2)
    return None


def generate_tags_with_ai(title, description, providers, existing_tags=None, additional_prompt=None):
    """Generate tags by trying each configured AI provider in order."""
    print("   🧠 Asking AI for tags...")

    # Define a mapping from provider name to function
    provider_functions = {
        "Gemini": generate_tags_with_gemini,
        "OpenAI": generate_tags_with_openai,
        "Ollama": generate_tags_with_ollama,
    }

    for provider in providers:
        if provider.is_configured and provider.name in provider_functions:
            print(f"   Trying provider: {provider.name}...")
            result = provider_functions[provider.name](
                title, description, provider, existing_tags, additional_prompt)
            if result:
                return result
    return None


# --- Main Execution Logic ---

def main():
    """Main function to parse arguments and run the tagging process."""
    parser = argparse.ArgumentParser(
        description="Auto-tag Calibre books using AI.")
    parser.add_argument("--library-path", required=True,
                        help="Full path to your Calibre library folder.")
    parser.add_argument(
        "--limit", type=int, help="Limit the number of books to process (for testing).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without making changes.")
    parser.add_argument("--overwrite", action="store_true",
                        help="Replace all existing tags instead of appending.")
    parser.add_argument("--provider", choices=["gemini", "openai", "ollama", "all"],
                        default="all", help="Choose a specific AI provider or try all available.")
    parser.add_argument("--prompt", type=str,
                        help="Additional instructions for the AI tagger (e.g., 'Add language tag for non-English titles')")
    args = parser.parse_args()

    if not os.path.isdir(args.library_path):
        print(f"❌ Error: Library path not found at '{args.library_path}'")
        return

    all_providers = configure_ai()

    # Filter providers based on user's choice
    if args.provider != "all":
        selected_providers = [
            p for p in all_providers if p.name.lower() == args.provider]
    else:
        selected_providers = all_providers

    if not selected_providers:
        print(
            f"❌ Error: The selected provider '{args.provider}' is not configured or available.")
        return

    books = get_books_from_calibre(args.library_path, args.limit)
    if not books:
        print("No books found or an error occurred. Exiting.")
        return

    if args.dry_run:
        print("\n" + "="*20 + " DRY RUN " + "="*20)
        print("No changes will be made to your library.")
        print("="*51 + "\n")

    for i, book in enumerate(books):
        print(
            f"\n[{i+1}/{len(books)}] Processing '{book['title']}' (ID: {book['id']})")
        print(f"   Existing Tags: {book.get('tags') or 'None'}")

        ai_tags_str = generate_tags_with_ai(
            book['title'],
            book.get('comments', ''),
            selected_providers,
            book.get('tags'),
            args.prompt)

        if not ai_tags_str:
            print("   ⚠️ Skipping book: Failed to generate tags from any AI provider.")
            continue

        new_tags = [tag.strip()
                    for tag in ai_tags_str.split(',') if tag.strip()]

        if args.dry_run:
            print(f"   DRY RUN: Would apply tags: {', '.join(new_tags)}")
        else:
            set_tags_in_calibre(args.library_path,
                                book['id'], new_tags, args.overwrite)
            print("   ✅ Successfully applied tags.")

    print("\n✨ Tagging process complete! ✨")


if __name__ == "__main__":
    main()
