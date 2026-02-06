import subprocess

class DevSkill(BaseSkill):
    name = "DevMode"
    description = "Generates and saves code using CodeLlama."

    CODING_MODEL = r"D:\models\codellama\codellama-7b-instruct.Q5_K_M.gguf"

    def handle(self, text: str) -> bool:
        print(f"DEBUG: DevSkill handle called with: '{text}'")
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
        current_path = self.context.engine.llm.current_model_path
        if current_path == self.CODING_MODEL:
            self.context.speak("I am already in Coding Mode.")
            return

        self.context.speak("Switching to CodeLlama model. This may take a moment...")
        success = self.context.engine.llm.reload_model(self.CODING_MODEL)
        if success:
            self.context.speak("Coding Mode Enabled. Initialized CodeLlama 7B.")
        else:
             self.context.speak("Failed to load CodeLlama. Reverting to default.")
             self.context.engine.llm.reload_model(self.context.engine.llm.default_model_path)

    def switch_to_normal(self):
        default = self.context.engine.llm.default_model_path
        if self.context.engine.llm.current_model_path == default:
            self.context.speak("I am already in Normal Mode.")
            return

        self.context.speak("Reverting to standard conversation model...")
        success = self.context.engine.llm.reload_model(default)
        if success:
             self.context.speak("Normal Mode Enabled.")
        else:
             self.context.speak("Error reverting model. System check required.")

    def start_dev_session(self, trigger_text):
        # Auto-switch
        if self.context.engine.llm.current_model_path != self.CODING_MODEL:
             self.context.speak("Using Coding Model...")
             self.switch_to_coding()
             if self.context.engine.llm.current_model_path != self.CODING_MODEL: return

        prompt = trigger_text
        if len(prompt.split()) < 4:
            self.context.speak("Please describe the code.")
            return 
            
        full_prompt = f"Write a complete, runnable Python script for: {prompt}. Return ONLY code."
        
        self.context.speak("Generating code...")
        code = self.context.llm_query(full_prompt).replace("```python", "").replace("```", "").strip()
        
        filename = "generated_script.py"
        try:
            with open(filename, "w") as f: f.write(code)
            self.context.speak(f"Saved to {filename}. Say 'run code' to test it.")
        except Exception as e:
            self.context.speak(f"Save failed: {e}")

    def run_and_debug_session(self):
        filename = "generated_script.py"
        if not os.path.exists(filename):
            self.context.speak("No generated script found to run.")
            return

        self.context.speak("Running script...")
        try:
            result = subprocess.run(["python", filename], capture_output=True, text=True, timeout=10)
            
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
            with open(filename, "r") as f: code = f.read()
            
            # Fix Prompt
            fix_prompt = f"""
            The following Python code has an error. Fix it.
            CODE:
            {code}
            
            ERROR:
            {error}
            
            Return ONLY the fixed code. No markdown.
            """
            
            fixed_code = self.context.llm_query(fix_prompt).replace("```python", "").replace("```", "").strip()
            
            with open(filename, "w") as f: f.write(fixed_code)
            self.context.speak("Applied fix. Say 'run code' to verify.")
            
        except Exception as e:
            self.context.speak(f"Execution error: {e}")
