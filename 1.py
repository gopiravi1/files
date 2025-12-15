import sys
import os
import subprocess
import importlib
import time
import threading
import multiprocessing
import queue
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

# ==============================================================================
# 1. SELF-HEALING DEPENDENCY INSTALLER (Windows Compatible)
# ==============================================================================
def check_and_install_packages():
    """
    Installs required libraries to your D:\ drive environment automatically.
    """
    required = [
        ("google-generativeai", "google.generativeai"),
        ("pandas", "pandas"), 
        ("openpyxl", "openpyxl") # Required for Excel
    ]

    # Skip if running as compiled .exe
    if getattr(sys, 'frozen', False): 
        return

    for package, import_name in required:
        try:
            importlib.import_module(import_name)
        except ImportError:
            print(f"[*] Installing missing library: {package}...")
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", 
                    "--user", package, 
                    "--quiet", "--disable-pip-version-check"
                ])
                print(f"[+] {package} installed.")
            except Exception as e:
                print(f"[!] Install Failed: {e}")

# Run installer check
check_and_install_packages()

# Safe Imports
import pandas as pd
import google.generativeai as genai

# ==============================================================================
# 2. WORKER PROCESS (The Probe)
# ==============================================================================
def mariner_probe(task_data):
    """
    Runs on a separate CPU core to prevent GUI freezing.
    """
    topic = task_data['topic']
    api_key = task_data['api_key']
    instruction = task_data['instruction']
    
    start_time = time.time()
    
    try:
        genai.configure(api_key=api_key)
        # Use 'gemini-1.5-flash' for speed, or 'gemini-pro' for detail
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"INSTRUCTION: {instruction}\n\nTOPIC: {topic}"
        
        # Generate
        response = model.generate_content(prompt)
        
        if not response.parts:
             return {"status": "BLOCKED", "topic": topic, "output": "Safety Filter Triggered", "duration": 0}

        text_out = response.text.strip()
        duration = round(time.time() - start_time, 2)
        
        return {
            "status": "SUCCESS",
            "topic": topic,
            "output": text_out,
            "duration": duration
        }

    except Exception as e:
        return {
            "status": "ERROR",
            "topic": topic,
            "output": str(e),
            "duration": 0
        }

# ==============================================================================
# 3. GUI (Windows Interface)
# ==============================================================================
class MarinerDesktopGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Project Mariner | Windows Desktop Edition")
        self.root.geometry("900x700")
        
        self.msg_queue = queue.Queue()
        self.results_cache = [] 
        self.topic_list = []
        
        self.setup_ui()
        self.root.after(100, self.process_queue)

    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#2d3436", height=70)
        header.pack(fill=tk.X)
        tk.Label(header, text="PROJECT MARINER", bg="#2d3436", fg="white", font=("Segoe UI", 18, "bold")).pack(pady=15)

        # Settings
        frame_config = ttk.LabelFrame(self.root, text="Configuration")
        frame_config.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(frame_config, text="Gemini API Key:").grid(row=0, column=0, padx=5, pady=5)
        self.ent_key = ttk.Entry(frame_config, width=50, show="*")
        self.ent_key.grid(row=0, column=1, padx=5)

        tk.Label(frame_config, text="Instruction:").grid(row=1, column=0, padx=5, pady=5)
        self.ent_prompt = ttk.Entry(frame_config, width=70)
        self.ent_prompt.insert(0, "Summarize this in 2 sentences.")
        self.ent_prompt.grid(row=1, column=1, padx=5)

        # File Loader
        frame_file = tk.Frame(self.root)
        frame_file.pack(fill=tk.X, padx=10, pady=5)
        self.btn_load = ttk.Button(frame_file, text="📂 Load .txt File", command=self.load_file)
        self.btn_load.pack(side=tk.LEFT)
        self.lbl_status = tk.Label(frame_file, text="No file loaded", fg="gray")
        self.lbl_status.pack(side=tk.LEFT, padx=10)

        # Action Buttons
        frame_action = tk.Frame(self.root)
        frame_action.pack(fill=tk.X, padx=10, pady=10)
        self.btn_run = ttk.Button(frame_action, text="▶ START BATCH", state="disabled", command=self.start_batch)
        self.btn_run.pack(side=tk.LEFT)
        self.btn_save = ttk.Button(frame_action, text="💾 Save Excel", state="disabled", command=self.save_excel)
        self.btn_save.pack(side=tk.LEFT, padx=5)
        
        # Progress
        self.progress = ttk.Progressbar(self.root, length=100, mode='determinate')
        self.progress.pack(fill=tk.X, padx=10, pady=5)

        # Logs
        self.txt_log = scrolledtext.ScrolledText(self.root, height=15, state='disabled', font=("Consolas", 9))
        self.txt_log.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.txt_log.tag_config("SUCCESS", foreground="green")
        self.txt_log.tag_config("ERROR", foreground="red")

    def load_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.topic_list = [line.strip() for line in f if line.strip()]
            self.lbl_status.config(text=f"Loaded {len(self.topic_list)} topics", fg="green")
            self.btn_run.config(state="normal")
            self.log(f"System: Loaded {path}")

    def start_batch(self):
        key = self.ent_key.get().strip()
        prompt = self.ent_prompt.get().strip()
        
        if not key:
            messagebox.showerror("Error", "Please enter API Key")
            return
            
        self.results_cache = [] # Clear old data
        self.btn_run.config(state="disabled")
        self.btn_save.config(state="disabled")
        self.log("--- STARTING MISSION ---")
        
        # Launch Thread
        threading.Thread(target=self.run_process, args=(key, prompt, self.topic_list), daemon=True).start()

    def run_process(self, key, prompt, topics):
        # Prepare Tasks
        tasks = [{'topic': t, 'api_key': key, 'instruction': prompt} for t in topics]
        total = len(tasks)
        
        # Windows Multiprocessing Context
        ctx = multiprocessing.get_context('spawn')
        
        # Use max 3 cores to be safe with rate limits
        try: cores = min(3, multiprocessing.cpu_count())
        except: cores = 2

        with ctx.Pool(processes=cores) as pool:
            for i, result in enumerate(pool.imap_unordered(mariner_probe, tasks)):
                # Save Result
                self.results_cache.append(result)
                
                # Log to GUI
                status = result['status']
                msg = f"[{status}] {result['topic']} ({result['duration']}s)"
                self.queue_put("log", msg, status)
                
                # Update Progress
                pct = ((i + 1) / total) * 100
                self.queue_put("progress", pct)

        self.queue_put("done")

    def save_excel(self):
        if not self.results_cache: return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if path:
            try:
                df = pd.DataFrame(self.results_cache)
                df.to_excel(path, index=False)
                messagebox.showinfo("Success", f"Saved to {path}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # Thread Safety Tools
    def queue_put(self, type, content, tag=None):
        self.msg_queue.put({"type": type, "content": content, "tag": tag})

    def process_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                if msg['type'] == 'log': self.log(msg['content'], msg['tag'])
                elif msg['type'] == 'progress': self.progress['value'] = msg['content']
                elif msg['type'] == 'done':
                    self.btn_run.config(state="normal")
                    self.btn_save.config(state="normal")
                    messagebox.showinfo("Done", "Batch Complete")
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)

    def log(self, text, tag=None):
        self.txt_log.config(state='normal')
        self.txt_log.insert(tk.END, text + "\n", tag)
        self.txt_log.see(tk.END)
        self.txt_log.config(state='disabled')

# ==============================================================================
# 4. ENTRY POINT (REQUIRED FOR WINDOWS)
# ==============================================================================
if __name__ == "__main__":
    multiprocessing.freeze_support()
    
    # Hide console if needed (Optional)
    # sys.stdout = open(os.devnull, 'w') 
    
    try:
        root = tk.Tk()
        app = MarinerDesktopGUI(root)
        root.mainloop()
    except Exception as e:
        print(f"Critical Error: {e}")
        input("Press Enter to Exit...")