#!/usr/bin/env python3
import json
import time
import requests
import os
import sys
from pathlib import Path
from datetime import datetime

try:
    import readchar
except ImportError:
    print("Installing readchar...")
    os.system(f"{sys.executable} -m pip install readchar -q")
    import readchar

CONFIG_FILE = Path.home() / ".llm-benchmark-config.json"
PROMPTS_DIR = Path(__file__).parent / "prompts"
RESULTS_FILE = Path(__file__).parent / "results.txt"

DEFAULT_CONFIG = {
    "ollama_url": "http://localhost:11434",
    "llamacpp_url": "http://localhost:8080",
    "lmstudio_url": "http://localhost:1234",
    "test_iterations": 3
}

def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return DEFAULT_CONFIG.copy()

def save_config(config):
    CONFIG_FILE.write_text(json.dumps(config, indent=2))

def get_prompts():
    if not PROMPTS_DIR.exists():
        return []
    return sorted([f.name for f in PROMPTS_DIR.glob("*.txt")])

def load_prompt(filename):
    return (PROMPTS_DIR / filename).read_text().strip()

def count_tokens(text):
    # Simple approximation: ~4 chars per token
    return len(text) // 4

def format_prompt_preview(prompt):
    lines = prompt.split('\n')
    if len(lines) <= 10:
        return prompt
    preview = '\n'.join(lines[:5])
    preview += f"\n\n... ({len(lines) - 10} lines omitted) ...\n\n"
    preview += '\n'.join(lines[-5:])
    return preview

def save_result(backend, model, prompt_file, prompt, results, iterations):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prompt_tokens = count_tokens(prompt)
    prompt_chars = len(prompt)
    prompt_lines = len(prompt.split('\n'))
    
    with open(RESULTS_FILE, 'a', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write(f"TEST REPORT - {timestamp}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Backend: {backend.upper()}\n")
        f.write(f"Model: {model}\n")
        f.write(f"Prompt File: {prompt_file}\n")
        f.write(f"Prompt Stats: {prompt_chars} chars, {prompt_lines} lines, ~{prompt_tokens} tokens\n")
        f.write(f"Iterations: {iterations}\n\n")
        
        f.write("PROMPT PREVIEW:\n")
        f.write("-" * 80 + "\n")
        f.write(format_prompt_preview(prompt) + "\n")
        f.write("-" * 80 + "\n\n")
        
        f.write("RESULTS:\n")
        for i, (elapsed, tokens, tps) in enumerate(results, 1):
            f.write(f"  Run {i}: {tps:.2f} tok/s ({tokens} tokens in {elapsed:.2f}s)\n")
        
        if results:
            avg_tps = sum(r[2] for r in results) / len(results)
            avg_time = sum(r[0] for r in results) / len(results)
            total_tokens = sum(r[1] for r in results)
            f.write(f"\nAVERAGE: {avg_tps:.2f} tok/s\n")
            f.write(f"AVG TIME: {avg_time:.2f}s\n")
            f.write(f"TOTAL OUTPUT TOKENS: {total_tokens}\n")
        
        f.write("\n\n")

def menu_select(title, options, multi_select=False):
    selected = 0
    marked = set() if multi_select else None
    
    while True:
        os.system('clear' if os.name != 'nt' else 'cls')
        print(f"╔{'═' * 50}╗")
        print(f"║ {title:<48} ║")
        print(f"╚{'═' * 50}╝\n")
        
        if multi_select:
            print("Use ↑↓ to navigate, SPACE to mark, ENTER to confirm, ESC to cancel\n")
        else:
            print("Use ↑↓ to navigate, ENTER to select, ESC to cancel\n")
        
        for i, opt in enumerate(options):
            prefix = "→ " if i == selected else "  "
            mark = "[✓] " if multi_select and i in marked else "[  ] " if multi_select else ""
            print(f"{prefix}{mark}{opt}")
        
        key = readchar.readkey()
        
        if key == readchar.key.UP and selected > 0:
            selected -= 1
        elif key == readchar.key.DOWN and selected < len(options) - 1:
            selected += 1
        elif key == readchar.key.ENTER:
            if multi_select:
                return list(marked) if marked else None
            return selected
        elif key == readchar.key.ESC:
            return None
        elif multi_select and key == ' ':
            if selected in marked:
                marked.remove(selected)
            else:
                marked.add(selected)

def get_ollama_models(url):
    try:
        r = requests.get(f"{url}/api/tags", timeout=2)
        return [m["name"] for m in r.json()["models"]]
    except:
        return []

def get_openai_models(url):
    try:
        r = requests.get(f"{url}/v1/models", timeout=2)
        return [m["id"] for m in r.json()["data"]]
    except:
        return []

def test_ollama(url, model, prompt):
    start = time.time()
    r = requests.post(f"{url}/api/generate", json={"model": model, "prompt": prompt, "stream": False})
    elapsed = time.time() - start
    data = r.json()
    tokens = data.get("eval_count", 0)
    return elapsed, tokens

def test_openai(url, model, prompt):
    start = time.time()
    r = requests.post(f"{url}/v1/chat/completions", json={
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    })
    elapsed = time.time() - start
    data = r.json()
    tokens = data["usage"]["completion_tokens"]
    return elapsed, tokens

def run_benchmark(backend, url, model, prompt, prompt_file, iterations):
    print(f"\n🔄 Testing {model}...")
    print(f"📝 Prompt: {prompt[:60]}..." if len(prompt) > 60 else f"📝 Prompt: {prompt}")
    print(f"🔁 Iterations: {iterations}\n")
    results = []
    
    test_fn = test_ollama if backend == "ollama" else test_openai
    
    for i in range(iterations):
        try:
            elapsed, tokens = test_fn(url, model, prompt)
            tps = tokens / elapsed if elapsed > 0 else 0
            results.append((elapsed, tokens, tps))
            print(f"  Run {i+1}: {tps:.2f} tok/s ({tokens} tokens in {elapsed:.2f}s)")
        except Exception as e:
            print(f"  Run {i+1}: ❌ Error - {e}")
    
    if results:
        avg_tps = sum(r[2] for r in results) / len(results)
        print(f"\n✅ Average: {avg_tps:.2f} tok/s")
        save_result(backend, model, prompt_file, prompt, results, iterations)
        return avg_tps
    return 0

def main_menu(config):
    options = [
        "Test Ollama models",
        "Test llama.cpp models", 
        "Test LM Studio models",
        "Settings",
        "Exit"
    ]
    
    while True:
        choice = menu_select("LLM Speed Benchmark Tool", options)
        
        if choice is None or choice == 4:
            break
        elif choice == 0:
            test_menu("ollama", config["ollama_url"], config)
        elif choice == 1:
            test_menu("llamacpp", config["llamacpp_url"], config)
        elif choice == 2:
            test_menu("lmstudio", config["lmstudio_url"], config)
        elif choice == 3:
            settings_menu(config)

def test_menu(backend, url, config):
    if backend == "ollama":
        models = get_ollama_models(url)
    else:
        models = get_openai_models(url)
    
    if not models:
        os.system('clear' if os.name != 'nt' else 'cls')
        print(f"❌ No models found or {backend} not running at {url}")
        input("\nPress Enter to continue...")
        return
    
    options = models + ["Test all models", "Back"]
    choice = menu_select(f"{backend.upper()} Benchmark", options)
    
    if choice is None or choice == len(options) - 1:
        return
    
    test_all = (choice == len(models))
    selected_models = models if test_all else [models[choice]]
    
    prompt_menu(backend, url, selected_models, config, test_all)

def prompt_menu(backend, url, models, config, test_all=False):
    prompts = get_prompts()
    
    if not prompts:
        os.system('clear' if os.name != 'nt' else 'cls')
        print("❌ No prompts found in prompts/")
        input("\nPress Enter to continue...")
        return
    
    options = prompts + ["Test all prompts", "Back"]
    choice = menu_select("Select Prompt", options)
    
    if choice is None or choice == len(options) - 1:
        return
    
    if choice == len(prompts):
        selected_prompts = prompts
    else:
        selected_prompts = [prompts[choice]]
    
    os.system('clear' if os.name != 'nt' else 'cls')
    
    for model in models:
        for prompt_file in selected_prompts:
            prompt = load_prompt(prompt_file)
            lines = prompt.split('\n')[:10]
            
            os.system('clear' if os.name != 'nt' else 'cls')
            print(f"\n{'='*60}")
            print(f"Model: {model}")
            print(f"Prompt: {prompt_file}")
            print(f"{'='*60}")
            print("\n📝 First 10 lines of prompt:")
            print("-" * 60)
            for line in lines:
                print(line)
            if len(prompt.split('\n')) > 10:
                print("...")
            print("-" * 60)
            
            if test_all:
                print("\n⏩ Auto-running (test all models mode)...")
                time.sleep(1)
            else:
                print("\nPress ENTER to start test, ESC to skip...")
                key = readchar.readkey()
                if key == readchar.key.ESC:
                    print("⏭️  Skipped")
                    time.sleep(0.5)
                    continue
            
            run_benchmark(backend, url, model, prompt, prompt_file, config["test_iterations"])
    
    input("\n✅ Tests complete. Press Enter to continue...")

def settings_menu(config):
    options = [
        f"Ollama URL: {config['ollama_url']}",
        f"llama.cpp URL: {config['llamacpp_url']}",
        f"LM Studio URL: {config['lmstudio_url']}",
        f"Iterations: {config['test_iterations']}",
        "Back"
    ]
    
    while True:
        choice = menu_select("Settings", options)
        
        if choice is None or choice == 4:
            save_config(config)
            break
        
        os.system('clear' if os.name != 'nt' else 'cls')
        if choice == 0:
            config["ollama_url"] = input("Enter Ollama URL: ").strip()
        elif choice == 1:
            config["llamacpp_url"] = input("Enter llama.cpp URL: ").strip()
        elif choice == 2:
            config["lmstudio_url"] = input("Enter LM Studio URL: ").strip()
        elif choice == 3:
            try:
                config["test_iterations"] = int(input("Enter iterations: ").strip())
            except:
                pass
        
        options = [
            f"Ollama URL: {config['ollama_url']}",
            f"llama.cpp URL: {config['llamacpp_url']}",
            f"LM Studio URL: {config['lmstudio_url']}",
            f"Iterations: {config['test_iterations']}",
            "Back"
        ]

if __name__ == "__main__":
    config = load_config()
    try:
        main_menu(config)
    except KeyboardInterrupt:
        pass
    save_config(config)
    print("\n👋 Goodbye!")
