import os
import math
import glob
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
from moviepy.editor import VideoFileClip

def split_video_by_size(input_file, target_size_mb=90):
    
    # 1. Validate file exists
    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found.")
        return

    # 2. Get file size in bytes
    file_size_bytes = os.path.getsize(input_file)
    target_size_bytes = target_size_mb * 1024 * 1024

    # 3. Check if splitting is necessary
    if file_size_bytes <= target_size_bytes:
        print(f"File is already smaller than {target_size_mb}MB. No splitting needed.")
        return

    print(f"Processing: {input_file}")
    print(f"Total Size: {file_size_bytes / (1024*1024):.2f} MB")
    
    # 4. Get video duration
    # We use VideoFileClip to get precise duration metadata
    try:
        clip = VideoFileClip(input_file)
        duration_seconds = clip.duration
        clip.close() # Close the clip to release resources
    except Exception as e:
        print(f"Error reading video metadata: {e}")
        return

    # 5. Calculate split parameters
    # We assume constant bitrate to estimate the duration required for 90MB.
    # Formula: (Target Size / Total Size) * Total Duration
    chunk_duration = (target_size_bytes / file_size_bytes) * duration_seconds
    
    total_chunks = math.ceil(duration_seconds / chunk_duration)
    
    print(f"Total Duration: {duration_seconds:.2f} seconds")
    print(f"Estimated Chunk Duration: {chunk_duration:.2f} seconds")
    print(f"Splitting into approximately {total_chunks} parts...")

    # 6. Split the file
    base_name, ext = os.path.splitext(input_file)
    
    for i in range(total_chunks):
        start_time = i * chunk_duration
        end_time = min((i + 1) * chunk_duration, duration_seconds)
        
        target_name = f"{base_name}_part{i+1}{ext}"
        
        print(f"Writing {target_name} ({start_time:.2f}s to {end_time:.2f}s)...")
        
        # ffmpeg_extract_subclip performs a "stream copy".
        # It is very fast and does not re-encode the video (no quality loss).
        ffmpeg_extract_subclip(input_file, start_time, end_time, targetname=target_name)

    print("Done! Splitting complete.")

if __name__ == "__main__":
    # Directory containing the video files
    input_DIR = r"C:\Users\DEPINDENGPT71\Downloads\GeometricDepthMaps"
    
    # Find all MP4 files in the directory
    # You can add other extensions if needed, e.g., *.mov, *.mkv
    video_files = glob.glob(os.path.join(input_DIR, "*.mp4"))
    
    if not video_files:
        print(f"No MP4 files found in {input_DIR}")
    else:
        print(f"Found {len(video_files)} videos. Starting processing...")
        
        for video_path in video_files:
            print(f"\n--- Processing {os.path.basename(video_path)} ---")
            split_video_by_size(video_path, target_size_mb=90)