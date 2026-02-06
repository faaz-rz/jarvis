from core.skills import BaseSkill
import subprocess
import logging

class AutomationSkill(BaseSkill):
    name = "AutomationSkill"
    description = "Controls the system via PowerShell commands."

    def __init__(self, context):
        super().__init__(context)
        self.pending_command = None

    def handle(self, text: str) -> bool:
        lower = text.lower().strip()
        
        # 1. Handle Verification/Confirmation
        if self.pending_command:
            if lower in ["yes", "confirm", "proceed", "do it", "sure"]:
                self.execute_pending()
                return True
            elif lower in ["no", "cancel", "stop", "don't"]:
                self.context.speak("Command cancelled.")
                self.pending_command = None
                return True
            else:
                self.context.speak("Please confirm: 'yes' to execute, 'no' to cancel.")
                return True

        # 2. Trigger Logic
        triggers = ["system", "open app", "create file", "make folder", "set volume", "run command", "execute"]
        # Also catch generic "open [app]" or "turn up volume" if possible, but let's be safe.
        # Let's use a keyword trigger for now to avoid false positives, or ask LLM to classify?
        # A simple heuristic: "can you [action]" might be smalltalk.
        # Let's check if the user *explicitly* asks for system action or if the text implies it strongly.
        
        strong_triggers = ["open ", "close ", "create ", "delete ", "set volume", "shutdown", "restart"]
        if any(t in lower for t in strong_triggers):
            # Use LLM to generate command
            self.propose_command(text)
            return True
            
        return False

    def propose_command(self, user_text):
        prompt = f"""
        You are an expert PowerShell developer. The user wants to perform a system action.
        User Request: "{user_text}"
        
        Generate the corresponding PowerShell command.
        - Return ONLY the command.
        - No markdown, no explanation.
        - If it involves opening an app, try `start "AppName"`.
        - If it involves volume, use nircmd or wscript, or just say #Impossible if too hard without tools.
        - Example: "Create folder test" -> "mkdir test"
        """
        command = self.context.llm_query(prompt).strip().strip('`').strip()
        
        if "Impossible" in command or len(command) > 200:
             self.context.speak("I am sorry, I can't generate a safe command for that.")
             return

        self.pending_command = command
        self.context.speak(f"I am ready to execute: {command}. Do you confirm?")

    def execute_pending(self):
        cmd = self.pending_command
        self.pending_command = None
        self.context.speak("Executing...")
        
        try:
            # Run PowerShell command
            result = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True)
            if result.returncode == 0:
                output = result.stdout.strip()
                if not output: output = "Done."
                self.context.speak(f"Success. {output[:100]}")
            else:
                self.context.speak(f"Command failed: {result.stderr[:200]}")
        except Exception as e:
            self.context.speak(f"System error: {e}")
