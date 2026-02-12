import pandas as pd
import os
import glob

def convert_parquet_to_text(input_dir, output_file):
    print(f"📂 Reading parquet files from: {input_dir}")
    parquet_files = glob.glob(os.path.join(input_dir, "*.parquet"))
    
    if not parquet_files:
        print("❌ No parquet files found.")
        return

    print(f"📄 Found {len(parquet_files)} files. Processing...")
    
    with open(output_file, "w", encoding="utf-8") as f_out:
        for file in parquet_files:
            print(f"   Reading {file}...")
            df = pd.read_parquet(file)
            
            # Check if 'text' column exists
            if 'text' not in df.columns:
                print(f"⚠️ Column 'text' not found in {file}. Skipping.")
                continue
                
            # Write text to file
            count = 0
            for text in df['text']:
                if isinstance(text, str) and len(text.strip()) > 0:
                    f_out.write(text.strip() + "\n\n")
                    count += 1
            print(f"   ✅ Written {count} documents.")

    print(f"🎉 Corpus saved to: {output_file}")

if __name__ == "__main__":
    input_dir = "data/download/fineweb_temp"
    output_file = "data/corpus_sample.txt"
    convert_parquet_to_text(input_dir, output_file)
