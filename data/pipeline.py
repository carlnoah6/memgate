import re
import hashlib
import json
import logging
from typing import List, Dict, Any, Set

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataPipelineMVP:
    def __init__(self):
        self.seen_hashes: Set[str] = set()
        # Simple English stopwords for heuristic language detection
        self.common_en_words = {
            'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i', 
            'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at'
        }

    def step_1_language_id(self, text: str) -> str:
        """
        Simple heuristic for language identification.
        In production, replace with: import fasttext; model.predict(text)
        """
        if not text or len(text.strip()) == 0:
            return "unknown"
            
        words = text.lower().split()
        if len(words) == 0:
            return "unknown"
            
        # Count intersection with common english words
        match_count = sum(1 for w in words if w in self.common_en_words)
        ratio = match_count / len(words)
        
        # Threshold for considering it English
        if ratio > 0.1: 
            return "en"
        return "other"

    def step_2_quality_filter(self, text: str) -> bool:
        """
        Filter out low quality text based on:
        1. Length (too short)
        2. Special character ratio
        """
        # 1. Length check
        if len(text) < 20:
            logger.debug(f"Filtered (length): {text[:20]}...")
            return False
            
        # 2. Special character ratio
        special_chars = sum(1 for c in text if not c.isalnum() and not c.isspace())
        ratio = special_chars / len(text)
        if ratio > 0.4: # If more than 40% are symbols
            logger.debug(f"Filtered (symbols): {text[:20]}...")
            return False
            
        return True

    def step_3_deduplication(self, text: str) -> bool:
        """
        Exact deduplication using MD5 hash.
        Returns True if unique (new), False if duplicate.
        """
        # Normalize text (basic)
        normalized = text.strip().lower()
        content_hash = hashlib.md5(normalized.encode('utf-8')).hexdigest()
        
        if content_hash in self.seen_hashes:
            logger.debug(f"Filtered (duplicate): {text[:20]}...")
            return False
        
        self.seen_hashes.add(content_hash)
        return True

    def step_4_pii_scrubbing(self, text: str) -> str:
        """
        Basic regex-based PII scrubbing.
        """
        # Email regex
        text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '<EMAIL_REDACTED>', text)
        
        # Phone regex (simple generic)
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '<PHONE_REDACTED>', text)
        
        # IP Address
        text = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '<IP_REDACTED>', text)
        
        return text

    def process(self, dataset: List[str]) -> List[str]:
        """
        Run the full pipeline on a dataset.
        """
        cleaned_data = []
        stats = {"total": 0, "kept": 0, "lang_filtered": 0, "quality_filtered": 0, "dedup_filtered": 0}
        
        for text in dataset:
            stats["total"] += 1
            
            # 1. Language ID
            lang = self.step_1_language_id(text)
            if lang != "en":
                stats["lang_filtered"] += 1
                continue
                
            # 2. Quality Filter
            if not self.step_2_quality_filter(text):
                stats["quality_filtered"] += 1
                continue
                
            # 3. Deduplication
            if not self.step_3_deduplication(text):
                stats["dedup_filtered"] += 1
                continue
                
            # 4. PII Scrubbing
            clean_text = self.step_4_pii_scrubbing(text)
            
            cleaned_data.append(clean_text)
            stats["kept"] += 1
            
        logger.info(f"Pipeline Stats: {json.dumps(stats, indent=2)}")
        return cleaned_data

if __name__ == "__main__":
    # Mock Data
    raw_data = [
        "This is a high quality English sentence that should pass.",
        "Ceci est une phrase en français.", # Non-English
        "Short.", # Too short
        "!!! @@@ ### $$$ %%% ^^^ &&&", # High symbol ratio
        "This is a high quality English sentence that should pass.", # Duplicate
        "Contact me at john.doe@example.com or 123-456-7890.", # PII
        "Server IP is 192.168.1.1, please connect." # PII
    ]
    
    logger.info("Starting Data Pipeline MVP...")
    pipeline = DataPipelineMVP()
    results = pipeline.process(raw_data)
    
    logger.info("Processing complete. Results:")
    for res in results:
        print(f"- {res}")
