"""
Privacy Guard Plugin for OpenClaw

A multi-user privacy isolation framework that provides:
1. Context-based knowledge access control
2. Output review for privacy violations  
3. Knowledge tagging (public/private)
4. Memory search filtering
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set, Any
from datetime import datetime
import uuid

# Data classes
@dataclass
class KnowledgeItem:
    id: str
    user: str
    content: str
    visibility: str  # 'public' or 'private'
    category: str
    source: str
    created: str

@dataclass
class Violation:
    category: str
    matched: str
    description: str

@dataclass
class ReviewResult:
    passed: bool
    message: Optional[str] = None
    violations: List[Violation] = field(default_factory=list)
    suggestion: Optional[str] = None

@dataclass
class ChannelInfo:
    channel_id: str
    participants: Set[str]
    channel_type: str  # 'dm' or 'group'
    
    @property
    def is_private(self) -> bool:
        return len(self.participants) <= 1

# Configuration
DEFAULT_CONFIG = {
    "enabled": True,
    "review": {
        "enabled": True,
        "llm_self_review": False,
        "block_on_violation": True
    },
    "knowledge_base": {
        "path": "./privacy/knowledge",
        "auto_tag": True
    },
    "defaults": {
        "visibility": "private",
        "always_private_categories": [
            "calendar", "family", "finance", "health", 
            "auth", "contact_private", "dm_content"
        ]
    }
}

class KnowledgeStore:
    """Knowledge storage with public/private classification"""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.items: Dict[str, List[KnowledgeItem]] = {}
        self.load()
    
    def load(self):
        """Load knowledge from filesystem"""
        if not self.base_path.exists():
            self.base_path.mkdir(parents=True, exist_ok=True)
            return
        
        for user_dir in self.base_path.iterdir():
            if user_dir.is_dir():
                user = user_dir.name
                self.items[user] = []
                
                # Load public knowledge
                public_file = user_dir / "public.jsonl"
                if public_file.exists():
                    with open(public_file) as f:
                        for line in f:
                            if line.strip():
                                item = json.loads(line)
                                self.items[user].append(KnowledgeItem(**item))
                
                # Load private knowledge
                private_file = user_dir / "private.jsonl"
                if private_file.exists():
                    with open(private_file) as f:
                        for line in f:
                            if line.strip():
                                item = json.loads(line)
                                self.items[user].append(KnowledgeItem(**item))
    
    def save(self):
        """Save knowledge to filesystem"""
        for user, items in self.items.items():
            user_dir = self.base_path / user
            user_dir.mkdir(parents=True, exist_ok=True)
            
            # Separate public and private items
            public_items = [item for item in items if item.visibility == "public"]
            private_items = [item for item in items if item.visibility == "private"]
            
            # Save public items
            with open(user_dir / "public.jsonl", "w") as f:
                for item in public_items:
                    f.write(json.dumps(item.__dict__, ensure_ascii=False) + "\n")
            
            # Save private items
            with open(user_dir / "private.jsonl", "w") as f:
                for item in private_items:
                    f.write(json.dumps(item.__dict__, ensure_ascii=False) + "\n")
    
    def get_by_user(self, user: str) -> List[KnowledgeItem]:
        """Get all knowledge for a user"""
        return self.items.get(user, [])
    
    def get_public_by_user(self, user: str) -> List[KnowledgeItem]:
        """Get public knowledge for a user"""
        items = self.items.get(user, [])
        return [item for item in items if item.visibility == "public"]
    
    def get_all(self) -> List[KnowledgeItem]:
        """Get all knowledge"""
        result = []
        for items in self.items.values():
            result.extend(items)
        return result
    
    def add(self, item: KnowledgeItem) -> KnowledgeItem:
        """Add a knowledge item"""
        if item.user not in self.items:
            self.items[item.user] = []
        self.items[item.user].append(item)
        self.save()
        return item
    
    def list_users(self) -> List[str]:
        """List all users with knowledge"""
        return list(self.items.keys())

class PrivacyContext:
    """Context-based knowledge access control"""
    
    def __init__(self, channel: ChannelInfo, config: Dict, store: KnowledgeStore):
        self.channel = channel
        self.config = config
        self.store = store
    
    @property
    def is_private(self) -> bool:
        return self.channel.is_private
    
    @property
    def participants(self) -> Set[str]:
        return self.channel.participants
    
    def get_accessible_knowledge(self) -> List[KnowledgeItem]:
        """Get knowledge accessible in current context"""
        if not self.config.get("enabled", True):
            return self.store.get_all()
        
        if self.is_private:
            user = list(self.participants)[0]
            return self.store.get_by_user(user)
        else:
            result = []
            for user in self.participants:
                result.extend(self.store.get_public_by_user(user))
            return result
    
    def can_access_item(self, item: KnowledgeItem) -> bool:
        """Check if item is accessible in current context"""
        if not self.config.get("enabled", True):
            return True
        
        if self.is_private:
            user = list(self.participants)[0]
            return item.user == user
        else:
            return item.user in self.participants and item.visibility == "public"
    
    def filter_memory_results(self, results: List[Dict]) -> List[Dict]:
        """Filter memory search results"""
        if not self.config.get("enabled", True):
            return results
        
        accessible_paths = set()
        if self.is_private:
            user = list(self.participants)[0]
            accessible_paths.add(f"{user}/public.jsonl")
            accessible_paths.add(f"{user}/private.jsonl")
        else:
            for user in self.participants:
                accessible_paths.add(f"{user}/public.jsonl")
        
        return [r for r in results if r.get("path", "") in accessible_paths]
    
    def get_context_summary(self) -> str:
        """Get summary for injection into session prompt"""
        if not self.config.get("enabled", True):
            return "[Privacy] Disabled"
        
        if self.is_private:
            user = list(self.participants)[0]
            return f"[Privacy] Private chat (user: {user}) - Access to all knowledge"
        else:
            users = ", ".join(sorted(self.participants))
            return f"[Privacy] Group chat (participants: {users}) - Only public knowledge accessible"

class PrivacyReviewer:
    """Output review for privacy violations"""
    
    def __init__(self, config: Dict, store: KnowledgeStore):
        self.config = config
        self.store = store
        self.patterns = self.load_patterns()
    
    def load_patterns(self) -> Dict:
        """Load privacy detection patterns"""
        return {
            "calendar": {
                "description": "Schedule/calendar information",
                "patterns": [
                    r"明天.*[去见约]",
                    r"今天.*[去见约]",
                    r"昨天.*[去见约]",
                    r"\d{1,2}[:.]\d{2}.*[去见约到]",
                    r"(上午|下午|晚上|早上)\d{1,2}[点时]",
                    r"日程|行程|安排|预约|航班",
                    r"schedule|appointment|meeting at",
                ],
            },
            "finance": {
                "description": "Financial information",
                "patterns": [
                    r"工资|薪水|月薪|年薪|收入",
                    r"投资.*\d|账户.*余额|信用卡.*\d",
                    r"salary|income|balance|investment.*\$",
                ],
            },
            "contact_private": {
                "description": "Private contact information",
                "patterns": [
                    r"\d{8,11}",  # phone numbers
                    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # email
                    r"住在|地址[是为]|家在",
                ],
            },
        }
    
    def review(self, message: str, channel_type: str, participants: Set[str]) -> ReviewResult:
        """Review message for privacy violations"""
        review_config = self.config.get("review", {})
        if not review_config.get("enabled", True):
            return ReviewResult(passed=True, message=message)
        
        if len(participants) <= 1:
            return ReviewResult(passed=True, message=message)
        
        violations = self._check_patterns(message)
        
        if violations:
            return ReviewResult(
                passed=False,
                violations=violations,
                suggestion="Message contains private information, please rewrite"
            )
        
        return ReviewResult(passed=True, message=message)
    
    def _check_patterns(self, message: str) -> List[Violation]:
        """Check message against privacy patterns"""
        violations = []
        always_private = self.config.get("defaults", {}).get("always_private_categories", [])
        
        for category, data in self.patterns.items():
            if category not in always_private:
                continue
            
            for pattern in data.get("patterns", []):
                try:
                    match = re.search(pattern, message, re.IGNORECASE)
                    if match:
                        violations.append(Violation(
                            category=category,
                            matched=match.group(),
                            description=f"Detected {data.get('description', category)} information"
                        ))
                        break
                except re.error:
                    continue
        
        return violations

# Plugin implementation
class PrivacyGuardPlugin:
    """OpenClaw Privacy Guard Plugin"""
    
    def __init__(self):
        self.id = "privacy-guard"
        self.name = "Privacy Guard"
        self.description = "Multi-user privacy isolation framework"
        self.config = DEFAULT_CONFIG
        self.store = None
        self.reviewer = None
        self.contexts = {}  # channel_id -> PrivacyContext
    
    def setup(self, config: Optional[Dict] = None):
        """Setup plugin with configuration"""
        if config:
            self.config.update(config)
        
        # Initialize knowledge store
        kb_config = self.config.get("knowledge_base", {})
        self.store = KnowledgeStore(kb_config.get("path", "./privacy/knowledge"))
        
        # Initialize reviewer
        self.reviewer = PrivacyReviewer(self.config, self.store)
        
        return self
    
    def on_session_init(self, session: Dict) -> Dict:
        """Handle session initialization"""
        channel_id = session.get("channel_id", "")
        participants = set(session.get("participants", []))
        channel_type = "dm" if len(participants) <= 1 else "group"
        
        channel_info = ChannelInfo(
            channel_id=channel_id,
            participants=participants,
            channel_type=channel_type
        )
        
        context = PrivacyContext(channel_info, self.config, self.store)
        self.contexts[channel_id] = context
        
        # Inject privacy context into session
        summary = context.get_context_summary()
        session["privacy_context"] = summary
        
        return session
    
    def on_before_send_message(self, message: str, session: Dict) -> str:
        """Review message before sending"""
        channel_id = session.get("channel_id", "")
        context = self.contexts.get(channel_id)
        
        if not context or context.is_private:
            return message
        
        result = self.reviewer.review(
            message,
            context.channel.channel_type,
            context.participants
        )
        
        if not result.passed and self.config.get("review", {}).get("block_on_violation", True):
            raise ValueError(f"Privacy violation: {result.violations}")
        
        return message
    
    def on_memory_search(self, results: List[Dict], session: Dict) -> List[Dict]:
        """Filter memory search results"""
        channel_id = session.get("channel_id", "")
        context = self.contexts.get(channel_id)
        
        if not context:
            return results
        
        return context.filter_memory_results(results)
    
    def on_file_read(self, path: str, session: Dict) -> Dict:
        """Check file read permissions"""
        channel_id = session.get("channel_id", "")
        context = self.contexts.get(channel_id)
        
        if not context:
            return {"allow": True}
        
        # Check if file is in privacy knowledge directory
        kb_path = self.config.get("knowledge_base", {}).get("path", "./privacy/knowledge")
        if kb_path in path:
            parts = path.split("/")
            try:
                user_index = parts.index("knowledge") + 1
                user = parts[user_index]
                is_private = path.endswith("private.jsonl")
                
                if is_private and not context.is_private:
                    return {"allow": False, "reason": "Private knowledge not accessible in group chat"}
                
                if user not in context.participants:
                    return {"allow": False, "reason": "Knowledge belongs to non-participant user"}
            except (ValueError, IndexError):
                pass
        
        return {"allow": True}
    
    # Tool implementations
    def get_privacy_context(self, session: Dict) -> Dict:
        """Get current privacy context"""
        channel_id = session.get("channel_id", "")
        context = self.contexts.get(channel_id)
        
        if not context:
            return {"error": "No privacy context for current session"}
        
        return {
            "is_private": context.is_private,
            "participants": list(context.participants),
            "accessible_knowledge": [
                {
                    "id": item.id,
                    "user": item.user,
                    "content": item.content[:100] + "..." if len(item.content) > 100 else item.content,
                    "visibility": item.visibility,
                    "category": item.category,
                }
                for item in context.get_accessible_knowledge()
            ],
            "summary": context.get_context_summary(),
        }
    
    def review_message(self, message: str, channel_type: str, participants: List[str]) -> Dict:
        """Review a message for privacy violations"""
        result = self.reviewer.review(message, channel_type, set(participants))
        
        return {
            "passed": result.passed,
            "violations": [
                {
                    "category": v.category,
                    "matched": v.matched,
                    "description": v.description,
                }
                for v in result.violations
            ],
            "suggestion": result.suggestion,
        }
    
    def add_knowledge(self, user: str, content: str, category: str, 
                     visibility: Optional[str] = None, source: Optional[str] = None) -> Dict:
        """Add knowledge item"""
        item = KnowledgeItem(
            id=f"k_{uuid.uuid4().hex[:12]}",
            user=user,
            content=content,
            visibility=visibility or self.config.get("defaults", {}).get("visibility", "private"),
            category=category,
            source=source or "manual",
            created=datetime.now().isoformat(),
        )
        
        self.store.add(item)
        
        return {
            "success": True,
            "item": {
                "id": item.id,
                "user": item.user,
                "content": item.content,
                "visibility": item.visibility,
                "category": item.category,
                "source": item.source,
                "created": item.created,
            },
        }

# Plugin factory function
def create_plugin():
    """Create and return plugin instance"""
    return PrivacyGuardPlugin()