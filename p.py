"""
==============================================================================
MAMA'S CAE BACKUP TOOL - PROFESSIONAL EDITION
==============================================================================
Includes Categories:
1. Security (Env Vars)    5. Logging (Rotating & Colors)
2. Robustness (Retries)   6. Code Quality (Type Hints, Docstrings)
4. Configuration (JSON)   7. Features (Dry Run)
                          8. File Handling (Recursive)
==============================================================================
"""

import os
import sys
import json
import time
import subprocess
import argparse
import logging
from logging.handlers import RotatingFileHandler
from typing import List, Optional

# --- AUTO-INSTALLER (Robustness) ---
def install_and_import(package_name: str, import_name: str):
    try:
        __import__(import_name)
    except ImportError:
        print(f"⚙️  Installing missing library: {package_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])

install_and_import("PyGithub", "github")
install_and_import("python-dotenv", "dotenv")
install_and_import("colorama", "colorama")
install_and_import("plyer", "plyer")

from github import Github, GithubException
from dotenv import load_dotenv
from colorama import Fore, Style, init
from plyer import notification

# Initialize Colors
init(autoreset=True)

# --- CATEGORY 4: CONFIGURATION LOAD ---
def load_config():
    if not os.path.exists("config.json"):
        print(Fore.RED + "❌ Error: config.json not found.")
        sys.exit(1)
    with open("config.json", "r") as f:
        return json.load(f)

CONFIG = load_config()

# --- CATEGORY 1: SECURITY (Load Token from .env) ---
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    print(Fore.RED + "❌ CRITICAL: GITHUB_TOKEN not found in .env file.")
    sys.exit(1)

# --- CATEGORY 5: LOGGING SETUP (Rotating) ---
LOG_FILE = "backup_history.log"
logger = logging.getLogger("BackupLogger")
logger.setLevel(logging.INFO)
# Rotate log after 5MB, keep 3 backup files
handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# --- CATEGORY 2: ROBUSTNESS (Retry Decorator) ---
def retry_operation(max_attempts: int = 3, delay: int = 2):
    """Decorator to retry a function if it fails (Network glitches)."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    logger.warning(f"Attempt {attempts} failed: {e}")
                    print(Fore.YELLOW + f"⚠️  Retry {attempts}/{max_attempts}...")
                    time.sleep(delay)
            logger.error(f"Operation failed after {max_attempts} attempts.")
            raise Exception("Max retries exceeded")
        return wrapper
    return decorator

# --- CORE FUNCTIONS ---

def check_internet() -> bool:
    """Category 2: Network Check."""
    try:
        # Check connection to GitHub API
        subprocess.check_call(["ping", "-n", "1", "api.github.com"], stdout=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

@retry_operation(max_attempts=CONFIG["max_retries"])
def upload_file(repo, local_path: str, github_path: str, dry_run: bool):
    """Category 8: Handles file uploads with retries."""
    
    if dry_run:
        print(Fore.CYAN + f"   [DRY RUN] Would upload: {github_path}")
        return True

    with open(local_path, "rb") as f:
        content = f.read()

    try:
        contents = repo.get_contents(github_path)
        # Category 3 (Optimization): Only update if content is different? (Simplified here)
        repo.update_file(contents.path, f"Update {github_path}", content, contents.sha)
        print(Fore.GREEN + f"   ✅ Updated: {github_path}")
        logger.info(f"Updated file: {github_path}")
    except GithubException:
        repo.create_file(github_path, f"Create {github_path}", content)
        print(Fore.GREEN + f"   ✅ Created: {github_path}")
        logger.info(f"Created file: {github_path}")

def main():
    # --- CATEGORY 7: FEATURES (Argparse for Dry Run) ---
    parser = argparse.ArgumentParser(description="Professional GitHub Backup Tool")
    parser.add_argument("--dry-run", action="store_true", help="Simulate backup without uploading")
    args = parser.parse_args()

    print(Style.BRIGHT + Fore.WHITE + "="*50)
    print(Style.BRIGHT + Fore.BLUE + "      🛡️  PROFESSIONAL CAE BACKUP SYSTEM  🛡️")
    print(Style.BRIGHT + Fore.WHITE + "="*50)

    if args.dry_run:
        print(Fore.CYAN + "🧪 DRY RUN MODE ENABLED (No changes will be made)")

    # 1. Network Check
    if not check_internet():
        print(Fore.RED + "❌ No Internet Connection. Aborting.")
        logger.error("Backup aborted: No internet.")
        return

    # 2. Connect
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(CONFIG["repo_name"])
        print(Fore.BLUE + f"🔒 Connected to: {CONFIG['repo_name']}")
    except Exception as e:
        print(Fore.RED + f"❌ Auth Failed: {e}")
        return

    # 3. Recursive Scan
    source_folder = CONFIG["source_folder"]
    if not os.path.exists(source_folder):
        print(Fore.RED + f"❌ Source folder not found: {source_folder}")
        return

    count_success = 0
    count_errors = 0

    for root, dirs, files in os.walk(source_folder):
        # Ignore folders
        dirs[:] = [d for d in dirs if d not in CONFIG["ignore_folders"]]

        for file_name in files:
            full_path = os.path.join(root, file_name)
            _, ext = os.path.splitext(file_name)

            # Category 8: Extension Filter
            if ext.lower() not in CONFIG["allowed_extensions"]:
                continue

            # Calculate GitHub Path
            rel_path = os.path.relpath(full_path, source_folder)
            github_path = rel_path.replace("\\", "/")

            print(f"⬆️  Processing: {github_path}...", end=" ")

            try:
                upload_file(repo, full_path, github_path, args.dry_run)
                count_success += 1
            except Exception as e:
                print(Fore.RED + f"\n❌ Failed: {e}")
                logger.error(f"Failed to upload {github_path}: {e}")
                count_errors += 1

    # Final Report
    print("-" * 50)
    summary = f"Run Complete. Success: {count_success} | Errors: {count_errors}"
    print(Style.BRIGHT + Fore.WHITE + summary)
    
    if not args.dry_run:
        try:
            notification.notify(
                title='CAE Backup Pro',
                message=summary,
                timeout=5
            )
        except:
            pass

if __name__ == "__main__":
    main()
    if sys.platform == "win32":
        input("Press Enter to exit...")