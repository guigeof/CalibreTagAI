import os
import subprocess
import json
import argparse
import shlex
from dotenv import load_dotenv
import google.generativeai as genai

# --- Configuration ---

def configure_ai():
    """
    Loads environment variables and configures the Google AI API.
    """
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found in .env file.")
        print("Please create a .env file and add your Google AI API key.")
        exit(1)
    genai.configure(api_key=api_key)

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
        result = subprocess.run(command, capture_output=True, text=True, check=True)
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
            result = subprocess.run(get_command, capture_output=True, text=True, check=True)
            existing_data = json.loads(result.stdout)
            if existing_data and 'tags' in existing_data[0]:
                existing_tags = existing_data[0]['tags'].split(',')
                # Combine and remove duplicates
                tags_list = sorted(list(set(existing_tags + tags_list)))
                tags_str = ",".join(tags_list)
        except Exception as e:
            print(f"  ⚠️ Could not read existing tags for book {book_id}. Appending may not be perfect. Error: {e}")


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

def generate_tags_with_ai(title, description):
    """
    Uses the Gemini AI to generate tags based on a book's title and description.

    Args:
        title (str): The title of the book.
        description (str): The description/summary of the book.

    Returns:
        str: A comma-separated string of tags, or None on error.
    """
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
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

    try:
        print("  🧠 Asking AI for tags...")
        response = model.generate_content(prompt)
        # Clean up the response text
        tags_text = response.text.strip().replace('\n', '')
        return tags_text
    except Exception as e:
        print(f"  ❌ An error occurred with the AI API: {e}")
        return None

# --- Main Execution Logic ---

def main():
    """
    Main function to parse arguments and run the tagging process.
    """
    parser = argparse.ArgumentParser(description="Auto-tag Calibre books using AI.")
    parser.add_argument("--library-path", required=True, help="Full path to your Calibre library folder.")
    parser.add_argument("--limit", type=int, help="Limit the number of books to process (for testing).")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes.")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing tags instead of appending.")
    
    args = parser.parse_args()

    if not os.path.isdir(args.library_path):
        print(f"Error: Library path not found at '{args.library_path}'")
        return

    configure_ai()
    books = get_books_from_calibre(args.library_path, args.limit)

    if not books:
        print("No books found or an error occurred. Exiting.")
        return

    if args.dry_run:
        print("\n" + "="*20 + " DRY RUN " + "="*20)
        print("No changes will be made to your library.")
        print("="*51 + "\n")


    for i, book in enumerate(books):
        print(f"\n[{i+1}/{len(books)}] Processing '{book['title']}' (ID: {book['id']})")
        print(f"  Existing Tags: {book.get('tags', 'None')}")

        # Skip books that have no description
        if not book.get('comments'):
            print("  ⚠️ Skipping book: No description/comments found.")
            continue
            
        ai_tags_str = generate_tags_with_ai(book['title'], book['comments'])

        if not ai_tags_str:
            print("  ⚠️ Skipping book: Failed to generate tags from AI.")
            continue

        # Clean up the tags list
        new_tags = [tag.strip() for tag in ai_tags_str.split(',') if tag.strip()]

        if args.dry_run:
            print(f"  DRY RUN: Would apply tags: {', '.join(new_tags)}")
        else:
            set_tags_in_calibre(args.library_path, book['id'], new_tags, args.overwrite)
            print("  ✅ Successfully applied tags.")

    print("\n✨ Tagging process complete! ✨")


if __name__ == "__main__":
    main()
