"""
Data redaction utilities for sensitive information handling.
"""

import re
from typing import Any, Dict, List, Optional, Pattern, Union, Callable
from dataclasses import dataclass
import json


@dataclass
class RedactionRule:
    """A rule for redacting sensitive data."""
    name: str
    pattern: Pattern[str]
    replacement: str = "[REDACTED]"
    field_names: Optional[List[str]] = None  # Specific field names to apply to


class RedactionManager:
    """
    Manager for handling sensitive data redaction.
    """
    
    def __init__(self):
        self.rules: List[RedactionRule] = []
        self._setup_default_rules()
    
    def _setup_default_rules(self) -> None:
        """Set up default redaction rules for common sensitive data."""
        
        # Email addresses
        self.add_rule(
            "email",
            re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            "[EMAIL]"
        )
        
        # Phone numbers (US format)
        self.add_rule(
            "phone",
            re.compile(r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'),
            "[PHONE]"
        )
        
        # Credit card numbers (basic pattern)
        self.add_rule(
            "credit_card",
            re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3[0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b'),
            "[CREDIT_CARD]"
        )
        
        # Social Security Numbers
        self.add_rule(
            "ssn",
            re.compile(r'\b(?!000|666|9\d{2})\d{3}[-.\s]?(?!00)\d{2}[-.\s]?(?!0000)\d{4}\b'),
            "[SSN]"
        )
        
        # API Keys (common patterns)
        self.add_rule(
            "api_key",
            re.compile(r'\b[A-Za-z0-9]{32,}\b'),
            "[API_KEY]",
            field_names=["api_key", "apikey", "key", "token", "secret", "password", "auth"]
        )
        
        # URLs with potential sensitive info
        self.add_rule(
            "sensitive_url",
            re.compile(r'https?://[^\s]*(?:token|key|password|secret)=[^\s&]+'),
            "[SENSITIVE_URL]"
        )
        
        # IP addresses
        self.add_rule(
            "ip_address",
            re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'),
            "[IP_ADDRESS]"
        )
    
    def add_rule(
        self, 
        name: str, 
        pattern: Union[str, Pattern[str]], 
        replacement: str = "[REDACTED]",
        field_names: Optional[List[str]] = None
    ) -> None:
        """
        Add a redaction rule.
        
        Args:
            name: Name of the rule
            pattern: Regex pattern (string or compiled)
            replacement: Replacement text
            field_names: Field names this rule applies to (None = all fields)
        """
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        
        rule = RedactionRule(
            name=name,
            pattern=pattern,
            replacement=replacement,
            field_names=field_names
        )
        self.rules.append(rule)
    
    def remove_rule(self, name: str) -> bool:
        """
        Remove a redaction rule by name.
        
        Args:
            name: Name of the rule to remove
            
        Returns:
            True if rule was found and removed, False otherwise
        """
        for i, rule in enumerate(self.rules):
            if rule.name == name:
                del self.rules[i]
                return True
        return False
    
    def redact_text(self, text: str, field_name: Optional[str] = None) -> str:
        """
        Redact sensitive information from text.
        
        Args:
            text: Text to redact
            field_name: Name of the field (for field-specific rules)
            
        Returns:
            Redacted text
        """
        if not text:
            return text
        
        result = text
        
        for rule in self.rules:
            # Check if rule applies to this field
            if rule.field_names and field_name:
                if field_name.lower() not in [fn.lower() for fn in rule.field_names]:
                    continue
            
            # Apply redaction
            result = rule.pattern.sub(rule.replacement, result)
        
        return result
    
    def redact_dict(self, data: Dict[str, Any], recursive: bool = True) -> Dict[str, Any]:
        """
        Redact sensitive information from a dictionary.
        
        Args:
            data: Dictionary to redact
            recursive: Whether to recursively redact nested structures
            
        Returns:
            Dictionary with redacted values
        """
        if not isinstance(data, dict):
            return data
        
        result = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.redact_text(value, key)
            elif isinstance(value, dict) and recursive:
                result[key] = self.redact_dict(value, recursive)
            elif isinstance(value, list) and recursive:
                result[key] = self.redact_list(value, recursive)
            else:
                result[key] = value
        
        return result
    
    def redact_list(self, data: List[Any], recursive: bool = True) -> List[Any]:
        """
        Redact sensitive information from a list.
        
        Args:
            data: List to redact
            recursive: Whether to recursively redact nested structures
            
        Returns:
            List with redacted values
        """
        if not isinstance(data, list):
            return data
        
        result = []
        
        for item in data:
            if isinstance(item, str):
                result.append(self.redact_text(item))
            elif isinstance(item, dict) and recursive:
                result.append(self.redact_dict(item, recursive))
            elif isinstance(item, list) and recursive:
                result.append(self.redact_list(item, recursive))
            else:
                result.append(item)
        
        return result
    
    def redact_json(self, json_str: str) -> str:
        """
        Redact sensitive information from JSON string.
        
        Args:
            json_str: JSON string to redact
            
        Returns:
            JSON string with redacted values
        """
        try:
            data = json.loads(json_str)
            redacted_data = self.redact_dict(data) if isinstance(data, dict) else self.redact_list(data)
            return json.dumps(redacted_data, indent=2)
        except json.JSONDecodeError:
            # If not valid JSON, treat as plain text
            return self.redact_text(json_str)
    
    def is_sensitive_field(self, field_name: str) -> bool:
        """
        Check if a field name is considered sensitive.
        
        Args:
            field_name: Field name to check
            
        Returns:
            True if field is considered sensitive
        """
        sensitive_keywords = [
            "password", "passwd", "pwd", "secret", "token", "key", "api_key",
            "apikey", "auth", "authorization", "credential", "ssn", "social",
            "credit", "card", "phone", "email", "address", "ip"
        ]
        
        field_lower = field_name.lower()
        return any(keyword in field_lower for keyword in sensitive_keywords)


# Global redaction manager instance
_default_manager = RedactionManager()


def redact_sensitive_data(
    data: Union[str, Dict[str, Any], List[Any]],
    field_name: Optional[str] = None,
    manager: Optional[RedactionManager] = None
) -> Union[str, Dict[str, Any], List[Any]]:
    """
    Convenience function for redacting sensitive data.
    
    Args:
        data: Data to redact (string, dict, or list)
        field_name: Field name for context-specific redaction
        manager: Custom redaction manager (uses default if None)
        
    Returns:
        Redacted data
    """
    redactor = manager or _default_manager
    
    if isinstance(data, str):
        return redactor.redact_text(data, field_name)
    elif isinstance(data, dict):
        return redactor.redact_dict(data)
    elif isinstance(data, list):
        return redactor.redact_list(data)
    else:
        return data


def add_redaction_rule(
    name: str,
    pattern: Union[str, Pattern[str]],
    replacement: str = "[REDACTED]",
    field_names: Optional[List[str]] = None
) -> None:
    """
    Add a redaction rule to the global manager.
    
    Args:
        name: Name of the rule
        pattern: Regex pattern
        replacement: Replacement text
        field_names: Field names this rule applies to
    """
    _default_manager.add_rule(name, pattern, replacement, field_names)
