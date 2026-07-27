import os
import subprocess
import sys
from pathlib import Path

from core.config import PROJECT_ROOT, coding_model_path
from core.llm import LLMUnavailableError
from core.skills import BaseSkill


class DevSkill(BaseSkill):
    name = "DevMode"
    description = "Generates and saves code using CodeLlama."
    priority = 80

    def __init__(self, context):
        super().__init__(context)
        configured = coding_model_path()
        self.coding_model = str(configured) if configured else None
        output_dir = Path(os.environ.get("JARVIS_GENERATED_DIR", PROJECT_ROOT))
        self.generated_file = output_dir.expanduser().resolve() / "generated_script.py"

    def handle(self, text: str) -> bool:
        lower = text.lower()
        
        # Explicit Mode Switching
        if "enable coding mode" in lower or "start coding mode" in lower:
             self.switch_to_coding()
             return True
             
        if "disable coding mode" in lower or "normal mode" in lower or "exit coding mode" in lower:
             self.switch_to_normal()
             return True

        # Run & Debug (New Feature)
        if "run code" in lower or "debug code" in lower or "fix code" in lower or "it failed" in lower:
            self.run_and_debug_session()
            return True

        # Trigger coding generation
        if "write code" in lower or "create python script" in lower or "generate code" in lower:
            self.start_dev_session(text)
            return True
            
        return False

    def switch_to_coding(self):
        if not self.coding_model:
            self.context.speak(
                "Coding mode is not configured. Set CODE_MODEL_PATH to a GGUF coding model."
            )
            return

        current_path = self.context.engine.llm.current_model_path
        if current_path == self.coding_model:
            self.context.speak("I am already in Coding Mode.")
            return

        self.context.speak("Switching to CodeLlama model. This may take a moment...")
        success = self.context.engine.llm.reload_model(self.coding_model)
        if success:
            self.context.speak("Coding Mode Enabled. Initialized CodeLlama 7B.")
        else:
            self.context.speak("Failed to load the coding model. Reverting to default.")
            if hasattr(self.context.engine.llm, "reload_default_model"):
                self.context.engine.llm.reload_default_model()

    def switch_to_normal(self):
        llm = self.context.engine.llm
        default = llm.default_model_path
        if (
            llm.current_model_path == default
            and getattr(llm, "backend", None) == getattr(llm, "default_backend", None)
        ):
            self.context.speak("I am already in Normal Mode.")
            return

        self.context.speak("Reverting to standard conversation model...")
        if hasattr(llm, "reload_default_model"):
            success = llm.reload_default_model()
        else:
            success = bool(default and llm.reload_model(default))
        if success:
            self.context.speak("Normal Mode Enabled.")
        else:
            self.context.speak("The standard model is not configured.")

    def start_dev_session(self, trigger_text):
        if not self.coding_model:
            self.context.speak(
                "Coding mode is not configured. Set CODE_MODEL_PATH to a GGUF coding model."
            )
            return
        # Auto-switch
        if self.context.engine.llm.current_model_path != self.coding_model:
            self.context.speak("Using Coding Model...")
            self.switch_to_coding()
            if self.context.engine.llm.current_model_path != self.coding_model:
                return

        prompt = trigger_text
        if len(prompt.split()) < 4:
            self.context.speak("Please describe the code.")
            return 
            
        full_prompt = f"Write a complete, runnable Python script for: {prompt}. Return ONLY code."
        
        self.context.speak("Generating code...")
        try:
            code = (
                self.context.llm_query(full_prompt)
                .replace("```python", "")
                .replace("```", "")
                .strip()
            )
            self.generated_file.parent.mkdir(parents=True, exist_ok=True)
            self.generated_file.write_text(code, encoding="utf-8")
            self.context.speak(
                f"Saved to {self.generated_file.name}. Say 'run code' to test it."
            )
        except LLMUnavailableError as e:
            self.context.speak(f"Code generation is unavailable: {e}")
        except OSError as e:
            self.context.speak(f"Save failed: {e}")

    def run_and_debug_session(self):
        if not self.generated_file.exists():
            self.context.speak("No generated script found to run.")
            return

        self.context.speak("Running script...")
        try:
            result = subprocess.run(
                [sys.executable, str(self.generated_file)],
                cwd=str(self.generated_file.parent),
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if not output: output = "Done (No Output)."
                self.context.speak(f"Success! Output: {output[:100]}")
                return
            
            # If failed, start Auto-Fix
            error = result.stderr.strip()
            self.context.speak(f"Script failed. Error: {error.splitlines()[-1]}")
            self.context.speak("Attempting to auto-fix the code...")
            
            # Read broken code
            code = self.generated_file.read_text(encoding="utf-8")
            
            # Fix Prompt
            fix_prompt = f"""
            The following Python code has an error. Fix it.
            CODE:
            {code}
            
            ERROR:
            {error}
            
            Return ONLY the fixed code. No markdown.
            """
            
            fixed_code = (
                self.context.llm_query(fix_prompt)
                .replace("```python", "")
                .replace("```", "")
                .strip()
            )
            self.generated_file.write_text(fixed_code, encoding="utf-8")
            self.context.speak("Applied fix. Say 'run code' to verify.")
        except subprocess.TimeoutExpired:
            self.context.speak("Execution stopped because the script exceeded 10 seconds.")
        except LLMUnavailableError as e:
            self.context.speak(f"Automatic debugging is unavailable: {e}")
        except Exception as e:
            self.context.speak(f"Execution error: {e}")
