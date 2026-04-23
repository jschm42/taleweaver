import os

path = r'alembic\versions\b2f08f0d7ceb_separate_adventuretemplate_gamesession_.py'
with open(path, 'r') as f:
    lines = f.readlines()

new_lines = []
helper_added = False
for line in lines:
    if 'def upgrade() -> None:' in line and not helper_added:
        new_lines.append('def _drop_table_if_exists(table_name: str):\n')
        new_lines.append('    bind = op.get_bind()\n')
        new_lines.append('    inspector = sa.inspect(bind)\n')
        new_lines.append('    if table_name in inspector.get_table_names():\n')
        new_lines.append('        op.drop_table(table_name)\n\n\n')
        new_lines.append(line)
        helper_added = True
    elif "op.drop_table('" in line:
        new_lines.append(line.replace("op.drop_table('", "_drop_table_if_exists('"))
    elif 'op.drop_table("' in line:
        new_lines.append(line.replace('op.drop_table("', '_drop_table_if_exists("'))
    else:
        new_lines.append(line)

with open(path, 'w') as f:
    f.writelines(new_lines)
print("Migration script updated successfully.")
