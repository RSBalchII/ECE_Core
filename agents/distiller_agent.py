import requests
import os

API_HUB_URL = "http://localhost:8080/api/v1/chat/completions"

class DistillerAgent:
    def distill_and_update_working_memory(self, source_file_path: str, destination_file_path: str):
        """
        Reads the latest text from a source file, sends it to the API Hub for summarization,
        and appends the result to a destination file.
        """
        print("Distilling text...")
        try:
            with open(source_file_path, 'r', encoding='utf-8') as f:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                f.seek(max(0, file_size - 500), os.SEEK_SET)
                last_500_chars = f.read()

            if not last_500_chars:
                print("Source file is empty or has less than 500 characters of new content.")
                return

            payload = {
                "model": "local-model",
                "messages": [
                    {
                        "role": "system",
                        "content": "distill the following text into a concise summary"
                    },
                    {
                        "role": "user",
                        "content": last_500_chars
                    }
                ]
            }

            response = requests.post(API_HUB_URL, json=payload)
            response.raise_for_status()

            summary = response.json()['choices'][0]['message']['content']

            print("Appending summary to working memory.")
            with open(destination_file_path, 'a', encoding='utf-8') as f:
                f.write(summary + '\n')

        except FileNotFoundError:
            print(f"Error: Source file not found at {source_file_path}")
        except requests.exceptions.RequestException as e:
            print(f"Error calling API: {e}")
        except (KeyError, IndexError) as e:
            print(f"Error processing API response: {e}")
            print("Response JSON:", response.json())


if __name__ == '__main__':
    agent = DistillerAgent()

    # Create dummy files for testing
    source_file = "test_main_context.md"
    dest_file = "test_working_memory.md"

    # Add some text to the source file
    with open(source_file, 'w', encoding='utf-8') as f:
        # Create a file with more than 500 characters to test the logic
        f.write("This is some initial text that is not very important. " * 20)
        f.write("The agent should ignore all of this and only focus on the last 500 characters. ")
        f.write("Let's add a lot more padding here to be sure. " * 20)
        f.write("This is the really important information that we want to be summarized. It's located at the very end of the file.")

    print(f"--- Running distillation on '{source_file}' ---")
    agent.distill_and_update_working_memory(source_file, dest_file)

    # Verify the result (if a summary was written)
    if os.path.exists(dest_file):
        with open(dest_file, 'r', encoding='utf-8') as f:
            print(f"\n--- Content of '{dest_file}' ---")
            print(f.read())
    else:
        print(f"\n--- '{dest_file}' was not created. This is expected if the API at {API_HUB_URL} is not running. ---")

    # Clean up the dummy files
    print("\n--- Cleaning up test files ---")
    if os.path.exists(source_file):
        os.remove(source_file)
        print(f"Removed '{source_file}'")
    if os.path.exists(dest_file):
        os.remove(dest_file)
        print(f"Removed '{dest_file}'")
