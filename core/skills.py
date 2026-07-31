import os
import importlib.util
import logging
import inspect
import threading
from typing import List, Dict

from core.tools import ToolRegistry


class SkillContext:
    """Provides skills with access to the core engine capabilities."""
    def __init__(self, engine):
        self.engine = engine
    
    def speak(self, text: str):
        self.engine.ui.display_message(text, "JARVIS")
        self.engine.speak(text)
        
    def listen(self) -> str:
        return self.engine.ui.get_input()

    def ask_user(self, question: str) -> str:
        self.engine.speak(question)
        return self.listen()
        
    def llm_query(self, prompt: str) -> str:
        return self.engine.llm.generate(prompt)
        
    @property
    def memory(self):
        return self.engine.memory

class BaseSkill:
    """Abstract base class for all skills."""
    name: str = "BaseSkill"
    description: str = "Base description"
    priority: int = 0

    def __init__(self, context: SkillContext):
        self.context = context

    def handle(self, input_text: str) -> bool:
        """Return True if this skill handled the input."""
        return False

    def help(self) -> str:
        return f"{self.name}: {self.description}"

    def tools(self):
        """Return typed tools this skill exposes to the language model."""
        return []


class SkillManager:
    def __init__(self, context: SkillContext):
        self.context = context
        self.skills: List[BaseSkill] = []
        self.load_errors: Dict[str, str] = {}
        self._process_lock = threading.RLock()
        self.tool_registry = ToolRegistry()
        self.skills_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'skills')

    def load_skills(self):
        self.skills = []
        self.load_errors = {}
        self.tool_registry = ToolRegistry()
        if not os.path.exists(self.skills_dir):
            os.makedirs(self.skills_dir)
            
        for filename in sorted(os.listdir(self.skills_dir)):
            if filename.endswith('.py') and not filename.startswith('__'):
                self._load_skill_file(os.path.join(self.skills_dir, filename))

        self.skills.sort(key=lambda skill: (-skill.priority, skill.name.lower()))
        for skill in self.skills:
            try:
                self.tool_registry.register_many(skill.tools())
            except Exception as exc:
                self.load_errors[f"{skill.name}:tools"] = str(exc)
                logging.error("Failed to register tools for %s: %s", skill.name, exc)
        logging.info(f"Loaded {len(self.skills)} skills.")

    def _load_skill_file(self, filepath):
        try:
            module_name = f"jarvis_skill_{os.path.splitext(os.path.basename(filepath))[0]}"
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not create import specification for {filepath}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find classes inheriting from BaseSkill
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, BaseSkill) and obj is not BaseSkill:
                    skill_instance = obj(self.context)
                    self.skills.append(skill_instance)
                    logging.info(f"Registered skill: {skill_instance.name}")
        except Exception as e:
            self.load_errors[os.path.basename(filepath)] = str(e)
            logging.error(f"Failed to load skill from {filepath}: {e}")

    def process(self, text: str) -> bool:
        """Iterate through skills to see if one wants to handle the input."""
        with self._process_lock:
            for skill in self.skills:
                try:
                    if skill.handle(text):
                        logging.info("Request handled by skill: %s", skill.name)
                        emit = getattr(
                            self.context.engine,
                            "_emit_ui_event",
                            None,
                        )
                        if emit:
                            emit("skill_used", skill=skill.name)
                        return True
                except Exception as e:
                    logging.exception(f"Error in skill {skill.name}: {e}")
                    self.context.speak(
                        f"I encountered an error while executing {skill.name}."
                    )
                    return True
        return False

    def help_text(self) -> str:
        return "\n".join(f"- {skill.help()}" for skill in self.skills)
