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
TEMP_DIR = Path(__file__).parent / "temp"

DEFAULT_CONFIG = {
    "ollama_url": "http://localhost:11434",
    "llamacpp_url": "http://localhost:8080",
    "lmstudio_url": "http://localhost:1234",
    "test_iterations": 3,
    "temperature": 0.3,
    "max_tokens": 8192,
    "top_p": 0.95,
    "repeat_penalty": 1.1
}

def load_config():
    if CONFIG_FILE.exists():
        config = json.loads(CONFIG_FILE.read_text())
        # Merge with defaults for any missing keys
        for key, value in DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = value
        return config
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
            print("Use ↑↓ to navigate, SPACE to mark, ENTER to confirm, q to cancel\n")
        else:
            print("Use ↑↓ to navigate, ENTER to select, q to cancel\n")
        
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
        elif key in ['q', 'Q', '\x1b']:  # q, Q or ESC
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
    payload = {"model": model, "prompt": prompt, "stream": False}
    r = requests.post(f"{url}/api/generate", json=payload)
    elapsed = time.time() - start
    data = r.json()
    tokens = data.get("eval_count", 0)
    return elapsed, tokens, payload, data

def test_openai(url, model, prompt, config):
    start = time.time()
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": config["temperature"],
        "max_tokens": config["max_tokens"],
        "top_p": config["top_p"],
        "repeat_penalty": config["repeat_penalty"]
    }
    r = requests.post(f"{url}/v1/chat/completions", json=payload)
    elapsed = time.time() - start
    data = r.json()
    tokens = data["usage"]["completion_tokens"]
    return elapsed, tokens, payload, data

def save_request_response(backend, model, prompt_file, prompt, payload, response, run_num, session_dir):
    session_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    prompt_name = Path(prompt_file).stem
    model_safe = model.replace("/", "_").replace(":", "_")
    
    base_name = f"{timestamp}_{backend}_{model_safe}_{prompt_name}_run{run_num}"
    
    # Request file
    request_data = {
        "backend": backend,
        "model": model,
        "prompt_file": prompt_file,
        "timestamp": timestamp,
        "run": run_num,
        "payload": payload,
        "prompt": prompt
    }
    (session_dir / f"{base_name}.req").write_text(json.dumps(request_data, indent=2, ensure_ascii=False))
    
    # Response file - JSON format
    (session_dir / f"{base_name}.res.json").write_text(json.dumps(response, indent=2, ensure_ascii=False))
    
    # Response file - Formatted markdown
    try:
        if backend == "ollama":
            content = response.get("response", "")
        else:
            # OpenAI format - check for thinking/reasoning
            message = response.get("choices", [{}])[0].get("message", {})
            content = message.get("content", "")
            
            # Check if there's a thinking/reasoning process
            thinking = None
            if "reasoning_content" in message:
                thinking = message.get("reasoning_content")
            elif "thinking" in message:
                thinking = message.get("thinking")
            
            # Format with thinking section if exists
            if thinking:
                formatted_content = f"## 🧠 Düşünme Süreci\n\n```\n{thinking}\n```\n\n---\n\n## 💬 Cevap\n\n{content}"
            else:
                formatted_content = content
        
        (session_dir / f"{base_name}.res.md").write_text(formatted_content if backend != "ollama" else content, encoding='utf-8')
    except:
        pass

def run_benchmark(backend, url, model, prompt, prompt_file, iterations, session_dir, config):
    print(f"\n🔄 Testing {model}...")
    print(f"📝 Prompt: {prompt[:60]}..." if len(prompt) > 60 else f"📝 Prompt: {prompt}")
    print(f"🔁 Iterations: {iterations}\n")
    results = []
    
    test_fn = test_ollama if backend == "ollama" else lambda u, m, p: test_openai(u, m, p, config)
    
    for i in range(iterations):
        try:
            elapsed, tokens, payload, response = test_fn(url, model, prompt)
            tps = tokens / elapsed if elapsed > 0 else 0
            results.append((elapsed, tokens, tps))
            save_request_response(backend, model, prompt_file, prompt, payload, response, i+1, session_dir)
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
    
    choices = menu_select(f"{backend.upper()} Benchmark - Select Models", models, multi_select=True)
    
    if choices is None or not choices:
        return
    
    selected_models = [models[i] for i in choices]
    
    prompt_menu(backend, url, selected_models, config)

def prompt_menu(backend, url, models, config):
    prompts = get_prompts()
    
    if not prompts:
        os.system('clear' if os.name != 'nt' else 'cls')
        print("❌ No prompts found in prompts/")
        input("\nPress Enter to continue...")
        return
    
    choices = menu_select("Select Prompts", prompts, multi_select=True)
    
    if choices is None or not choices:
        return
    
    selected_prompts = [prompts[i] for i in choices]
    
    os.system('clear' if os.name != 'nt' else 'cls')
    
    # Create session directory with timestamp
    session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = TEMP_DIR / session_timestamp
    performance_file = session_dir / "performans.txt"
    
    results_summary = []
    
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
            
            if len(models) > 1 or len(selected_prompts) > 1:
                print("\n⏩ Auto-running (multiple tests mode)...")
                time.sleep(1)
            else:
                print("\nPress ENTER to start test, ESC to skip...")
                key = readchar.readkey()
                if key == readchar.key.ESC:
                    print("⏭️  Skipped")
                    time.sleep(0.5)
                    continue
            
            avg_tps = run_benchmark(backend, url, model, prompt, prompt_file, config["test_iterations"], session_dir, config)
            if avg_tps > 0:
                results_summary.append((model, prompt_file, avg_tps))
                
                # Update performance file after each test
                results_summary.sort(key=lambda x: x[2], reverse=True)
                with open(performance_file, 'w', encoding='utf-8') as f:
                    f.write("=" * 80 + "\n")
                    f.write("📊 PERFORMANCE SUMMARY (Fastest to Slowest)\n")
                    f.write("=" * 80 + "\n\n")
                    for i, (m, p, tps) in enumerate(results_summary, 1):
                        f.write(f"{i}. {m:<40} | {p:<30} | {tps:>6.2f} tok/s\n")
                    f.write("\n" + "=" * 80 + "\n")
    
    if results_summary:
        os.system('clear' if os.name != 'nt' else 'cls')
        print("\n" + "="*80)
        print("📊 PERFORMANCE SUMMARY (Fastest to Slowest)")
        print("="*80 + "\n")
        
        results_summary.sort(key=lambda x: x[2], reverse=True)
        
        for i, (model, prompt_file, tps) in enumerate(results_summary, 1):
            print(f"{i}. {model:<40} | {prompt_file:<30} | {tps:>6.2f} tok/s")
        
        print("\n" + "="*80)
        print(f"\n💾 Performance summary saved to: temp/{session_timestamp}/performans.txt")
    
    input("\n✅ Tests complete. Press Enter to continue...")

def settings_menu(config):
    options = [
        f"Ollama URL: {config['ollama_url']}",
        f"llama.cpp URL: {config['llamacpp_url']}",
        f"LM Studio URL: {config['lmstudio_url']}",
        f"Iterations: {config['test_iterations']}",
        f"Temperature: {config['temperature']}",
        f"Max Tokens: {config['max_tokens']}",
        f"Top P: {config['top_p']}",
        f"Repeat Penalty: {config['repeat_penalty']}",
        "Back"
    ]
    
    while True:
        choice = menu_select("Settings", options)
        
        if choice is None or choice == 8:
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
        elif choice == 4:
            try:
                config["temperature"] = float(input("Enter temperature (0.0-2.0): ").strip())
            except:
                pass
        elif choice == 5:
            try:
                config["max_tokens"] = int(input("Enter max tokens: ").strip())
            except:
                pass
        elif choice == 6:
            try:
                config["top_p"] = float(input("Enter top_p (0.0-1.0): ").strip())
            except:
                pass
        elif choice == 7:
            try:
                config["repeat_penalty"] = float(input("Enter repeat penalty: ").strip())
            except:
                pass
        
        options = [
            f"Ollama URL: {config['ollama_url']}",
            f"llama.cpp URL: {config['llamacpp_url']}",
            f"LM Studio URL: {config['lmstudio_url']}",
            f"Iterations: {config['test_iterations']}",
            f"Temperature: {config['temperature']}",
            f"Max Tokens: {config['max_tokens']}",
            f"Top P: {config['top_p']}",
            f"Repeat Penalty: {config['repeat_penalty']}",
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
