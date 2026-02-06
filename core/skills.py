import os
import importlib.util
import logging
import inspect
from typing import List, Dict, Callable

class SkillContext:
    """Provides skills with access to the core engine capabilities."""
    def __init__(self, engine):
        self.engine = engine
    
    def speak(self, text: str):
        self.engine.ui.display_message(text, "JARVIS")
        self.engine.speak(text)
        
    def listen(self) -> str:
        # For now, just a placeholder or UI prompt if needed
        # In a real voice loop, this would record audio
        return self.engine.ui.get_input()

    def ask_user(self, question: str) -> str:
        self.engine.speak(question)
        # In a real GUI async flow, this is tricky. 
        # For now we assume a blocking behavior or CLI/callback flow.
        # But since our engine is async-ish, returning values is hard.
        return ""  # Placeholder
        
    def llm_query(self, prompt: str) -> str:
        return self.engine.llm.generate(prompt)
        
    @property
    def memory(self):
        return self.engine.memory

class BaseSkill:
    """Abstract base class for all skills."""
    name: str = "BaseSkill"
    description: str = "Base description"

    def __init__(self, context: SkillContext):
        self.context = context

    def handle(self, input_text: str) -> bool:
        """Return True if this skill handled the input."""
        return False

    def help(self) -> str:
        return f"{self.name}: {self.description}"

class SkillManager:
    def __init__(self, context: SkillContext):
        self.context = context
        self.skills: List[BaseSkill] = []
        self.skills_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'skills')

    def load_skills(self):
        self.skills = []
        if not os.path.exists(self.skills_dir):
            os.makedirs(self.skills_dir)
            
        for filename in os.listdir(self.skills_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                self._load_skill_file(os.path.join(self.skills_dir, filename))
        
        logging.info(f"Loaded {len(self.skills)} skills.")

    def _load_skill_file(self, filepath):
        try:
            spec = importlib.util.spec_from_file_location("skill_module", filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find classes inheriting from BaseSkill
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, BaseSkill) and obj is not BaseSkill:
                    skill_instance = obj(self.context)
                    self.skills.append(skill_instance)
                    logging.info(f"Registered skill: {skill_instance.name}")
        except Exception as e:
            logging.error(f"Failed to load skill from {filepath}: {e}")

    def process(self, text: str) -> bool:
        """Iterate through skills to see if one wants to handle the input."""
        for skill in self.skills:
            try:
                if skill.handle(text):
                    return True
            except Exception as e:
                logging.error(f"Error in skill {skill.name}: {e}")
                self.context.speak(f"I encountered an error while executing {skill.name}.")
                return True # We caught it, so it's 'handled' in a way
        return False
