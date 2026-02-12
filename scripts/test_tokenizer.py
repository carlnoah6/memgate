import sentencepiece as spm
import os

def test_tokenizer(model_path):
    if not os.path.exists(model_path):
        print(f"❌ Model file not found: {model_path}")
        return

    sp = spm.SentencePieceProcessor(model_file=model_path)

    text = "The quick brown fox jumps over the lazy dog."
    print(f"Original Text: {text}")

    tokens = sp.encode(text, out_type=str)
    print(f"Tokens (str): {tokens}")

    token_ids = sp.encode(text, out_type=int)
    print(f"Token IDs: {token_ids}")

    decoded_text = sp.decode(token_ids)
    print(f"Decoded Text: {decoded_text}")

    assert text == decoded_text, "❌ Decoding mismatch!"
    print("✅ Test Passed: Text reconstructed successfully.")

if __name__ == "__main__":
    model_path = "data/tokenizer.model"
    test_tokenizer(model_path)
