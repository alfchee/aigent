
import unittest
from unittest.mock import MagicMock, patch
import asyncio
from app.core.agent import NaviBot

class TestAgentHistory(unittest.TestCase):
    def test_get_history_uses_get_history_method(self):
        """Test that get_history calls the method on the chat object if it exists."""
        bot = NaviBot()
        
        # Mock the chat session object
        mock_chat = MagicMock()
        # Ensure it does NOT have a history attribute
        del mock_chat.history 
        # Ensure it HAS a get_history method
        mock_chat.get_history.return_value = [{"role": "user", "parts": ["hello"]}]
        
        # Inject the mock chat into the bot's sessions
        bot._chat_sessions["test_session"] = mock_chat
        
        # Call get_history
        history = bot.get_history("test_session")
        
        # Verify result
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["role"], "user")
        
        # Verify method was called
        mock_chat.get_history.assert_called_once()

    def test_get_history_fallback_to_attribute(self):
        """Test that get_history falls back to .history attribute if get_history method is missing."""
        bot = NaviBot()
        
        # Mock the chat session object
        mock_chat = MagicMock()
        # Ensure it does NOT have get_history method
        del mock_chat.get_history
        # Ensure it HAS a history attribute
        mock_chat.history = [{"role": "model", "parts": ["hi"]}]
        
        # Inject the mock chat into the bot's sessions
        bot._chat_sessions["test_session_legacy"] = mock_chat
        
        # Call get_history
        history = bot.get_history("test_session_legacy")
        
        # Verify result
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["role"], "model")

    def test_get_history_missing_both(self):
        """Test graceful failure when neither exists."""
        bot = NaviBot()
        
        mock_chat = MagicMock()
        del mock_chat.get_history
        del mock_chat.history
        
        bot._chat_sessions["broken_session"] = mock_chat
        
        history = bot.get_history("broken_session")
        self.assertEqual(history, [])

if __name__ == "__main__":
    unittest.main()
