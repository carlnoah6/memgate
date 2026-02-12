
import sys
import unittest
from unittest.mock import MagicMock, patch
import json
from pathlib import Path

# Add scripts/ to path to import the module
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "scripts"))

# Import the module to be tested
# We use importlib because the filename has hyphens
import importlib.util
spec = importlib.util.spec_from_file_location("check_group_privacy", 
    str(Path(__file__).resolve().parent.parent.parent / "scripts/check-group-privacy.py"))
check_group_privacy = importlib.util.module_from_spec(spec)
sys.modules["check_group_privacy"] = check_group_privacy
spec.loader.exec_module(check_group_privacy)

class TestCheckGroupPrivacy(unittest.TestCase):
    
    def setUp(self):
        # Configuration mock
        self.config_patcher = patch('check_group_privacy.load_config')
        self.mock_config = self.config_patcher.start()
        self.mock_config.return_value = {
            "app_id": "cli_123",
            "app_secret": "secret_123",
            "admin_open_id": "ou_carl"
        }

    def tearDown(self):
        self.config_patcher.stop()

    @patch('urllib.request.urlopen')
    def test_mixed_luna_members(self, mock_urlopen):
        """
        Test scenario:
        - Admin: Carl (ou_carl)
        - Bot: Luna (ou_bot_luna)
        - User: Luna (ou_human_luna) -> Same name as bot!
        
        Expected: is_private = False (because there is a second human)
        """
        BOT_OPEN_ID = "ou_88371dccab8541963f7f6a108990d7b3"
        HUMAN_LUNA_ID = "ou_human_luna"
        ADMIN_ID = "ou_carl"

        # Mock responses for the sequence of calls:
        # 1. get_tenant_token
        # 2. get_bot_open_id
        # 3. get_group_members
        
        mock_response_token = MagicMock()
        mock_response_token.read.return_value = json.dumps({
            "code": 0, "tenant_access_token": "t-123"
        }).encode()

        mock_response_bot_info = MagicMock()
        mock_response_bot_info.read.return_value = json.dumps({
            "code": 0, 
            "bot": {"open_id": BOT_OPEN_ID, "app_name": "Luna"}
        }).encode()

        mock_response_members = MagicMock()
        mock_response_members.read.return_value = json.dumps({
            "code": 0,
            "data": {
                "has_more": False,
                "items": [
                    {
                        "member_id": ADMIN_ID, 
                        "name": "Carl",
                        "member_type": "user"
                    },
                    {
                        "member_id": BOT_OPEN_ID, 
                        "name": "Luna",
                        "member_type": "bot"  # This is the key field we want to leverage
                    },
                    {
                        "member_id": HUMAN_LUNA_ID, 
                        "name": "Luna",
                        "member_type": "user"
                    }
                ]
            }
        }).encode()

        # Set side_effect to return these in order
        # Note: tenant token is called inside check_group_privacy -> get_tenant_token
        # then get_bot_open_id
        # then get_group_members
        mock_urlopen.side_effect = [
            mock_response_token,
            mock_response_bot_info,
            mock_response_members
        ]

        # Run the function
        result = check_group_privacy.check_group_privacy("oc_test_chat")

        # Verify
        print("\nTest Result:", json.dumps(result, indent=2, ensure_ascii=False))
        
        self.assertFalse(result['is_private'], "Should NOT be private because Human Luna is present")
        self.assertEqual(result['human_count'], 2, "Should count 2 humans (Carl + Luna)")
        
        # Verify members structure
        human_luna = next(m for m in result['members'] if m['open_id'] == HUMAN_LUNA_ID)
        self.assertFalse(human_luna['is_bot'], "Human Luna should not be marked as bot")
        
        bot_luna = next(m for m in result['members'] if m['open_id'] == BOT_OPEN_ID)
        self.assertTrue(bot_luna['is_bot'], "Bot Luna should be marked as bot")

if __name__ == '__main__':
    unittest.main()
