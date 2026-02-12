import sentencepiece as spm
import os
import time

def train_tokenizer(input_file, model_prefix, vocab_size, model_type, character_coverage):
    print(f"🚀 Starting Tokenizer Training")
    print(f"📂 Input: {input_file}")
    print(f"🔢 Vocab Size: {vocab_size}")
    print(f"🧠 Model Type: {model_type}")
    
    start_time = time.time()
    
    # SentencePiece trainer arguments
    # input_sentence_size: load limit to avoid OOM on large files, though 200MB is fine.
    # shuffle_input_sentence: good for stochasticity but maybe not strictly necessary for this size.
    command = (
        f"--input={input_file} "
        f"--model_prefix={model_prefix} "
        f"--vocab_size={vocab_size} "
        f"--model_type={model_type} "
        f"--character_coverage={character_coverage} "
        f"--pad_id=0 --unk_id=1 --bos_id=2 --eos_id=3 "
        f"--pad_piece=[PAD] --unk_piece=[UNK] --bos_piece=[BOS] --eos_piece=[EOS] "
        f"--user_defined_symbols=[MASK] "
        f"--input_sentence_size=30000 "
        f"--shuffle_input_sentence=false "
        f"--train_extremely_large_corpus=false"
    )
    
    try:
        spm.SentencePieceTrainer.Train(command)
        print(f"✅ Training complete!")
        print(f"💾 Model saved to: {model_prefix}.model")
        print(f"📚 Vocab saved to: {model_prefix}.vocab")
    except Exception as e:
        print(f"❌ Error during training: {e}")
        raise e
    
    end_time = time.time()
    print(f"⏱️ Duration: {end_time - start_time:.2f}s")

if __name__ == "__main__":
    input_file = "data/corpus_sample.txt"
    # Output to data/ directory as requested implied by "Output: tokenizer.model" usually in CWD or data
    # I'll save to data/tokenizer to keep it organized, then might move or reference it.
    # The prompt says output "tokenizer.model", let's put it in data/tokenizer_mvp to be safe and clean.
    output_dir = "data"
    model_prefix = os.path.join(output_dir, "tokenizer")
    
    train_tokenizer(
        input_file=input_file,
        model_prefix=model_prefix,
        vocab_size=100000,
        model_type="bpe",
        character_coverage=0.9995
    )
