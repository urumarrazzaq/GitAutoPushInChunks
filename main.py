import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

# ============================= #
# 🚀 Function to get folder size #
# ============================= #
def get_folder_size(folder):
    total_size = 0
    for dirpath, _, filenames in os.walk(folder):
        if ".git" in dirpath:  
            continue
        for file in filenames:
            filepath = os.path.join(dirpath, file)
            if os.path.isfile(filepath):
                total_size += os.path.getsize(filepath)
    return total_size

# ============================= #
# 🔄 Log Message Function #
# ============================= #
def log_message(message, color="black"):
    log_text.tag_config("black", foreground="black")
    log_text.tag_config("green", foreground="green")
    log_text.tag_config("red", foreground="red")
    log_text.tag_config("yellow", foreground="orange")
    log_text.tag_config("blue", foreground="blue")

    symbol = message[:2]  # First two characters
    rest_of_text = message[2:]  # Everything after the first two characters

    log_text.insert(tk.END, symbol, color)
    log_text.insert(tk.END, rest_of_text + "\n", "black")
    log_text.yview(tk.END)
    root.update()

# ============================= #
# 🛑 Stop Push Process #
# ============================= #
stop_push = False

def stop_push_process():
    global stop_push
    stop_push = True
    log_message("❌ Stopping push process...", "red")

# ============================= #
# 📜 Copy Logs Function #
# ============================= #
def copy_logs():
    root.clipboard_clear()
    root.clipboard_append(log_text.get("1.0", tk.END))
    root.update()
    messagebox.showinfo("Copied", "Logs copied to clipboard!")

# ============================= #
# ➕ Add Folder to Ignore List #
# ============================= #
def add_folder_to_ignore():
    folder = filedialog.askdirectory()
    if folder and folder not in ignored_listbox.get(0, tk.END):
        ignored_listbox.insert(tk.END, folder)

# ============================= #
# ❌ Remove Selected Folder (With Confirmation) #
# ============================= #
def remove_selected_folder():
    selected_indices = ignored_listbox.curselection()
    
    if not selected_indices:
        messagebox.showwarning("No Selection", "Please select a folder to remove.")
        return

    confirmation = messagebox.askyesno("Confirm Removal", "Are you sure you want to remove the selected folder(s) from the ignore list?")
    if confirmation:
        for index in reversed(selected_indices):
            ignored_listbox.delete(index)

# ============================= #
# 🚀 Push function (Updated) #
# ============================= #
def push_folder(folder_path, repo_path, chunk_size_mb):
    global stop_push
    if stop_push:
        return

    folder_size_mb = get_folder_size(folder_path) / (1024 * 1024)

    if folder_size_mb > chunk_size_mb:
        log_message(f"🔍 Large Folder Detected: {folder_path} ({folder_size_mb:.2f} MB) - Checking Subfolders", "blue")
        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            if os.path.isdir(item_path):
                push_folder(item_path, repo_path, chunk_size_mb)
            elif os.path.isfile(item_path):
                file_size_mb = os.path.getsize(item_path) / (1024 * 1024)
                if file_size_mb > chunk_size_mb:
                    log_message(f"⚠️ Skipping Large File: {item_path} ({file_size_mb:.2f} MB)", "yellow")
                else:
                    try:
                        commit_msg = f"Added {item} from {folder_path.replace(repo_path, '').replace('\\', '/')}"
                        subprocess.run(["git", "add", item_path], cwd=repo_path, check=True)
                        subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_path, check=True)
                        subprocess.run(["git", "push", "origin", "main"], cwd=repo_path, check=True)
                        log_message(f"✅ Pushed: {item_path}", "green")
                    except subprocess.CalledProcessError as e:
                        log_message(f"❌ Failed: {item_path} - {str(e)}", "red")
    else:
        try:
            commit_msg = f"Added folder {folder_path.replace(repo_path, '').replace('\\', '/')}"
            subprocess.run(["git", "add", folder_path], cwd=repo_path, check=True)
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_path, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=repo_path, check=True)
            log_message(f"✅ Pushed Folder: {folder_path}", "green")
        except subprocess.CalledProcessError as e:
            log_message(f"❌ Failed: {folder_path} - {str(e)}", "red")

def push_project_in_chunks():
    global stop_push
    stop_push = False  
    start_button.config(state=tk.DISABLED)  
    stop_button.config(state=tk.NORMAL)  

    repo_path = folder_path.get()
    repo_url = repo_url_entry.get()
    chunk_size_mb = int(chunk_size_entry.get())

    if not repo_path or not repo_url:
        messagebox.showerror("Error", "Please select a project folder and enter a GitHub repository URL.")
        start_button.config(state=tk.NORMAL)
        stop_button.config(state=tk.DISABLED)
        return

    log_text.delete("1.0", tk.END)  

    subprocess.run(["git", "rm", "-f", ".git/index.lock"], cwd=repo_path, check=False)

    ignored_folders_list = [ignored_listbox.get(i) for i in range(ignored_listbox.size())]

    if not os.path.exists(os.path.join(repo_path, ".git")):
        subprocess.run(["git", "init"], cwd=repo_path)
        subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=repo_path)

    for dirpath, _, _ in os.walk(repo_path):
        if stop_push:
            log_message("\n❌ Push process stopped!", "red")
            break

        if ".git" in dirpath or any(dirpath.startswith(folder) for folder in ignored_folders_list):
            log_message(f"⚠️ Skipping: {dirpath}", "yellow")
            continue

        push_folder(dirpath, repo_path, chunk_size_mb)

    if not stop_push:
        log_message("\n✅ Push Process Completed!", "blue")

    start_button.config(state=tk.NORMAL)
    stop_button.config(state=tk.DISABLED)

# ============================= #
# 🎨 UI Setup #
# ============================= #
root = tk.Tk()
root.title("Git Auto Push In Chunks")
root.geometry("800x600")
root.resizable(True, True)

root.columnconfigure(1, weight=1)
root.rowconfigure(5, weight=1)

# 📁 Project Folder Selection
tk.Label(root, text="Project Folder:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
folder_path = tk.StringVar()
folder_entry = tk.Entry(root, textvariable=folder_path, width=50)
folder_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
tk.Button(root, text="Browse", command=lambda: folder_path.set(filedialog.askdirectory())).grid(row=0, column=2, padx=5, pady=5)

# 🔗 GitHub Repo URL
tk.Label(root, text="GitHub Repo URL:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
repo_url_entry = tk.Entry(root, width=50)
repo_url_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

# 📦 Chunk Size
tk.Label(root, text="Chunk Size (MB):").grid(row=2, column=0, sticky="w", padx=10, pady=5)
chunk_size_entry = tk.Entry(root, width=10)
chunk_size_entry.grid(row=2, column=1, sticky="w", padx=5, pady=5)
chunk_size_entry.insert(0, "25")

# 🚫 Ignored Folders
tk.Label(root, text="Ignored Folders:").grid(row=3, column=0, sticky="w", padx=10, pady=5)
ignored_listbox = tk.Listbox(root, height=5, selectmode=tk.MULTIPLE)
ignored_listbox.grid(row=3, column=1, sticky="ew", padx=5, pady=5)

ignore_button_frame = tk.Frame(root)
ignore_button_frame.grid(row=3, column=2, padx=5, pady=5, sticky="w")
tk.Button(ignore_button_frame, text="➕ Add", command=add_folder_to_ignore).pack(side=tk.TOP, padx=2, pady=2)
tk.Button(ignore_button_frame, text="❌ Remove", command=remove_selected_folder).pack(side=tk.TOP, padx=2, pady=2)

# 🚀 Buttons Frame (Centered)
button_frame = tk.Frame(root)
button_frame.grid(row=4, column=0, columnspan=3, pady=10)

start_button = tk.Button(button_frame, text="🚀 Start", command=push_project_in_chunks, width=12, bg="green", fg="white" , disabledforeground="#555555")
stop_button = tk.Button(button_frame, text="🛑 Stop", command=stop_push_process, state=tk.DISABLED, width=12, bg="red", fg="white", disabledforeground="#555555")
copy_logs_button = tk.Button(button_frame, text="📋 Copy Logs", command=copy_logs, width=12, bg="blue", fg="white")

start_button.pack(side=tk.LEFT, padx=10)
stop_button.pack(side=tk.LEFT, padx=10)
copy_logs_button.pack(side=tk.LEFT, padx=10)

log_text = scrolledtext.ScrolledText(root, width=90, height=20)
log_text.grid(row=5, column=0, columnspan=3, sticky="nsew", padx=10, pady=5)

root.mainloop()