import sys
import os
import subprocess
import importlib
import time
import random
import threading
import multiprocessing
import queue
import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

# ==============================================================================
# 1. SELF-HEALING DEPENDENCY INSTALLER (Runs first)
# ==============================================================================
def check_and_install_packages():
    """
    Scans for required libraries. If missing, installs them to the user's 
    local folder (Bypassing Admin Rights).
    """
    # Format: ("pip-name", "import-name")
    required = [
        ("pandas", "pandas"), 
        ("requests", "requests"),
        ("openpyxl", "openpyxl") 
    ]

    # Skip installation if running as a compiled EXE (dependencies are already inside)
    if getattr(sys, 'frozen', False):
        return

    for package, import_name in required:
        try:
            importlib.import_module(import_name)
        except ImportError:
            print(f"[*] Installing missing library: {package}...")
            try:
                # --user flag is CRITICAL for non-admin installation
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", 
                    "--user", package, 
                    "--quiet", "--disable-pip-version-check"
                ])
                print(f"[+] {package} installed successfully.")
            except subprocess.CalledProcessError:
                print(f"[!] Could not install {package}. Check internet connection.")

# Run the check immediately
check_and_install_packages()

# Now it is safe to import them
import pandas as pd
import requests

# ==============================================================================
# 2. WORKER PROCESS (The "Heavy Lifter")
# ==============================================================================
def parallel_worker(task_data):
    """
    This function runs on a separate CPU core.
    It performs the heavy automation tasks (scraping, data processing, etc).
    """
    task_id = task_data['id']
    target = task_data['target']
    
    start_time = time.time()
    result_status = "SUCCESS"
    log_message = ""

    try:
        # --- YOUR AUTOMATION LOGIC STARTS HERE ---
        
        # Simulate heavy processing (Replace this with your real code)
        simulation_time = random.uniform(0.5, 2.0)
        time.sleep(simulation_time)
        
        # Simulate a random crash to test robustness
        if random.random() < 0.05: 
            raise ConnectionError("Simulated Network Timeout")
            
        # Example Data Processing using Pandas
        df = pd.DataFrame({'Data': [1, 2, 3]})
        processed_val = df.sum() * task_id
        
        log_message = f"Processed {target} | Val: {processed_val}"
        
        # --- YOUR AUTOMATION LOGIC ENDS HERE ---

    except Exception as e:
        result_status = "ERROR"
        log_message = str(e)

    # Return result dict to Main GUI
    return {
        "id": task_id,
        "status": result_status,
        "msg": log_message,
        "duration": round(time.time() - start_time, 2)
    }

# ==============================================================================
# 3. GRAPHICAL USER INTERFACE (The Controller)
# ==============================================================================
class AutomationBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Python Parallel Automation (No-Admin)")
        self.root.geometry("800x600")
        
        # Communication Queue (Thread-Safe)
        self.msg_queue = queue.Queue()
        
        self.setup_ui()
        
        # Start checking the queue for updates
        self.root.after(100, self.process_queue)

    def setup_ui(self):
        # -- Styles --
        style = ttk.Style()
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("TLabel", font=("Segoe UI", 10))
        
        # -- Header --
        header_frame = tk.Frame(self.root, bg="#2d3436", height=60)
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text="AutoBot Pro v1.0", bg="#2d3436", fg="white", 
                 font=("Segoe UI", 16, "bold")).pack(pady=15)

        # -- Control Area --
        control_frame = tk.Frame(self.root, pady=10)
        control_frame.pack(fill=tk.X, padx=10)
        
        self.btn_run = ttk.Button(control_frame, text="▶ START BATCH", command=self.run_automation)
        self.btn_run.pack(side=tk.LEFT, padx=5)
        
        self.lbl_status = ttk.Label(control_frame, text="Status: Ready", foreground="blue")
        self.lbl_status.pack(side=tk.LEFT, padx=15)

        # -- Progress Bar --
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.root, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=10, pady=5)

        # -- Log Window --
        log_frame = ttk.LabelFrame(self.root, text="Live Execution Logs")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, height=10, state='disabled', font=("Consolas", 9))
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tag configs for colored logs
        self.log_area.tag_config("INFO", foreground="black")
        self.log_area.tag_config("SUCCESS", foreground="green")
        self.log_area.tag_config("ERROR", foreground="red")

    def run_automation(self):
        """Prepares data and launches the separate thread"""
        self.btn_run.config(state="disabled")
        self.log_area.config(state='normal')
        self.log_area.delete(1.0, tk.END) # Clear logs
        self.log_area.config(state='disabled')
        
        self.log("Initializing Batch Process...", "INFO")
        
        # Run the heavy coordinator in a thread so GUI doesn't freeze
        threading.Thread(target=self.coordinator_thread, daemon=True).start()

    def coordinator_thread(self):
        """
        Runs in a background THREAD.
        It manages the Multiprocessing POOL.
        """
        # 1. Define Work (Fixed Syntax Error Here)
        # We create a list of 50 dummy tasks
        tasks = [{'id': i, 'target': f'Item-{i}'} for i in range(1, 51)]
        
        total_tasks = len(tasks)
        
        # 2. Setup Pool
        # Use (CPU_COUNT - 1) to leave one core free for the OS
        try:
            cpu_cores = max(1, multiprocessing.cpu_count() - 1)
        except:
            cpu_cores = 2 # Fallback
            
        self.queue_put("log", f"Spawning {cpu_cores} parallel worker processes...", "INFO")
        
        results_success = 0
        results_error = 0
        
        # 3. Execute in Parallel
        # 'spawn' is safer for Windows GUIs
        ctx = multiprocessing.get_context('spawn')
        
        try:
            with ctx.Pool(processes=cpu_cores) as pool:
                # imap_unordered yields results as soon as they finish
                for i, result in enumerate(pool.imap_unordered(parallel_worker, tasks)):
                    
                    # Process Result
                    if result['status'] == "SUCCESS":
                        results_success += 1
                        log_tag = "SUCCESS"
                        msg = f"Task {result['id']} OK: {result['msg']} ({result['duration']}s)"
                    else:
                        results_error += 1
                        log_tag = "ERROR"
                        msg = f"Task {result['id']} FAILED: {result['msg']}"
                    
                    # Update GUI via Queue
                    self.queue_put("log", msg, log_tag)
                    
                    # Update Progress
                    progress = ((i + 1) / total_tasks) * 100
                    self.queue_put("progress", progress)

        except Exception as e:
            self.queue_put("log", f"CRITICAL POOL ERROR: {e}", "ERROR")

        # 4. Finish
        self.queue_put("log", f"--- Batch Complete. Success: {results_success} | Errors: {results_error} ---", "INFO")
        self.queue_put("done")

    # --- Queue Handling (Thread Safety) ---
    def queue_put(self, msg_type, content=None, tag=None):
        self.msg_queue.put({"type": msg_type, "content": content, "tag": tag})

    def process_queue(self):
        """Polls queue for messages from background thread"""
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                
                if msg['type'] == 'log':
                    self.log(msg['content'], msg['tag'])
                
                elif msg['type'] == 'progress':
                    self.progress_var.set(msg['content'])
                
                elif msg['type'] == 'done':
                    self.btn_run.config(state="normal")
                    self.lbl_status.config(text="Status: Completed")
                    messagebox.showinfo("Done", "Automation Batch Finished")
                    
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue) # Check again in 100ms

    def log(self, message, tag):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S ")
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, timestamp + message + "\n", tag)
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

# ==============================================================================
# 4. ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    # REQUIRED for PyInstaller/Windows Multiprocessing
    multiprocessing.freeze_support()
    
    try:
        root = tk.Tk()
        app = AutomationBotGUI(root)
        root.mainloop()
    except Exception as e:
        # Last resort crash logger
        with open("crash_log.txt", "w") as f:
            f.write(f"Critical Startup Error: {e}")