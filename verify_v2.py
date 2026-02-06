
import sys
import os
import logging

# Add current dir to path
sys.path.append(os.getcwd())

# Configure logging to show errors in console
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

def test_imports():
    print("Testing Imports...")
    try:
        import pytesseract
        import pyautogui
        from duckduckgo_search import DDGS
        from bs4 import BeautifulSoup
        import requests
        print("PASS: Dependencies installed.")
    except ImportError as e:
        print(f"FAIL: Missing dependency: {e}")
        return

def test_skills_loading():
    print("\nTesting Skills Loading...")
    try:
        from core.engine import JarvisEngine
        # Mock engine to avoid full startup
        engine = JarvisEngine()
        engine.skill_manager.load_skills()
        
        skill_names = [s.name for s in engine.skill_manager.skills]
        print(f"Loaded Skills: {skill_names}")
        
        required = ["VisionSkill", "ResearchSkill", "AutomationSkill", "SmallTalk"]
        missing = [r for r in required if r not in skill_names]
        
        if missing:
            print(f"FAIL: Missing skills: {missing}")
        else:
            print("PASS: All V2.0 Skills Loaded.")
            
    except Exception as e:
        print(f"FAIL: Skill loading error: {e}")
        import traceback
        traceback.print_exc()

def test_direct_imports():
    print("\nTesting Direct Skill Imports...")
    modules = [
        "skills.vision_skill",
        "skills.research_skill",
        "skills.automation_skill",
        "skills.smalltalk_skill"
    ]
    for m in modules:
        try:
            import importlib
            importlib.import_module(m)
            print(f"PASS: Imported {m}")
        except Exception as e:
            print(f"FAIL: Could not import {m}: {e}")

if __name__ == "__main__":
    test_imports()
    test_direct_imports()
    test_skills_loading()
