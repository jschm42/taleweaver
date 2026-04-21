import os

file_path = r"backend/core/llm_router.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix the token budget logic in execute_complex_task and aexecute_complex_task
# We need to make sure max_tokens is the total of content + thinking
old_kwargs = '"max_tokens": self.max_tokens,'
new_kwargs = '"max_tokens": self.max_tokens + (self.max_thinking_tokens if self.enable_thinking else 0),'

content = content.replace(old_kwargs, new_kwargs)

# Also improve the error message for length finish reason
old_error = 'raise ValueError("No content returned from LLM for complex task. Check logs for raw response.")'
new_error = """if response.choices[0].finish_reason == "length":
                raise ValueError("LLM hit token limit during reasoning. Increase 'Max Tokens' in Settings.")
            raise ValueError("No content returned from LLM for complex task. Check logs for raw response.")"""

# This replacement might be tricky because of indentation and multiple occurrences
# Let's use a simpler replacement for the error strings first

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Router budget logic updated.")
