import os
db_path = r"d:\DEV\repositories\git\taleweaver\data\taleweaver.db"
print("File exists:", os.path.exists(db_path))
if os.path.exists(db_path):
    print("File size:", os.path.getsize(db_path))
    # list directory contents
    print("Dir files:", os.listdir(os.path.dirname(db_path)))
