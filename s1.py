#!/usr/bin/env python3
import os
import re
import glob

# -------------------------
# Configuration
# -------------------------
CONFIG = {
    "INPUT_DIR": r"E:\USERS\Gopi_AIML\Slate_Model_Files\KFiless",
    "OUTPUT_DIR": r"E:\USERS\Gopi_AIML\Slate_Model_Files\KFiless_out",
    "FILE_PATTERN": "*.dyn"
}

# -------------------------
# Robust Helpers
# -------------------------
def safe_int(value):
    """
    Safely converts a string to an integer.
    Returns None if the value is not a valid number (e.g., 'mm', 'Part', etc.)
    """
    try:
        # Check if it's a clean digit string
        s = value.strip()
        if s.isdigit():
            return int(s)
        # Handle cases like "1.0" or weird formatting
        f = float(s)
        if f.is_integer():
            return int(f)
    except:
        return None
    return None

def is_odd(n):
    return n % 2 != 0

def extract_odd_components(input_file, output_file):
    print(f"Processing: {os.path.basename(input_file)}...")
    
    keep_pids = set()
    keep_sec_ids = set()
    keep_mat_ids = set()
    keep_node_ids = set()
    
    # Read file safely
    try:
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"  [ERR] Could not read file {input_file}: {e}")
        return
        
    n = len(lines)

    # --- PASS 1: Identify Odd Parts & Related Properties (Sec/Mat) ---
    # We look for *PART, then read the PID, SECID, MID from the next line
    i = 0
    while i < n:
        line = lines[i].strip()
        if line.startswith('*PART'):
            # Scan ahead 1-4 lines to find the data line (skipping $comments)
            for offset in range(1, 5):
                if i + offset >= n: break
                look = lines[i+offset].strip()
                if look.startswith('*'): break
                if look.startswith('$'): continue
                
                # Tokenize
                tokens = re.split(r'[,\s]+', look)
                if len(tokens) >= 1:
                    pid = safe_int(tokens[0])
                    
                    if pid is not None and is_odd(pid):
                        keep_pids.add(pid)
                        
                        # Extract SECID (Index 1) and MID (Index 2) if available
                        # Standard PART format: PID, SECID, MID, ...
                        if len(tokens) > 1:
                            sid = safe_int(tokens[1])
                            if sid is not None: keep_sec_ids.add(sid)
                        
                        if len(tokens) > 2:
                            mid = safe_int(tokens[2])
                            if mid is not None: keep_mat_ids.add(mid)
                break
        i += 1

    print(f"  -> Found {len(keep_pids)} Odd PIDs.")
    if not keep_pids:
        print("  -> Skipping (No odd parts found).")
        return

    # --- PASS 2: Find Elements & Nodes linked to these PIDs ---
    # Keywords for elements (Expanded to include Discrete and Mass)
    element_keywords = (
        '*ELEMENT_SHELL', '*ELEMENT_SOLID', '*ELEMENT_BEAM', 
        '*ELEMENT_TSHELL', '*ELEMENT_DISCRETE', '*ELEMENT_MASS'
    )
    
    i = 0
    while i < n:
        line = lines[i].strip()
        if line.startswith(element_keywords):
            # Process this element block
            j = i + 1
            while j < n:
                el_line = lines[j].strip()
                if el_line.startswith('*'): break
                if el_line.startswith('$'): 
                    j += 1; continue
                
                tokens = re.split(r'[,\s]+', el_line)
                
                if len(tokens) > 2:
                    pid = safe_int(tokens[1])
                    
                    if pid is not None and pid in keep_pids:
                        # Standard Elements start nodes at index 2
                        start_index = 2
                        
                        # Adjust for MASS elements (EID, NID, MASS, PID)
                        # Note: Mass elements are tricky, PID is usually 3rd or 4th token depending on format.
                        # For robustness with MASS linked to PIDs, we assume standard index 1 is PID or NID.
                        # If the line is *ELEMENT_MASS, token[1] is NID usually.
                        
                        if line.startswith('*ELEMENT_MASS'):
                            # For Mass, if we found it via PID (rarely stored in line), keep node.
                            # But usually Mass is kept if Node is kept. 
                            # Here we just scan for PIDs in standard elements to build the Node List first.
                            pass 
                        else:
                            for t in tokens[start_index:]:
                                nid = safe_int(t)
                                if nid is not None:
                                    keep_node_ids.add(nid)
                j += 1
            i = j
            continue
        i += 1
        
    print(f"  -> Identified {len(keep_node_ids)} related Nodes.")
    print(f"  -> Identified {len(keep_sec_ids)} related Sections.")
    print(f"  -> Identified {len(keep_mat_ids)} related Materials.")

    # --- PASS 3: Write Output File ---
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write("*KEYWORD\n")
        out.write(f"$ Extracted Odd Components from {os.path.basename(input_file)}\n")
        out.write(f"$ Proper DYNA File for Visualization\n")
        
        i = 0
        while i < n:
            line = lines[i]
            line_strip = line.strip()
            
            # 1. Handle NODES
            if line_strip.startswith('*NODE'):
                out.write(line) 
                j = i + 1
                while j < n:
                    node_line = lines[j]
                    if node_line.strip().startswith('*'): break
                    
                    # Preserve Comments
                    if node_line.strip().startswith('$'): 
                        out.write(node_line)
                        j += 1; continue
                    
                    tokens = re.split(r'[,\s]+', node_line.strip())
                    if tokens:
                        nid = safe_int(tokens[0])
                        if nid is not None and nid in keep_node_ids:
                            out.write(node_line)
                    j += 1
                i = j
                continue

            # 2. Handle ELEMENTS (Standard)
            elif line_strip.startswith(element_keywords) and not line_strip.startswith('*ELEMENT_MASS'):
                out.write(line)
                j = i + 1
                while j < n:
                    el_line = lines[j]
                    if el_line.strip().startswith('*'): break
                    if el_line.strip().startswith('$'): 
                         out.write(el_line)
                         j += 1; continue
                    
                    tokens = re.split(r'[,\s]+', el_line.strip())
                    if len(tokens) > 2:
                        pid = safe_int(tokens[1])
                        if pid is not None and pid in keep_pids:
                            out.write(el_line)
                    j += 1
                i = j
                continue

            # 3. Handle MASS ELEMENTS (Keep if attached to kept Node)
            elif line_strip.startswith('*ELEMENT_MASS'):
                out.write(line)
                j = i + 1
                while j < n:
                    el_line = lines[j]
                    if el_line.strip().startswith('*'): break
                    if el_line.strip().startswith('$'):
                        out.write(el_line)
                        j += 1; continue

                    tokens = re.split(r'[,\s]+', el_line.strip())
                    if len(tokens) > 1:
                        nid = safe_int(tokens[1])
                        if nid is not None and nid in keep_node_ids:
                            out.write(el_line)
                    j += 1
                i = j
                continue

            # 4. Handle PARTS
            elif line_strip.startswith('*PART'):
                buffer_block = [line]
                is_target_part = False
                
                j = i + 1
                while j < n:
                    p_line = lines[j]
                    if p_line.strip().startswith('*'): break
                    buffer_block.append(p_line)
                    
                    if not p_line.strip().startswith('$') and not is_target_part:
                        tokens = re.split(r'[,\s]+', p_line.strip())
                        if tokens:
                            pid = safe_int(tokens[0])
                            if pid is not None and pid in keep_pids:
                                is_target_part = True
                    j += 1
                
                if is_target_part:
                    for b in buffer_block: out.write(b)
                i = j 
                continue

            # 5. Handle SECTIONS (Filtered by ID)
            elif line_strip.startswith(('*SECTION_SHELL', '*SECTION_BEAM', '*SECTION_SOLID', '*SECTION_DISCRETE')):
                # Buffer to check ID
                buffer_block = [line]
                is_target_sec = False
                
                j = i + 1
                while j < n:
                    s_line = lines[j]
                    if s_line.strip().startswith('*'): break
                    buffer_block.append(s_line)
                    
                    if not s_line.strip().startswith('$') and not is_target_sec:
                        tokens = re.split(r'[,\s]+', s_line.strip())
                        if tokens:
                            # SECID is usually the first token
                            sid = safe_int(tokens[0])
                            if sid is not None and sid in keep_sec_ids:
                                is_target_sec = True
                    j += 1
                
                if is_target_sec:
                    for b in buffer_block: out.write(b)
                i = j
                continue

            # 6. Handle MATERIALS (Filtered by ID)
            elif line_strip.startswith('*MAT_'):
                # Buffer to check ID
                buffer_block = [line]
                is_target_mat = False
                
                j = i + 1
                while j < n:
                    m_line = lines[j]
                    if m_line.strip().startswith('*'): break
                    buffer_block.append(m_line)
                    
                    if not m_line.strip().startswith('$') and not is_target_mat:
                        tokens = re.split(r'[,\s]+', m_line.strip())
                        if tokens:
                            # MID is usually the first token
                            mid = safe_int(tokens[0])
                            if mid is not None and mid in keep_mat_ids:
                                is_target_mat = True
                    j += 1
                
                if is_target_mat:
                    for b in buffer_block: out.write(b)
                i = j
                continue
            
            # Skip everything else
            else:
                i += 1

        out.write("*END\n")
    print(f"  [OK] Saved: {os.path.basename(output_file)}")

def main():
    # Use raw string literals (r"") for Windows paths to avoid escape sequence issues
    if not os.path.exists(CONFIG["OUTPUT_DIR"]):
        try:
            os.makedirs(CONFIG["OUTPUT_DIR"])
        except OSError as e:
            print(f"[ERROR] Could not create output dir: {e}")
            return
    
    # Check input
    if not os.path.exists(CONFIG["INPUT_DIR"]):
        print(f"[ERROR] Input directory not found: {CONFIG['INPUT_DIR']}")
        print("Please check the path.")
        return

    search_path = os.path.join(CONFIG["INPUT_DIR"], CONFIG["FILE_PATTERN"])
    files = sorted(glob.glob(search_path))
    
    if not files:
        print(f"[ERROR] No matching files found in: {CONFIG['INPUT_DIR']}")
        return

    print(f"--- Segregating Odd Components from {len(files)} files ---")
    
    for f in files:
        try:
            fname = os.path.basename(f)
            out_name = f"Odd_Comps_{fname}"
            out_path = os.path.join(CONFIG["OUTPUT_DIR"], out_name)
            extract_odd_components(f, out_path)
        except Exception as e:
            print(f"  [ERR] General Failure on {f}: {e}")

    print("\nExtraction Complete.")

if __name__ == "__main__":
    main()