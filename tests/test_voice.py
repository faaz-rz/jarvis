import unittest

from core.voice import VoiceManager


class FakeUI:
    def __init__(self):
        self.messages = []
        self.statuses = []

    def display_message(self, text, sender="JARVIS"):
        self.messages.append((sender, text))

    def set_status(self, text):
        self.statuses.append(text)


class FakeTTS:
    is_speaking = False


class FakeEngine:
    def __init__(self):
        self.ui = FakeUI()
        self.tts = FakeTTS()
        self.running = True
        self.commands = []
        self.spoken = []

    def handle_input(self, text):
        self.commands.append(text)

    def speak(self, text):
        self.spoken.append(text)


class VoiceRoutingTests(unittest.TestCase):
    def setUp(self):
        self.engine = FakeEngine()
        self.voice = VoiceManager(self.engine)

    def test_command_in_same_wake_word_utterance(self):
        self.voice._handle_transcript("jarvis open calculator")
        self.assertEqual(self.engine.commands, ["open calculator"])

    def test_two_stage_wake_word_interaction(self):
        self.voice._handle_transcript("jarvis")
        self.assertEqual(self.engine.spoken, ["Yes?"])
        self.voice._handle_transcript("what time is it")
        self.assertEqual(self.engine.commands, ["what time is it"])

    def test_unprompted_transcript_is_ignored(self):
        self.voice._handle_transcript("open calculator")
        self.assertEqual(self.engine.commands, [])

    def test_stop_listening_is_not_undone_by_resume_callback(self):
        self.voice._handle_transcript("stop listening")
        self.assertFalse(self.voice.user_enabled)
        self.voice.resume()
        self.assertFalse(self.voice.user_enabled)


if __name__ == "__main__":
    unittest.main()
