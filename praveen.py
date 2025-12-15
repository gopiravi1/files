import cv2
import torch
import numpy as np
import os
from transformers import pipeline
from PIL import Image

# ==========================================
# USER CONFIGURATION
# ==========================================
# Replace with your actual video path
VIDEO_FILE_PATH = r"C:\Users\DEPINDENGPT71\Downloads\Untitled1.mp4"
OUTPUT_DIR = r"C:\Users\DEPINDENGPT71\Downloads\GeometricDepthMaps"

# Strength of the 3D separation (Try 5-10)
SHIFT_INTENSITY = 8 

# Inpainting fills black gaps left by shifting pixels. 
# Set to True for better quality, False for faster speed.
USE_INPAINTING = True 

# ==========================================
# PROCESSING LOGIC
# ==========================================

def load_depth_model():
    """
    Loads 'Depth Anything V2' which provides sharper edges than MiDaS.
    """
    print("Loading Depth Anything V2 model... (First run will download ~100MB)")
    device = 0 if torch.cuda.is_available() else -1
    
    # We use the 'Small' version for a good balance of speed and quality.
    # You can swap 'Small' with 'Base' or 'Large' if you have a powerful GPU.
    pipe = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device=device)
    return pipe

def warp_and_fill(img, depth, shift, direction):
    """
    Warps the image pixels and uses Inpainting to fill the empty gaps.
    direction: 1 = Left Eye, -1 = Right Eye
    """
    h, w, c = img.shape
    
    # Normalize depth map to 0.0 - 1.0 range
    depth_min = depth.min()
    depth_max = depth.max()
    depth_norm = (depth - depth_min) / (depth_max - depth_min)
    
    # Create the flow map: Foreground (high depth) shifts more than background.
    flow = depth_norm * shift * direction

    # Create coordinate grid
    x_coords, y_coords = np.meshgrid(np.arange(w), np.arange(h))
    
    # Apply the shift to X coordinates
    x_shifted = x_coords + flow
    x_shifted = np.clip(x_shifted, 0, w - 1).astype(np.float32)
    
    # Remap (Warp) the image
    # We use BORDER_CONSTANT to leave black gaps where pixels moved away
    warped = cv2.remap(img, x_shifted, y_coords.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0,0,0))
    
    # -- INPAINTING STEP --
    if USE_INPAINTING:
        # Convert to grayscale to find the black holes (pixels that are 0,0,0)
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        
        # Create a mask: 255 where the image is black (hole), 0 otherwise
        mask = (gray == 0).astype(np.uint8) * 255
        
        # Apply inpainting: Fills holes based on surrounding pixel data
        # radius=3 is usually sufficient for 3D shifts
        warped = cv2.inpaint(warped, mask, 3, cv2.INPAINT_TELEA)
        
    return warped

def convert_video():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    filename = os.path.basename(VIDEO_FILE_PATH)
    name, ext = os.path.splitext(filename)
    output_path = os.path.join(OUTPUT_DIR, f"HQ_DepthAnything_{name}.mp4")

    # 1. Load Model
    depth_pipe = load_depth_model()

    # 2. Open Video Source
    cap = cv2.VideoCapture(VIDEO_FILE_PATH)
    if not cap.isOpened():
        print("Error opening video file.")
        return

    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps    = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # 3. Setup Video Writer (Double FPS for Frame Sequential)
    output_fps = fps * 2
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, output_fps, (width, height))

    print(f"Processing {total_frames} frames with high-quality settings...")
    
    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # -- AI INFERENCE --
        # Convert BGR (OpenCV) to RGB (PIL) for the AI model
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        
        # Get depth map
        depth_result = depth_pipe(pil_img)
        depth_map = np.array(depth_result["depth"])
        
        # Resize depth map to match video resolution exactly
        depth_map = cv2.resize(depth_map, (width, height))

        # -- GENERATE VIEWS --
        # Calculate maximum pixel shift
        max_shift = int(width * (SHIFT_INTENSITY / 100))
        
        # Generate Left and Right views with hole filling
        # Left Eye (Shift content Right, direction +1)
        left_view = warp_and_fill(frame, depth_map, max_shift, 1)
        
        # Right Eye (Shift content Left, direction -1)
        right_view = warp_and_fill(frame, depth_map, max_shift, -1)

        # -- WRITE SEQUENTIAL FRAMES --
        out.write(left_view)
        out.write(right_view)
        
        frame_idx += 1
        print(f"Processed Frame {frame_idx}/{total_frames}", end='\r')

    cap.release()
    out.release()
    print(f"\nDone! High Quality video saved to:\n{output_path}")

if __name__ == "__main__":
    convert_video()