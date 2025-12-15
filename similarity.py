import os
import glob
import math
import re
import logging
from collections import defaultdict

# Configure logging to show progress
logging.basicConfig(level=logging.INFO, format='%(message)s')

try:
    # We use qd-cae because it handles includes and parses mesh data accurately
    from qd.cae.dyna import KeyFile
except ImportError:
    print("CRITICAL ERROR: The 'qd' library is missing.")
    print("Please install it by running: pip install qd")
    exit(1)

class DynaSimilarityEngine:
    def __init__(self, reference_file):
        """
        Initialize with the baseline design file (e.g., design_1.k).
        """
        self.ref_path = reference_file
        logging.info(f"LOADING REFERENCE: {os.path.basename(reference_file)}...")
        
        # load_includes=True ensures we compare the full assembly, not just the wrapper file.
        # parse_mesh=True allows us to detect changes in node coordinates/element connectivity.
        try:
            self.ref_kf = KeyFile(reference_file, load_includes=True, parse_mesh=True)
            self.ref_data = self._canonicalize(self.ref_kf)
            self.ref_keywords = set(self.ref_data.keys())
        except Exception as e:
            logging.error(f"Failed to load reference file: {e}")
            raise
        
        logging.info(f"Reference loaded. Found {len(self.ref_keywords)} unique keyword types.")

    def _canonicalize(self, keyfile):
        """
        Converts the KeyFile object into a normalized dictionary for accurate comparison.
        Structure: { Keyword_Name : { ID : { Field_Name : Value } } }
        """
        data = defaultdict(dict)
        
        # Iterate over all keywords in the deck
        for kw in keyfile.keywords:
            kw_name = kw.get_keyword_name()
            
            # Determine a unique identifier for the card (ID, PID, MID, etc.)
            # If no ID exists (e.g., *CONTROL_TERMINATION), use "Global"
            card_id = "Global"
            id_fields = ['id', 'pid', 'mid', 'secid', 'eid', 'nid']
            for field in id_fields:
                if field in kw.field_names:
                    card_id = kw[field]
                    break
            
            # Extract and normalize fields
            fields = {}
            for name in kw.field_names:
                raw_val = kw[name]
                
                # ACCURACY LAYER: Normalize values to ignore formatting noise
                if isinstance(raw_val, float):
                    # Round to 6 decimals to treat 1.0000001 and 1.0 as identical
                    val = round(raw_val, 6) 
                elif isinstance(raw_val, str):
                    # Strip whitespace to treat "MAT1" and "MAT1    " as identical
                    val = raw_val.strip()
                else:
                    val = raw_val
                
                fields[name] = val
            
            # Handle duplicate IDs (last one wins, consistent with LS-DYNA behavior)
            data[kw_name][card_id] = fields
            
        return data

    def calculate_score(self, target_file):
        """
        Compares a target file against the reference and returns a similarity score (0.0 to 1.0).
        """
        logging.info(f"  -> Comparing against: {os.path.basename(target_file)}")
        try:
            tgt_kf = KeyFile(target_file, load_includes=True, parse_mesh=True)
            tgt_data = self._canonicalize(tgt_kf)
            tgt_keywords = set(tgt_data.keys())
        except Exception as e:
            logging.error(f"Failed to parse {target_file}: {e}")
            return 0.0

        # 1. Structural Similarity (Jaccard Index of Keywords)
        intersection = self.ref_keywords.intersection(tgt_keywords)
        union = self.ref_keywords.union(tgt_keywords)
        struct_score = len(intersection) / len(union) if union else 0.0

        # 2. Parametric Similarity (Field-by-Field Check)
        total_fields = 0
        matching_fields = 0

        # Only compare keywords that exist in both files
        for kw in intersection:
            ref_cards = self.ref_data[kw]
            tgt_cards = tgt_data[kw]
            
            # Compare cards with matching IDs
            common_ids = set(ref_cards.keys()).intersection(tgt_cards.keys())
            
            for cid in common_ids:
                ref_vals = ref_cards[cid]
                tgt_vals = tgt_cards[cid]
                
                for field, r_val in ref_vals.items():
                    total_fields += 1
                    t_val = tgt_vals.get(field)
                    
                    # Exact match check (using normalized values)
                    if r_val == t_val:
                        matching_fields += 1
                    # Fallback for close floats (physics tolerance)
                    elif isinstance(r_val, float) and isinstance(t_val, float):
                        if math.isclose(r_val, t_val, rel_tol=1e-5):
                            matching_fields += 1
        
        param_score = matching_fields / total_fields if total_fields > 0 else 0.0

        # 3. Weighted Hybrid Similarity Score (WHSS)
        # Structure weight: 20%, Parameter weight: 80%
        final_score = (0.2 * struct_score) + (0.8 * param_score)
        
        return round(final_score * 100, 2)

def natural_sort_key(s):
    """
    Sorts strings with embedded numbers naturally (e.g. design_2 comes before design_10).
    """
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split('([0-9]+)', s)]

def main():
    # SETTINGS: Current directory - NOTE: The path uses Windows backslashes,
    # which can sometimes cause issues. Using raw string (r"...") is safer.
    work_dir = r"E:\USERS\Gopi_AIML\Slate_Model_Files\KFiless" 
    extensions = ['*.k', '*.dyn', '*.key']
    
    # 1. Discover Files
    files = [] # FIX 1: Initialize the list correctly
    for ext in extensions:
        # Recursive glob in case designs are in subfolders
        # Looking for files named 'design_*.k' etc.
        files.extend(glob.glob(os.path.join(work_dir, "**", f"design_{ext}"), recursive=True))
    
    # Deduplicate and Sort naturally so design_1 is the reference
    files = sorted(list(set(files)), key=natural_sort_key)
    
    if len(files) < 2:
        print(f"Error: Found only {len(files)} files matching 'design_*' in {work_dir}. Need at least 2 to perform comparison.")
        return

    # 2. Initialize Engine with the first file as Baseline
    reference_file = files[0] # FIX 2: Use the first element of the sorted list as reference
    try:
        engine = DynaSimilarityEngine(reference_file)
    except Exception:
        print("Aborting due to reference file error.")
        return
    
    # 3. Process Batch
    print(f"\n{'='*60}")
    print(f"LS-DYNA SIMILARITY REPORT")
    print(f"Reference Model: {os.path.basename(reference_file)}")
    print(f"{'='*60}")
    print(f"{'Design Variant':<30} | {'Similarity Score':<15}")
    print(f"{'-'*30} | {'-'*15}")
    
    # Print baseline (100% match)
    print(f"{os.path.basename(reference_file):<30} | 100.00%")
    
    # Compare others
    for target in files[1:]:
        score = engine.calculate_score(target)
        print(f"{os.path.basename(target):<30} | {score}%")
    
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()