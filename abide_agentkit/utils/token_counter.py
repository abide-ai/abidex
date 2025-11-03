"""
Token counting utilities for tracking model usage.
"""

import re
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass


@dataclass
class TokenCount:
    """Token count result."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    
    def __add__(self, other: 'TokenCount') -> 'TokenCount':
        """Add two token counts together."""
        return TokenCount(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens
        )


class TokenCounter:
    """
    Token counter for various model providers and formats.
    
    This is a simplified implementation that provides rough estimates.
    For production use, consider integrating with tiktoken or similar libraries.
    """
    
    # Rough token-to-character ratios for different languages
    TOKEN_RATIOS = {
        "english": 4.0,  # ~4 characters per token for English
        "code": 3.5,     # Code tends to be more token-dense
        "default": 4.0
    }
    
    def __init__(self, model: Optional[str] = None):
        self.model = model
    
    def count_text(self, text: str, language: str = "default") -> int:
        """
        Count tokens in a text string using character-based estimation.
        
        Args:
            text: The text to count tokens for
            language: Language hint for better estimation
            
        Returns:
            Estimated token count
        """
        if not text:
            return 0
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Get ratio for language
        ratio = self.TOKEN_RATIOS.get(language, self.TOKEN_RATIOS["default"])
        
        # Estimate tokens
        char_count = len(text)
        token_estimate = max(1, int(char_count / ratio))
        
        return token_estimate
    
    def count_messages(self, messages: List[Dict[str, Any]]) -> TokenCount:
        """
        Count tokens in a list of chat messages.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            TokenCount object with input token estimate
        """
        total_tokens = 0
        
        for message in messages:
            # Count tokens in content
            content = message.get("content", "")
            if isinstance(content, str):
                total_tokens += self.count_text(content)
            elif isinstance(content, list):
                # Handle multimodal content
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        total_tokens += self.count_text(item.get("text", ""))
            
            # Add overhead for role and message structure
            role = message.get("role", "")
            total_tokens += len(role) // 4 + 3  # Role + message overhead
        
        return TokenCount(input_tokens=total_tokens, total_tokens=total_tokens)
    
    def count_completion(self, completion: str) -> TokenCount:
        """
        Count tokens in a completion/response.
        
        Args:
            completion: The completion text
            
        Returns:
            TokenCount object with output token estimate
        """
        output_tokens = self.count_text(completion)
        return TokenCount(output_tokens=output_tokens, total_tokens=output_tokens)
    
    def count_function_call(self, function_call: Dict[str, Any]) -> int:
        """
        Count tokens in a function call.
        
        Args:
            function_call: Function call dictionary
            
        Returns:
            Estimated token count
        """
        total_tokens = 0
        
        # Count function name
        name = function_call.get("name", "")
        total_tokens += len(name) // 4 + 1
        
        # Count arguments (usually JSON)
        arguments = function_call.get("arguments", "")
        if isinstance(arguments, str):
            total_tokens += self.count_text(arguments, "code")
        
        return total_tokens
    
    def extract_usage_from_response(self, response: Any) -> Optional[TokenCount]:
        """
        Extract token usage from various API response formats.
        
        Args:
            response: API response object
            
        Returns:
            TokenCount if usage info found, None otherwise
        """
        usage_data = None
        
        # Try different response formats
        if hasattr(response, 'usage'):
            usage_data = response.usage
        elif isinstance(response, dict):
            usage_data = response.get('usage')
        
        if not usage_data:
            return None
        
        # Extract token counts
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        
        if hasattr(usage_data, 'prompt_tokens'):
            input_tokens = usage_data.prompt_tokens
        elif isinstance(usage_data, dict):
            input_tokens = usage_data.get('prompt_tokens', 0)
        
        if hasattr(usage_data, 'completion_tokens'):
            output_tokens = usage_data.completion_tokens
        elif isinstance(usage_data, dict):
            output_tokens = usage_data.get('completion_tokens', 0)
        
        if hasattr(usage_data, 'total_tokens'):
            total_tokens = usage_data.total_tokens
        elif isinstance(usage_data, dict):
            total_tokens = usage_data.get('total_tokens', input_tokens + output_tokens)
        
        return TokenCount(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens or (input_tokens + output_tokens)
        )


# Global token counter instance
_default_counter = TokenCounter()


def count_tokens(
    text: Optional[str] = None,
    messages: Optional[List[Dict[str, Any]]] = None,
    completion: Optional[str] = None,
    model: Optional[str] = None
) -> TokenCount:
    """
    Convenience function for counting tokens.
    
    Args:
        text: Text to count (for simple text counting)
        messages: List of chat messages
        completion: Completion/response text
        model: Model name for better estimation
        
    Returns:
        TokenCount object
    """
    counter = TokenCounter(model) if model else _default_counter
    
    total_count = TokenCount()
    
    if text:
        tokens = counter.count_text(text)
        total_count += TokenCount(input_tokens=tokens, total_tokens=tokens)
    
    if messages:
        total_count += counter.count_messages(messages)
    
    if completion:
        total_count += counter.count_completion(completion)
    
    return total_count
