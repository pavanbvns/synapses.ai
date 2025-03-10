import subprocess
# import json


def infer(prompt):
    llama_cpp_path = "./llama.cpp/build/main"  # Relative path
    model_path = "./models/llama-3.2-11b-vision.gguf"  # Relative path
    command = [llama_cpp_path, "-m", model_path, "-p", prompt, "-n", "512"]
    result = subprocess.run(command, capture_output=True, text=True)
    return result.stdout
