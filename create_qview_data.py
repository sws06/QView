import json
import os
import datetime

# --- CONFIGURATION ---
# Path to the original JSON file from J. Kingsman
ORIGINAL_JSON_PATH = "posts.url-normalized.json"
# Path where our new standardized JSON will be saved
# It's good practice to save it in user_data if QView will look for it there,
# or in the root if you plan to bundle it directly with the app scripts.
# For now, let's assume we'll save it in the same directory as this script,
# and you can then move it to be alongside main.py for QView to use.
OUTPUT_JSON_PATH = "qview_posts_data.json"
# --- END CONFIGURATION ---

def convert_post_data():
    """
    Reads the original posts.url-normalized.json, transforms it into the new
    QView standard format, and saves it.
    """
    qview_posts_list = []

    print(f"Loading original data from: {ORIGINAL_JSON_PATH}...")
    try:
        with open(ORIGINAL_JSON_PATH, 'r', encoding='utf-8') as f:
            original_data_wrapper = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Original data file not found at {ORIGINAL_JSON_PATH}")
        return
    except json.JSONDecodeError as e:
        print(f"ERROR: Could not decode JSON from {ORIGINAL_JSON_PATH}. Error: {e}")
        return
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while loading {ORIGINAL_JSON_PATH}. Error: {e}")
        return

    # The original JSON is a dictionary with a top-level key (e.g., 'posts') containing the list
    # Attempt to find the list of posts, common key is 'posts'
    original_posts_list = None
    if isinstance(original_data_wrapper, list):
        original_posts_list = original_data_wrapper
    elif isinstance(original_data_wrapper, dict):
        if 'posts' in original_data_wrapper and isinstance(original_data_wrapper['posts'], list):
            original_posts_list = original_data_wrapper['posts']
        else:
            # Try to find the first value that is a list, as some versions might have a different top key
            for value in original_data_wrapper.values():
                if isinstance(value, list):
                    original_posts_list = value
                    break
    
    if not original_posts_list:
        print("ERROR: Could not find a list of posts in the original JSON data.")
        return

    print(f"Found {len(original_posts_list)} posts in original data. Starting conversion...")

    for i, original_post in enumerate(original_posts_list):
        if not isinstance(original_post, dict):
            print(f"Warning: Skipping item at index {i} as it's not a dictionary.")
            continue

        new_post_object = {}
        post_metadata = original_post.get("post_metadata", {})
        source_info = post_metadata.get("source", {})

        # --- Map Basic Fields ---
        new_post_object["postNumber"] = original_post.get("id", post_metadata.get("id")) # Prefer top-level id if present
        new_post_object["timestamp"] = original_post.get("time", post_metadata.get("time"))
        new_post_object["text"] = original_post.get("text", "")

        # --- Map Author Info ---
        new_post_object["author"] = post_metadata.get("author")
        new_post_object["tripcode"] = post_metadata.get("tripcode")
        new_post_object["authorId"] = post_metadata.get("author_id") # from post_metadata

        # --- Map Source Info ---
        new_post_object["sourceLink"] = source_info.get("link")
        new_post_object["sourceSite"] = source_info.get("site")
        new_post_object["sourceBoard"] = source_info.get("board")

        # --- Map Images (directly attached to this post) ---
        new_images_list = []
        original_images_data = original_post.get("images", []) # This should be for the current post
        if original_images_data and isinstance(original_images_data, list):
            for img_data in original_images_data:
                if isinstance(img_data, dict):
                    new_images_list.append({
                        "filename": img_data.get("file"),
                        "originalName": img_data.get("name")
                    })
        new_post_object["images"] = new_images_list

        # --- Map Referenced Posts ---
        new_references_list = []
        original_references_data = original_post.get("referenced_posts", [])
        if original_references_data and isinstance(original_references_data, list):
            for ref_data in original_references_data:
                if isinstance(ref_data, dict):
                    new_ref_object = {
                        "referenceID": ref_data.get("reference"),
                        "referencedPostAuthorID": ref_data.get("author_id"),
                        "textContent": ref_data.get("text"),
                        "images": [] # Initialize as empty list for images within this specific quote
                    }
                    # Now, process images if present in ref_data (for this specific quoted post)
                    original_ref_images = ref_data.get("images", []) # Get images from the current ref_data
                    if original_ref_images and isinstance(original_ref_images, list):
                        for ref_img_data in original_ref_images:
                            if isinstance(ref_img_data, dict):
                                new_ref_object["images"].append({
                                    "filename": ref_img_data.get("file"), # Should map to "file" from original
                                    "originalName": ref_img_data.get("name")  # Should map to "name" from original
                                })
                    new_references_list.append(new_ref_object)
        new_post_object["referencedPosts"] = new_references_list
        
        # Ensure all keys from our defined structure are present, even if null
        for key in ["postNumber", "timestamp", "text", "author", "tripcode", "authorId", 
                    "images", "sourceLink", "sourceSite", "sourceBoard", "referencedPosts"]:
            if key not in new_post_object:
                if key == "images" or key == "referencedPosts":
                    new_post_object[key] = []
                else:
                    new_post_object[key] = None
        
        # Sanity check for essential data
        if new_post_object["postNumber"] is None or new_post_object["timestamp"] is None:
            print(f"Warning: Skipping post at original index {i} due to missing critical 'id' or 'time'. Original data: {original_post.get('id')} / {post_metadata.get('id')}")
            continue


        qview_posts_list.append(new_post_object)

    print(f"Conversion processed. {len(qview_posts_list)} posts transformed.")
    print(f"Saving transformed data to: {OUTPUT_JSON_PATH}...")
    try:
        with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(qview_posts_list, f, indent=2) # Using indent=2 for slightly smaller file size than 4
        print("Successfully saved the new JSON data file.")
    except IOError as e:
        print(f"ERROR: Could not write output file to {OUTPUT_JSON_PATH}. Error: {e}")
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while saving {OUTPUT_JSON_PATH}. Error: {e}")


if __name__ == "__main__":
    # Ensure the script is run from the QView root directory or adjust paths accordingly
    # For simplicity, this script assumes posts.url-normalized.json is in the same directory
    # and will output qview_posts_data.json in the same directory.
    
    # Check if original file exists before starting
    if not os.path.exists(ORIGINAL_JSON_PATH):
        print(f"FATAL ERROR: The input file '{ORIGINAL_JSON_PATH}' was not found in the current directory.")
        print("Please place it in the same directory as this script, or update ORIGINAL_JSON_PATH in the script.")
    else:
        convert_post_data()