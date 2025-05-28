import os
import shutil

import pandas as pd
import requests

# --- Configuration ---
DATAFRAME_PICKLE_PATH = r"c:\users\william\qposts\posts_df.pkl"
BASE_DATA_DIR = os.path.dirname(DATAFRAME_PICKLE_PATH)
IMAGE_DIR = os.path.join(BASE_DATA_DIR, "q_images")  # Local directory to save images
QANON_PUB_MEDIA_BASE_URL = "https://www.qanon.pub/data/media/"


def download_all_post_images(df_path):
    """
    Downloads images for posts from the DataFrame.
    """
    print(f"Loading DataFrame from: {df_path}")
    try:
        df = pd.read_pickle(df_path)
    except FileNotFoundError:
        print(f"Error: DataFrame pickle file not found at {df_path}")
        return
    except Exception as e:
        print(f"Error loading DataFrame: {e}")
        return

    if "ImagesJSON" not in df.columns:
        print("Error: 'ImagesJSON' column not found in the DataFrame.")
        print(
            "Please ensure your Q_Ninja script's load_or_parse_data function is updated to include it and re-create the pickle."
        )
        return

    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)
        print(f"Created image directory: {IMAGE_DIR}")

    total_images_downloaded = 0
    total_images_skipped = 0
    total_posts_with_images = 0
    posts_processed = 0

    for index, row in df.iterrows():
        posts_processed += 1
        images_in_post = row.get("ImagesJSON", [])

        if not images_in_post or not isinstance(images_in_post, list):
            continue

        total_posts_with_images += 1
        post_id_display = row.get("Post Number", f"index_{index}")

        for img_data in images_in_post:
            if not isinstance(img_data, dict):
                print(
                    f"Warning: Malformed image data in post {post_id_display}: {img_data}"
                )
                continue

            img_filename = img_data.get("file")
            if not img_filename:
                print(
                    f"Warning: Missing 'file' field in image data for post {post_id_display}: {img_data}"
                )
                continue

            image_url = QANON_PUB_MEDIA_BASE_URL + img_filename
            local_image_path = os.path.join(IMAGE_DIR, img_filename)

            if not os.path.exists(local_image_path):
                try:
                    print(
                        f"Downloading (Post {post_id_display}): {image_url} to {local_image_path}..."
                    )
                    response = requests.get(
                        image_url, stream=True, timeout=20
                    )  # Increased timeout
                    response.raise_for_status()

                    with open(local_image_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    print(f"Successfully downloaded {img_filename}")
                    total_images_downloaded += 1
                except requests.exceptions.HTTPError as e:
                    print(f"HTTP Error downloading {image_url}: {e}")
                except requests.exceptions.ConnectionError as e:
                    print(f"Connection Error downloading {image_url}: {e}")
                except requests.exceptions.Timeout:
                    print(f"Timeout downloading {image_url}")
                except requests.exceptions.RequestException as e:
                    print(f"General Error downloading {image_url}: {e}")
                except Exception as e:
                    print(f"An unexpected error occurred with {image_url}: {e}")
            else:
                # print(f"Skipped: Image {img_filename} already exists locally.")
                total_images_skipped += 1

        if posts_processed % 100 == 0:
            print(f"Processed {posts_processed}/{len(df)} posts...")

    print("\n--- Download Summary ---")
    print(f"Total posts processed: {posts_processed}")
    print(f"Total posts found with image data: {total_posts_with_images}")
    print(f"Total images newly downloaded: {total_images_downloaded}")
    print(f"Total images skipped (already exist): {total_images_skipped}")
    print(f"Images are saved in: {IMAGE_DIR}")


if __name__ == "__main__":
    if not os.path.exists(DATAFRAME_PICKLE_PATH):
        print(
            f"Pickle file {DATAFRAME_PICKLE_PATH} does not exist. Please run your main Q_Ninja GUI script first to generate it with the 'ImagesJSON' column."
        )
    else:
        download_all_post_images(DATAFRAME_PICKLE_PATH)
