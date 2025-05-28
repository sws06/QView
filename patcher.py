# --- START PATCHER_PY_HEADER ---
import os
import re

# --- END PATCHER_PY_HEADER ---


# --- START APPLY_PATCH_FUNCTION ---
def apply_patch(patch_file_path):
    """
    Applies patches defined in a patch instruction file.
    Each instruction should specify:
    FILE: target_file.py
    START_TAG: # --- START UNIQUE_BLOCK_NAME ---
    END_TAG: # --- END UNIQUE_BLOCK_NAME ---
    CONTENT:
    # --- START UNIQUE_BLOCK_NAME ---
    New multi-line
    content for the block
    # --- END UNIQUE_BLOCK_NAME ---
    --- (separator for next instruction)
    """
    try:
        with open(patch_file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Patch file '{patch_file_path}' not found.")
        return
    except Exception as e:
        print(f"Error reading patch file '{patch_file_path}': {e}")
        return

    instructions = content.split("\n---\n")  # Split by '---' separator on its own line

    for i, instruction_block in enumerate(instructions):
        instruction_block = (
            instruction_block.strip()
        )  # Strip the whole instruction block
        if not instruction_block:
            continue

        print(f"\nProcessing instruction {i+1}...")

        try:
            # Extract tags and content carefully
            file_match = re.search(r"FILE:\s*(.+)", instruction_block)
            # Use a more robust way to get tags, preserving leading/trailing spaces on the tag line itself
            start_tag_line_match = re.search(
                r"^START_TAG:(.*)$", instruction_block, re.MULTILINE
            )
            end_tag_line_match = re.search(
                r"^END_TAG:(.*)$", instruction_block, re.MULTILINE
            )

            content_header_match = re.search(
                r"CONTENT:\n", instruction_block, re.DOTALL
            )

            if not (
                file_match
                and start_tag_line_match
                and end_tag_line_match
                and content_header_match
            ):
                print(
                    f"Error: Instruction {i+1} is malformed. Missing FILE, START_TAG, END_TAG, or 'CONTENT:\\n' line."
                )
                continue

            target_file = file_match.group(1).strip()
            # Get the tag content *exactly* as it is after "START_TAG:" or "END_TAG:", including leading/trailing spaces on that line
            start_tag = start_tag_line_match.group(1)
            end_tag = end_tag_line_match.group(1)

            # Remove only the single leading space if present, but keep intentional indentation
            if start_tag.startswith(" "):
                start_tag = start_tag[1:]
            if end_tag.startswith(" "):
                end_tag = end_tag[1:]

            new_content = instruction_block[content_header_match.end() :]

            if not os.path.exists(target_file):
                print(
                    f"Error: Target file '{target_file}' for instruction {i+1} does not exist."
                )
                continue

            print(f"  Target File: {target_file}")
            print(
                f"  Start Tag (as used): '{start_tag}'"
            )  # Show what's actually being used
            print(f"  End Tag (as used): '{end_tag}'")

            with open(target_file, "r", encoding="utf-8") as f_target:
                target_content = f_target.read()

            escaped_start_tag = re.escape(start_tag)
            escaped_end_tag = re.escape(end_tag)

            pattern = None
            if start_tag == end_tag:
                pattern = re.compile(f"^{escaped_start_tag}$", re.MULTILINE)
            else:
                pattern = re.compile(
                    f"^{escaped_start_tag}$.*?^{escaped_end_tag}$",
                    re.MULTILINE | re.DOTALL,
                )

            match = pattern.search(target_content)

            if match:
                updated_target_content = (
                    target_content[: match.start()]
                    + new_content
                    + target_content[match.end() :]
                )

                with open(target_file, "w", encoding="utf-8") as f_target:
                    f_target.write(updated_target_content)
                print(
                    f"  Success: Block identified by '{start_tag}' (and '{end_tag}') in '{target_file}' was updated."
                )
            else:
                print(
                    f"  Warning: Block identified by '{start_tag}' and '{end_tag}' not found in '{target_file}'. No changes made for this instruction."
                )

        except Exception as e:
            print(f"Error processing instruction {i+1}: {e}")
            import traceback

            traceback.print_exc()


# --- END APPLY_PATCH_FUNCTION ---

# --- START PATCHER_MAIN_EXECUTION ---
if __name__ == "__main__":
    default_patch_instructions_file = "patch_instructions.txt"
    patch_file_to_use = input(
        f"Enter path to patch instructions file (default: {default_patch_instructions_file}): "
    )
    if not patch_file_to_use.strip():
        patch_file_to_use = default_patch_instructions_file

    if os.path.exists(patch_file_to_use):
        apply_patch(patch_file_to_use)
        print("\nPatcher finished.")
    else:
        print(
            f"Patch file '{patch_file_to_use}' not found. To use the patcher, create this file with patch instructions."
        )
        print("Example instruction format within the file:")
        print(
            """
FILE: gui.py
START_TAG:     # --- START INDENTED_BLOCK ---
END_TAG:     # --- END INDENTED_BLOCK ---
CONTENT:
    # --- START INDENTED_BLOCK ---
    # New content
    # --- END INDENTED_BLOCK ---
---
FILE: utils.py
START_TAG: # --- START TOP_LEVEL_BLOCK ---
END_TAG: # --- END TOP_LEVEL_BLOCK ---
CONTENT:
# --- START TOP_LEVEL_BLOCK ---
# More new content.
# --- END TOP_LEVEL_BLOCK ---
"""
        )
# --- END PATCHER_MAIN_EXECUTION ---
