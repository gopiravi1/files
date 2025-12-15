#!/usr/bin/env python3
"""
FEA Comparator: All-Pairs Combination (N-to-N)
==============================================
1. Finds ALL files matching the pattern.
2. Generates every possible unique combination of files.
3. Compares Thickness (Deep Search) for every pair.
"""

import os
import re
import glob
import itertools
from multiprocessing import Pool, cpu_count

# -------------------------
# Configuration
# -------------------------
CONFIG = {
    "INPUT_DIR": "E:\\USERS\\Gopi_AIML\\Slate_Model_Files\\KFiless",
    "OUTPUT_DIR": "E:\\USERS\\Gopi_AIML\\Slate_Model_Files\\KFiless_out",
    
    # Pattern to find ALL design files
    "FILE_PATTERN": "Design_*.dyn",
    
    # Tolerance for reporting differences
    "TOLERANCE": 0.001  
}

def safe_float(s):
    try: return float(s)
    except: return 0.0

def get_numeric_line(line):
    """Returns a list of integers if line contains PID/SECID pattern."""
    if '$' in line: line = line.split('$')[0]
    tokens = re.split(r'[,\s]+', line.strip())
    tokens = [t for t in tokens if t]
    
    if len(tokens) >= 2:
        if tokens[0].isdigit() and tokens[1].isdigit():
            return int(tokens[0]), int(tokens[1])
    return None

def parse_deep_search(filepath):
    """
    Robust Parser: Scans for *PART and *SECTION to map PID -> Thickness.
    """
    data = {
        "parts": {},      # {pid: {'name': str, 'secid': int, 'value': 0.0}}
        "sections": {}    # {secid: value}
    }
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    n = len(lines)
    
    for i, line in enumerate(lines):
        line_strip = line.strip()
        if not line_strip or line_strip.startswith('$'): continue
        
        if line_strip.startswith('*'):
            keyword = line_strip.split()[0].upper()
            
            # --- PARSE PART ---
            if keyword.startswith('*PART'):
                found_pid = None
                found_secid = None
                part_name = "Unknown"

                # Look ahead 4 lines for ID pattern
                for offset in range(1, 5):
                    if i + offset >= n: break
                    look_line = lines[i+offset].strip()
                    
                    if look_line.startswith('*'): break
                    if look_line.startswith('$'): continue
                    
                    ids = get_numeric_line(look_line)
                    if ids:
                        found_pid, found_secid = ids
                        if offset > 1:
                            prev_line = lines[i+offset-1].strip()
                            if not prev_line.startswith('$'):
                                part_name = prev_line
                        break
                    elif offset == 1:
                        part_name = look_line

                if found_pid is not None:
                    data["parts"][found_pid] = {'name': part_name, 'secid': found_secid, 'value': 0.0}

            # --- PARSE SHELL SECTION ---
            elif keyword.startswith('*SECTION_SHELL'):
                for offset in range(1, 5):
                    if i + offset >= n: break
                    l = lines[i+offset].strip()
                    if l.startswith('*'): break
                    if l.startswith('$'): continue
                    
                    tokens = re.split(r'[,\s]+', l)
                    if tokens and tokens[0].isdigit():
                        secid = int(tokens[0])
                        # Look for next data line (Thickness)
                        next_data_idx = i + offset + 1
                        while next_data_idx < n:
                            nl = lines[next_data_idx].strip()
                            if nl.startswith('*'): break
                            if not nl or nl.startswith('$'): 
                                next_data_idx += 1
                                continue
                            
                            tok2 = re.split(r'[,\s]+', nl)
                            if tok2:
                                val = safe_float(tok2[0])
                                data["sections"][secid] = val
                            break
                        break

            # --- PARSE BEAM SECTION ---
            elif keyword.startswith('*SECTION_BEAM'):
                for offset in range(1, 5):
                    if i + offset >= n: break
                    l = lines[i+offset].strip()
                    if l.startswith('*'): break
                    if l.startswith('$'): continue
                    
                    tokens = re.split(r'[,\s]+', l)
                    if tokens and tokens[0].isdigit():
                        secid = int(tokens[0])
                        next_data_idx = i + offset + 1
                        while next_data_idx < n:
                            nl = lines[next_data_idx].strip()
                            if nl.startswith('*'): break
                            if not nl or nl.startswith('$'): 
                                next_data_idx += 1
                                continue
                            tok2 = re.split(r'[,\s]+', nl)
                            if tok2:
                                val = safe_float(tok2[0])
                                data["sections"][secid] = val
                            break
                        break

    # Link Sections to Parts
    for pid, p in data["parts"].items():
        sid = p['secid']
        if sid in data["sections"]:
            p['value'] = data["sections"][sid]
            
    return data

def worker(fpath):
    try:
        return (fpath, parse_deep_search(fpath))
    except Exception as e:
        print(f"Error parsing {fpath}: {e}")
        return (fpath, None)

def main():
    if not os.path.exists(CONFIG["OUTPUT_DIR"]): os.makedirs(CONFIG["OUTPUT_DIR"])
    
    # 1. Identify all Design Files
    search_path = os.path.join(CONFIG["INPUT_DIR"], CONFIG["FILE_PATTERN"])
    all_files = sorted(glob.glob(search_path))
    
    num_files = len(all_files)
    if num_files < 2:
        print(f"Not enough files to compare. Found: {num_files}")
        return

    # 2. Parse ALL files first (Parallel)
    print(f"--- Parsing {num_files} Files ---")
    with Pool(cpu_count()) as p:
        results = dict(p.map(worker, all_files))

    # 3. Generate Max Combinations (nC2)
    # itertools.combinations('ABCD', 2) --> AB AC AD BC BD CD
    file_combinations = list(itertools.combinations(all_files, 2))
    print(f"--- Generated {len(file_combinations)} unique comparison pairs ---")

    # 4. Run Comparisons
    print("\n--- PROCESSING COMBINATIONS ---")
    
    diff_count = 0
    
    for file_a, file_b in file_combinations:
        name_a = os.path.basename(file_a)
        name_b = os.path.basename(file_b)
        
        data_a = results.get(file_a)
        data_b = results.get(file_b)
        
        if not data_a or not data_b: continue
        
        # Find Changes
        changes = []
        common_pids = set(data_a["parts"].keys()) & set(data_b["parts"].keys())
        
        for pid in common_pids:
            val_a = data_a["parts"][pid]['value']
            val_b = data_b["parts"][pid]['value']
            
            if abs(val_a - val_b) > CONFIG["TOLERANCE"]:
                if val_a > 0 or val_b > 0:
                    part_name = data_a["parts"][pid]['name']
                    changes.append((pid, part_name, val_a, val_b))
        
        # Report if changes found
        if changes:
            diff_count += 1
            print(f"\n[!] CHANGE DETECTED: {name_a} vs {name_b}")
            print(f"    {'PID':<10} {'Val_A':<8} {'Val_B':<8} {'Delta':<8} {'Name'}")
            print(f"    {'-'*60}")
            
            for pid, name, va, vb in changes:
                delta = vb - va
                print(f"    {pid:<10} {va:<8.3f} {vb:<8.3f} {delta:<8.3f} {name[:30]}")
            
            # Save Pairwise Report
            out_name = f"Diff_{name_a}_VS_{name_b}.csv"
            out_path = os.path.join(CONFIG["OUTPUT_DIR"], out_name)
            with open(out_path, 'w') as f:
                f.write(f"Comparison,{name_a},{name_b}\n")
                f.write("PID,PartName,Value_A,Value_B,Delta\n")
                for pid, name, va, vb in changes:
                    f.write(f"{pid},{name},{va},{vb},{vb-va}\n")
    
    print("\n" + "="*40)
    print(f"Done. Found differences in {diff_count} of {len(file_combinations)} pairs.")
    print("="*40)

if __name__ == "__main__":
    main()