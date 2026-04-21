import os

file_path = r"backend/core/llm_router.py"
with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'raise ValueError("No content returned from LLM for complex task.")' in line:
        indent = line[:line.find('raise')]
        new_lines.append(f'{indent}logger.error(f"LLM returned empty content. Raw response: {{response.model_dump()}}")\n')
        new_lines.append(line)
    else:
        new_lines.append(line)

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("File updated successfully.")
