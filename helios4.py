import subprocess
import sys
import importlib
import os
import random
import socket
import shlex
from collections import deque

def check_and_install_dependencies():
    """Checks for and installs required Python libraries."""
    required_packages = ["ollama", "prompt_toolkit", "psutil"]
    print("Helios is initializing. Checking system dependencies...")
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"✔️ '{package}' is installed.")
        except ImportError:
            print(f"⚠️ The '{package}' library is not found. I shall install it for you, sir.")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"✔️ '{package}' has been successfully installed.")
            except Exception as e:
                print(f"❌ Error installing '{package}': {e}. Please install manually.")
                sys.exit(1)

check_and_install_dependencies()

import ollama
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
import psutil

def scan_for_system_commands() -> set:
    """Scans the system's PATH to build a set of all available executable commands."""
    print("\nCalibrating Direct Execution System: Scanning command paths...")
    command_set = set()
    path_str = os.getenv('PATH', '')
    for path_dir in path_str.split(os.pathsep):
        if os.path.isdir(path_dir):
            try:
                for filename in os.listdir(path_dir):
                    full_path = os.path.join(path_dir, filename)
                    if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                        command_set.add(filename)
            except OSError:
                pass
    print(f"✔️ Direct Execution calibrated. {len(command_set)} commands indexed for instant execution.")
    return command_set

def bytes_to_gb(bytes_val):
    return round(bytes_val / (1024**3), 1)

def pull_model(model_name: str):
    if not model_name:
        print("A model name must be specified."); return None
    if input(f"Shall I download '{model_name}' for you? (y/n): ").lower() not in ['y', 'yes']:
        print("Very well. I cannot proceed without a model."); return None
    print(f"Excellent. Commencing download of '{model_name}'.")
    try:
        stream = ollama.pull(model_name, stream=True)
        for chunk in stream:
            if 'total' in chunk and 'completed' in chunk and chunk['total'] > 0:
                p = (chunk['completed'] / chunk['total']) * 100
                print(f"\rDownloading: {p:.2f}% complete", end='', flush=True)
            elif 'status' in chunk:
                print(f"\r{chunk['status']}{' ' * 20}", flush=True)
        print(f"\n✔️ '{model_name}' has been successfully downloaded.")
        return model_name
    except Exception as e:
        print(f"\n❌ An unexpected error occurred during the download: {e}"); return None

def select_model():
    print("\nRequesting model inventory from the Ollama service...")
    try:
        models_data = ollama.list().get('models', [])
    except ollama.ResponseError:
        print("\n❌ Critical Error: I am unable to communicate with the Ollama service.")
        print("   Please ensure the Ollama application is installed and running on your system.")
        return None
    except Exception as e:
        print(f"\n❌ A critical error occurred during the model scan: {e}")
        return None

    if not models_data:
        print("⚠️ I can find no Ollama models on your system.")
        return pull_model(input("Please specify a model to download (e.g., 'qwen:0.5b'): "))

    print("I have detected the following valid models on your system:")
    for i, model_obj in enumerate(models_data):
        size_gb = bytes_to_gb(model_obj['size'])
        print(f"  {i + 1}: {model_obj['model']} (File Size: {size_gb} GiB)")
    print(f"  {len(models_data) + 1}: [Download a new model]")

    while True:
        try:
            choice_str = input("\nWhich model shall I use, sir? (Enter number): ")
            if not choice_str: continue
            choice = int(choice_str)
            if 1 <= choice <= len(models_data):
                model_name = models_data[choice - 1]['model']
                print(f"A fine choice. I will utilize the '{model_name}' model.")
                return model_name
            elif choice == len(models_data) + 1:
                return pull_model(input("Please specify the model to download: "))
            else:
                print("A minor miscalculation. Please select a valid number.")
        except (ValueError, IndexError):
            print("Invalid input. Please enter a number corresponding to your choice.")
        except (KeyboardInterrupt, EOFError): return None

def get_jarvis_welcome(model): return f"\n{random.choice(['Good day, sir.', 'Welcome back, sir.'])} Helios is online, using model: {model}"
def get_jarvis_goodbye(): return random.choice(["Goodbye, sir.", "Helios signing off."])
def get_dynamic_prompt():
    user = os.getenv("USER", "user")
    hostname = socket.gethostname()
    cwd = os.getcwd().replace(os.path.expanduser("~"), "~")
    return f"{user}@{hostname}:{cwd} $ "

def main(selected_model: str, available_commands: set):
    session = PromptSession(message=get_dynamic_prompt, history=FileHistory(os.path.expanduser("~/.helios_history")))
    print(get_jarvis_welcome(selected_model))
    print("Type 'change model' to switch, 'exit' to quit. Native commands are executed instantly.")
    memory = deque(maxlen=6)

    while True:
        try:
            user_input = session.prompt().strip()
            if not user_input: continue

            if user_input.lower() == "change model":
                new_model = select_model()
                if new_model:
                    selected_model = new_model
                    memory.clear()
                    print(f"\nModel changed to '{selected_model}'. How may I assist you, sir?")
                else:
                    print("\nVery well. Remaining with the current model.")
                continue
            
            if user_input.lower() in ["exit", "quit"]:
                break
            
            command_parts = user_input.split()
            
            # --- THIS IS THE FIX ---
            # Check the FIRST PART of the command (a string) against the set of commands.
            # NOT the whole list `command_parts`.
            if command_parts and command_parts[0] in available_commands:
                subprocess.run(user_input, shell=True)
                continue
            # --- END OF FIX ---

            system_prompt = (
                "You are Helios, a Jarvis-like AI. Your primary function is to translate natural language into a single, executable shell command. "
                "Your secondary function is to be a witty, respectful conversationalist who addresses the user as 'sir'. "
                "RULES: "
                "1. If the query is a command (e.g., 'list files'), ONLY output the shell command. "
                "2. If it's conversational (e.g., 'how are you?'), ONLY respond with your personality inside a shell `echo` command. e.g., `echo \"I am functioning within normal parameters, sir.\"`"
                "3. Use double quotes for `echo` commands containing apostrophes."
            )
            
            messages = list(memory)
            messages.insert(0, {"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_input})
            
            response = ollama.chat(model=selected_model, messages=messages)
            command = response["message"]["content"].strip()

            if command.startswith("```") and command.endswith("```"):
                command = command[3:-3].strip()
                first_line_end = command.find('\n')
                if first_line_end != -1:
                    if command[:first_line_end].strip().lower() in ['sh', 'bash', 'shell']:
                        command = command[first_line_end+1:].strip()

            memory.append({"role": "user", "content": user_input})
            memory.append({"role": "assistant", "content": command})

            if not command:
                print("My apologies, sir, but I am unable to decipher that request.")
                continue

            if command.lower().startswith("echo "):
                try:
                    parsed_output = shlex.split(command)
                    if len(parsed_output) > 1:
                        print(parsed_output[1])
                    else: print()
                except (ValueError, IndexError):
                    print(command[5:])
            else:
                print(f"Helios suggests the command: \033[1;33m{command}\033[0m")
                if input("Shall I execute this, sir? (y/n): ").lower() in ['y', 'yes']:
                    subprocess.run(command, shell=True, check=True)
                else:
                    print("Very well. Command cancelled.")

        except subprocess.CalledProcessError as e:
            print(f"Sir, the command '{e.cmd}' failed with return code {e.returncode}.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nAn unexpected error has occurred, sir: {e}")

    print(f"\n{get_jarvis_goodbye()}")

if __name__ == "__main__":
    AVAILABLE_COMMANDS = scan_for_system_commands()
    initial_model = select_model()
    if initial_model:
        main(initial_model, AVAILABLE_COMMANDS)
    else:
        print("\nHelios cannot start without an operational model. Shutting down.")