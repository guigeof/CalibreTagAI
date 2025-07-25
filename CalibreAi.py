import os
import subprocess
import json
import argparse
import shlex
from dotenv import load_dotenv
import google.generativeai as genai
import random
try:
    import openai
except ImportError:
    openai = None

# --- Configuration ---


class AIProvider:
    def __init__(self, name, key_env_var, is_configured=False):
        self.name = name
        self.key_env_var = key_env_var
        self.is_configured = is_configured
        self.api_keys = []

    def configure(self, api_keys):
        if not api_keys:
            return False
        self.api_keys = api_keys
        self.is_configured = True
        return True

    def get_random_key(self):
        return random.choice(self.api_keys) if self.api_keys else None


class AIProviders:
    GEMINI = AIProvider("Gemini", "GOOGLE_API_KEYS")
    OPENAI = AIProvider("OpenAI", "OPENAI_API_KEYS")


def parse_keys_from_env(env_var):
    """Parse comma-separated API keys from environment variable."""
    keys = os.getenv(env_var, "").strip()
    return [k.strip() for k in keys.split(",")] if keys else []


def configure_ai():
    """
    Loads environment variables and configures the AI APIs.
    Returns a list of configured providers.
    """
    load_dotenv()
    configured_providers = []

    # Configure Gemini
    gemini_keys = parse_keys_from_env(AIProviders.GEMINI.key_env_var)
    if AIProviders.GEMINI.configure(gemini_keys):
        configured_providers.append(AIProviders.GEMINI)
        genai.configure(api_key=gemini_keys[0])  # Initial configuration

    # Configure OpenAI if available
    if openai:
        openai_keys = parse_keys_from_env(AIProviders.OPENAI.key_env_var)
        if AIProviders.OPENAI.configure(openai_keys):
            configured_providers.append(AIProviders.OPENAI)
            openai.api_key = openai_keys[0]  # Initial configuration

    if not configured_providers:
        print("Error: No AI providers configured.")
        print("Please add API keys to your .env file:")
        print("GOOGLE_API_KEYS=key1,key2,key3")
        print("OPENAI_API_KEYS=key1,key2,key3")
        exit(1)

    return configured_providers

# --- Calibre Interaction Functions ---


def get_books_from_calibre(library_path, limit=None):
    """
    Fetches book data from the Calibre library using the calibredb command.

    Args:
        library_path (str): The full path to the Calibre library.
        limit (int, optional): The maximum number of books to fetch.

    Returns:
        list: A list of dictionaries, where each dictionary represents a book.
        Returns an empty list on error.
    """
    print(f"📚 Accessing Calibre library at: {library_path}")
    command = [
        "calibredb",
        "list",
        "--for-machine",
        "--fields", "id,title,comments,tags",
        "--with-library", library_path
    ]
    if limit:
        command.extend(["--limit", str(limit)])

    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=True)
        books = json.loads(result.stdout)
        print(f"✅ Found {len(books)} books to process.")
        return books
    except FileNotFoundError:
        print("Error: 'calibredb' command not found.")
        print("Please ensure Calibre is installed and its command-line tools are in your system's PATH.")
        return []
    except subprocess.CalledProcessError as e:
        print(f"Error executing calibredb command: {e}")
        print(f"Stderr: {e.stderr}")
        return []
    except json.JSONDecodeError:
        print("Error: Could not parse the output from calibredb. Is the library empty?")
        return []


def set_tags_in_calibre(library_path, book_id, tags_list, overwrite=False):
    """
    Sets tags for a specific book in the Calibre library.

    Args:
        library_path (str): The full path to the Calibre library.
        book_id (int): The ID of the book to update.
        tags_list (list): A list of strings representing the tags.
        overwrite (bool): If True, replaces existing tags. If False, appends.
    """
    # Format the tags into a comma-separated string, enclosed in quotes.
    tags_str = ",".join(tags_list)

    # The operator determines if we append or overwrite.
    # Calibre's set_metadata uses ':=' for overwrite and nothing special for append/merge.
    # However, to be explicit and safe, we will set the full list.
    # First, get existing tags if we are not overwriting.
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
                get_command, capture_output=True, text=True, check=True)
            existing_data = json.loads(result.stdout)
            if existing_data and 'tags' in existing_data[0]:
                existing_tags = existing_data[0]['tags'].split(',')
                # Combine and remove duplicates
                tags_list = sorted(list(set(existing_tags + tags_list)))
                tags_str = ",".join(tags_list)
        except Exception as e:
            print(
                f"  ⚠️ Could not read existing tags for book {book_id}. Appending may not be perfect. Error: {e}")

    print(f"  🏷️  Applying tags: {tags_str}")

    command = [
        "calibredb",
        "set_metadata",
        "--field", f"tags:\"{tags_str}\"",
        str(book_id),
        "--with-library", library_path
    ]

    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Error setting metadata for book ID {book_id}.")
        print(f"  Stderr: {e.stderr}")


# --- AI Tag Generation ---

def generate_tags_with_gemini(title, description, provider):
    """Generate tags using Google's Gemini AI."""
    import time
    time.sleep(4)  # Add a delay between requests to avoid rate limits

    # Rotate API keys on error
    for _ in range(len(provider.api_keys)):
        try:
            key = provider.get_random_key()
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(get_prompt(title, description))
            return response.text.strip().replace('\n', '')
        except Exception as e:
            print(f"  ⚠️ Error with Gemini key: {str(e)}")
            continue
    return None


def generate_tags_with_openai(title, description, provider):
    """Generate tags using OpenAI's GPT models."""
    import time
    time.sleep(4)  # Add a delay between requests to avoid rate limits

    # Rotate API keys on error
    for _ in range(len(provider.api_keys)):
        try:
            key = provider.get_random_key()
            openai.api_key = key
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates tags for books."},
                    {"role": "user", "content": get_prompt(title, description)}
                ],
                temperature=0.7,
                max_tokens=100
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"  ⚠️ Error with OpenAI key: {str(e)}")
            continue
    return None


def get_prompt(title, description):
    """Get the appropriate prompt based on available information."""

    # Prepare the prompt based on available information
    if description:
        return f"""
    Analyze the following book information and generate a list of 8-12 relevant tags.
    The tags should cover genre, sub-genre, key themes, character archetypes, setting, and tone.

    RULES:
    - Return ONLY a single line of comma-separated tags.
    - Do not include any other text, preamble, or explanation.
    - Example format: Fantasy,Epic Fantasy,Magic,Quest,Good vs Evil,Medieval,Dragons,Chosen One

    BOOK TITLE: "{title}"
    BOOK DESCRIPTION: "{description}"

    TAGS:
    """
    else:
        return f"""
    Based on this book title, generate a list of 5-8 relevant tags.
    Analyze the title carefully for subject matter, themes, and potential genre.
    Consider any keywords, topics, or cultural references in the title.

    RULES:
    - Return ONLY a single line of comma-separated tags.
    - Do not include any other text, preamble, or explanation.
    - Be confident in your analysis but not overly specific without more context.
    - Example format: Non-Fiction,History,Ancient Civilizations,Research

    BOOK TITLE: "{title}"

    TAGS:
    """


def generate_tags_with_ai(title, description, configured_providers):
    """
    Generate tags using available AI providers.
    Tries each configured provider in turn until successful.
    """
    print("  🧠 Asking AI for tags...")

    for provider in configured_providers:
        if provider.name == "Gemini":
            result = generate_tags_with_gemini(title, description, provider)
            if result:
                return result
        elif provider.name == "OpenAI" and openai:
            result = generate_tags_with_openai(title, description, provider)
            if result:
                return result

    return None

# --- Main Execution Logic ---


def main():
    """
    Main function to parse arguments and run the tagging process.
    """
    parser = argparse.ArgumentParser(
        description="Auto-tag Calibre books using AI.")
    parser.add_argument("--library-path", required=True,
                        help="Full path to your Calibre library folder.")
    parser.add_argument(
        "--limit", type=int, help="Limit the number of books to process (for testing).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without making changes.")
    parser.add_argument("--overwrite", action="store_true",
                        help="Replace existing tags instead of appending.")
    parser.add_argument("--provider", choices=["gemini", "openai", "all"],
                        default="all", help="Choose which AI provider to use.")

    args = parser.parse_args()

    if not os.path.isdir(args.library_path):
        print(f"Error: Library path not found at '{args.library_path}'")
        return

    # Configure AI providers based on user selection
    all_providers = configure_ai()
    selected_providers = []

    if args.provider == "all":
        selected_providers = all_providers
    else:
        for provider in all_providers:
            if provider.name.lower() == args.provider:
                selected_providers = [provider]
                break

    if not selected_providers:
        print(f"Error: No AI providers available for '{args.provider}'")
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
        print(f"  Existing Tags: {book.get('tags', 'None')}")

        # Get AI tags based on title and description (if available)
        ai_tags_str = generate_tags_with_ai(
            book['title'], book.get('comments', ''), selected_providers)

        if not ai_tags_str:
            print("  ⚠️ Skipping book: Failed to generate tags from AI.")
            continue

        # Clean up the tags list
        new_tags = [tag.strip()
                    for tag in ai_tags_str.split(',') if tag.strip()]

        if args.dry_run:
            print(f"  DRY RUN: Would apply tags: {', '.join(new_tags)}")
        else:
            set_tags_in_calibre(args.library_path,
                                book['id'], new_tags, args.overwrite)
            print("  ✅ Successfully applied tags.")

    print("\n✨ Tagging process complete! ✨")


if __name__ == "__main__":
    main()
