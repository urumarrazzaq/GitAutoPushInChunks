import os
import subprocess
import time
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

# ============================= #
# 🚀 Function to get folder size #
# ============================= #
def get_folder_size(folder):
    total_size = 0
    for dirpath, _, filenames in os.walk(folder):
        for file in filenames:
            filepath = os.path.join(dirpath, file)
            if os.path.isfile(filepath):
                total_size += os.path.getsize(filepath)
    return total_size

# ============================= #
# 🗂️ Function to count files      #
# ============================= #
def count_files(folder):
    total_files = 0
    for _, _, files in os.walk(folder):
        total_files += len(files)
    return total_files

# ============================= #
# 🎨 Log Message with Colors    #
# ============================= #
def log_message(msg, color="black"):
    log_text.insert(tk.END, msg + "\n")
    log_text.tag_add(color, "end-2l", "end-1l")
    log_text.tag_config("red", foreground="red")
    log_text.tag_config("yellow", foreground="orange")
    log_text.tag_config("green", foreground="green")
    log_text.yview(tk.END)
    root.update()

# ============================= #
# 📂 Function to Select Folders #
# ============================= #
def select_folders_to_ignore():
    selected_folder = filedialog.askdirectory()
    if selected_folder:
        current_folders = ignored_folders_listbox.get(0, tk.END)
        if selected_folder not in current_folders:
            ignored_folders_listbox.insert(tk.END, selected_folder)

# ============================= #
# 🚀 Push Project in Chunks     #
# ============================= #
def push_project_in_chunks():
    start_push_btn.config(state=tk.DISABLED)  # Disable button
    repo_path = folder_path.get()
    repo_url = repo_url_entry.get()
    chunk_size_mb = int(chunk_size_entry.get())

    if not repo_path or not repo_url:
        messagebox.showerror("Error", "Please select a project folder and enter a GitHub repository URL.")
        start_push_btn.config(state=tk.NORMAL)
        return

    log_text.delete("1.0", tk.END)  # Clear log
    report_file = os.path.join(repo_path, "push_report.txt")

    # 📊 Calculate stats
    total_files = count_files(repo_path)
    total_size_mb = get_folder_size(repo_path) / (1024 * 1024)
    estimated_pushes = int(total_size_mb / chunk_size_mb) + 1
    estimated_time = estimated_pushes * 30  # Assuming 30 sec per push

    # 📝 Log Summary
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message(f"""
📁 Project: {repo_path}
🗂️ Total Files: {total_files}
📦 Estimated Pushes: {estimated_pushes}
⏳ Estimated Time: {estimated_time // 60} min {estimated_time % 60} sec
🕒 Start Time: {start_time}
""", "black")

    failed_files = []
    ignored_folders_list = ignored_folders_listbox.get(0, tk.END)

    # 🔄 Initialize Git Repo if not exists
    if not os.path.exists(os.path.join(repo_path, ".git")):
        subprocess.run(["git", "init"], cwd=repo_path)
        subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=repo_path)

    # 🚀 Push Files and Folders in Chunks
    for dirpath, dirnames, filenames in os.walk(repo_path):
        if ".git" in dirpath or any(dirpath.startswith(ignored) for ignored in ignored_folders_list):
            log_message(f"⚠️ Skipping: {dirpath}", "yellow")
            continue  

        folder_size_mb = get_folder_size(dirpath) / (1024 * 1024)

        if folder_size_mb <= chunk_size_mb:
            # ✅ Push entire folder
            try:
                subprocess.run(["git", "add", dirpath], cwd=repo_path, check=True)
                commit_msg = f"Added {dirpath.replace(repo_path, '')}"
                subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_path, check=True)
                subprocess.run(["git", "push", "origin", "main"], cwd=repo_path, check=True)
                log_message(f"✅ Pushed Folder: {dirpath} ({folder_size_mb:.2f} MB)", "green")
                continue  # Skip file-by-file processing
            except subprocess.CalledProcessError as e:
                log_message(f"❌ Failed to push folder {dirpath} - {str(e)}", "red")

        # 🔍 If folder is too large, push files one by one
        for file in filenames:
            file_path = os.path.join(dirpath, file)
            try:
                subprocess.run(["git", "add", file_path], cwd=repo_path, check=True)
                commit_msg = f"Added {file} from {dirpath.replace(repo_path, '')}"
                subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_path, check=True)
                subprocess.run(["git", "push", "origin", "main"], cwd=repo_path, check=True)
                log_message(f"✅ Pushed File: {file_path}", "green")
            except subprocess.CalledProcessError as e:
                error_msg = f"❌ Failed: {file_path} - {str(e)}"
                log_message(error_msg, "red")
                failed_files.append(error_msg)

    # 📜 Log Failed Files
    if failed_files:
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("\n❌ Failed Files:\n" + "\n".join(failed_files))
        log_message("\nSome files failed to push. Check push_report.txt\n", "red")

    # 🏁 Final Report
    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message(f"✅ Push Process Completed!\n🕒 End Time: {end_time}", "green")
    start_push_btn.config(state=tk.NORMAL)  # Re-enable button

# ============================= #
# 🎨 UI Setup                    #
# ============================= #
root = tk.Tk()
root.title("Git Auto Pusher")
root.geometry("750x600")  # Increased size

# Project Folder Selection
tk.Label(root, text="Project Folder:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
folder_path = tk.StringVar()
tk.Entry(root, textvariable=folder_path, width=50).grid(row=0, column=1, padx=5, pady=5)
tk.Button(root, text="Browse", command=lambda: folder_path.set(filedialog.askdirectory())).grid(row=0, column=2, padx=5, pady=5)

# GitHub Repo URL
tk.Label(root, text="GitHub Repo URL:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
repo_url_entry = tk.Entry(root, width=50)
repo_url_entry.grid(row=1, column=1, padx=5, pady=5)

# Chunk Size
tk.Label(root, text="Chunk Size (MB):").grid(row=2, column=0, sticky="w", padx=10, pady=5)
chunk_size_entry = tk.Entry(root, width=10)
chunk_size_entry.grid(row=2, column=1, sticky="w", padx=5, pady=5)
chunk_size_entry.insert(0, "25")

# Ignore Folders Selection
tk.Label(root, text="Ignore Folders:").grid(row=3, column=0, sticky="w", padx=10, pady=5)
ignored_folders_listbox = tk.Listbox(root, height=5, width=50)
ignored_folders_listbox.grid(row=3, column=1, padx=5, pady=5)
tk.Button(root, text="Select Folder", command=select_folders_to_ignore).grid(row=3, column=2, padx=5, pady=5)

# Push Button
start_push_btn = tk.Button(root, text="Start Push", command=push_project_in_chunks, bg="green", fg="white", font=("Arial", 12, "bold"))
start_push_btn.grid(row=4, column=1, pady=10)

# Log Area
tk.Label(root, text="Progress Log:").grid(row=5, column=0, sticky="w", padx=10, pady=5)
log_text = scrolledtext.ScrolledText(root, width=80, height=20)
log_text.grid(row=6, column=0, columnspan=3, padx=10, pady=5)

root.mainloop()
