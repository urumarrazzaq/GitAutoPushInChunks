import os
import subprocess
import time
from datetime import datetime

# =============================== #
# 🚀 Function to get folder size  #
# =============================== #
def get_folder_size(folder):
    total_size = 0
    for dirpath, _, filenames in os.walk(folder):
        for file in filenames:
            filepath = os.path.join(dirpath, file)
            if os.path.isfile(filepath):
                total_size += os.path.getsize(filepath)
    return total_size

# =============================== #
# 🗂️ Function to count total files #
# =============================== #
def count_files(folder):
    total_files = 0
    for _, _, files in os.walk(folder):
        total_files += len(files)
    return total_files

# =============================== #
# 📝 Write logs to a report file  #
# =============================== #
def write_report(report_path, content):
    with open(report_path, "a", encoding="utf-8") as f:
        f.write(content + "\n")

# =============================== #
# 🚀 Push files in chunks         #
# =============================== #
def push_project_in_chunks(repo_path, repo_url, chunk_size_mb=25):
    report_file = os.path.join(repo_path, "push_report.txt")
    if os.path.exists(report_file):
        os.remove(report_file)  # Clear previous report

    total_files = count_files(repo_path)
    total_size_mb = get_folder_size(repo_path) / (1024 * 1024)
    estimated_pushes = int(total_size_mb / chunk_size_mb) + 1
    estimated_time = estimated_pushes * 30  # Assuming 30 sec per push

    # 📝 Log Initial Report
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    initial_report = f"""
📁 Project: {repo_path}
🗂️ Total Files: {total_files}
📦 Estimated Pushes: {estimated_pushes}
⏳ Estimated Time: {estimated_time // 60} min {estimated_time % 60} sec
🕒 Start Time: {start_time}
"""
    print(initial_report)
    write_report(report_file, initial_report)

    failed_files = []

    # 🔄 Initialize Git Repo if not exists
    if not os.path.exists(os.path.join(repo_path, ".git")):
        subprocess.run(["git", "init"], cwd=repo_path)
        subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=repo_path)

    # 🚀 Iterate through subfolders and push in chunks
    for dirpath, _, filenames in os.walk(repo_path):
        folder_size_mb = get_folder_size(dirpath) / (1024 * 1024)

        if folder_size_mb > chunk_size_mb:
            continue  # Skip large folders

        for file in filenames:
            file_path = os.path.join(dirpath, file)
            try:
                subprocess.run(["git", "add", file_path], cwd=repo_path, check=True)
                commit_msg = f"Added {file} from {dirpath.replace(repo_path, '')}"
                subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_path, check=True)
                subprocess.run(["git", "push", "origin", "main"], cwd=repo_path, check=True)
                print(f"✅ Pushed: {file_path}")

            except subprocess.CalledProcessError as e:
                error_msg = f"❌ Failed: {file_path} - {str(e)}"
                print(error_msg)
                failed_files.append(error_msg)

    # 📜 Log Failed Files
    if failed_files:
        write_report(report_file, "\n❌ Failed Files:\n" + "\n".join(failed_files))

    # 🏁 Final Report
    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    final_report = f"""
✅ Push Process Completed!
🕒 End Time: {end_time}
📂 Report saved at: {report_file}
"""
    print(final_report)
    write_report(report_file, final_report)

# =============================== #
# 🏁 Run Script                   #
# =============================== #
if __name__ == "__main__":
    repo_path = input("Enter the path to your main project folder: ")
    repo_url = input("Enter your GitHub repository URL: ")
    push_project_in_chunks(repo_path, repo_url)
