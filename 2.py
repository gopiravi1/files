import os
from PIL import Image
from google import genai
from google.genai import types
from io import BytesIO
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

import google.genai.errors as genai_errors 

# --- Configuration ---

# WARNING: Please regenerate your API key after testing.
client = genai.Client(api_key="AIzaSyB8sgHT6x3Gxq41Ypz05vRRDmM_w56Q_d8") 

# Model optimized for multi-turn (sequential) image editing
MODEL_ID = "gemini-3-pro-image-preview"

# Define the retry configuration for the API call
@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(15), # <--- CHANGED TO 15 SECONDS
    retry=retry_if_exception_type(genai_errors.APIError),
    before_sleep=lambda retry_state: print(
        # --- Updated Print Statement to reflect 15 seconds ---
        f"API Error (Possible 429 Quota). Retrying in 15 seconds (Attempt {retry_state.attempt_number}/3)..."
    )
)
def send_message_with_retry(chat_session, content):
    """Wrapper function to send message with retry logic for API errors."""
    return chat_session.send_message(content)


# --- Main Function ---

def process_sequential_edits(base_image_path, comments_list, output_dir="output_steps"):
    """
    Performs a sequence of image edits using a persistent chat session 
    to maintain context across steps.
    """
    
    # 1. Setup Output Directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    # 2. Load Initial Image
    try:
        current_image = Image.open(base_image_path)
        current_image.save(os.path.join(output_dir, "step_0_base.png"))
    except FileNotFoundError:
        print(f"Error: Base image not found at {base_image_path}")
        return

    # 3. Initialize Chat Session
    try:
        chat = client.chats.create(
            model=MODEL_ID,
            config=types.GenerateContentConfig(
                response_modalities=["image", "text"], 
                safety_settings=[] 
            )
        )
    except Exception as e:
        if isinstance(e, genai_errors.APIError):
             print(f"Error initializing chat: API Error. Check your connection or quota.")
        else:
             print(f"Error initializing chat session. Check your API key and model ID: {e}")
        return
        
    results = [] 
    print(f"Starting Sequential Batch with model: {MODEL_ID}")

    for i, comment in enumerate(comments_list):
        step_num = i + 1
        print(f"\n--- Processing Step {step_num}: '{comment}' ---")
        
        try:
            # 4. Send Message with Reasoning (Uses the retry wrapper function)
            response = send_message_with_retry(chat, [comment, current_image])

            # 5. Extract and Process Response
            image_generated = False
            
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    
                    if part.text:
                        print(f"Model Reasoning: {part.text}")
                    
                    if part.inline_data:
                        from io import BytesIO
                        img_data = part.inline_data.data
                        generated_image = Image.open(BytesIO(img_data))
                        
                        save_path = os.path.join(output_dir, f"step_{step_num}_output.png")
                        generated_image.save(save_path)
                        
                        current_image = generated_image
                        results.append(generated_image)
                        image_generated = True
                        print(f"✓ Saved: {save_path}")

            if not image_generated:
                warning_text = response.text if response.text else "No text part received."
                print(f"⚠ Warning: No image generated for step {step_num}. Response: {warning_text}")

        except Exception as e:
            # This block runs only if the retry attempts failed completely
            print(f"✘ Fatal Error at step {step_num} after retries: {e}")
            break

    return results

# --- Example Usage ---

if __name__ == "__main__":
    comments = [
        "Change the background to a cyberpunk city night scene",
        "Add heavy rain effects and neon reflections",
        "Give the character a glowing visor"
    ]
    
    # 2. Define the base image file path
    base_image_file = r"C:\Users\DEPINDENGPT71\Downloads\s\base.png" 
    
    # 3. Call the function
    process_sequential_edits(base_image_file, comments)
    
    print("\n--- Script execution finished ---")