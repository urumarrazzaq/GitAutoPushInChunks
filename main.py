import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

# ============================= #
# 🚀 Function to get folder size #
# ============================= #
def get_folder_size(folder):
    total_size = 0
    for dirpath, _, filenames in os.walk(folder):
        if ".git" in dirpath:  # Ignore .git folder
            continue
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
    for dirpath, _, files in os.walk(folder):
        if ".git" in dirpath:  # Ignore .git folder
            continue
        total_files += len(files)
    return total_files

# ============================= #
# 🔄 Log Message Function (Symbol Color Only) #
# ============================= #
def log_message(message, symbol_color="black"):
    """
    Logs messages with only the first symbol colored.
    The rest of the text remains default black.
    """
    log_text.tag_config("black", foreground="black")
    log_text.tag_config("green", foreground="green")
    log_text.tag_config("red", foreground="red")
    log_text.tag_config("yellow", foreground="orange")
    log_text.tag_config("blue", foreground="blue")

    # Extract the first character (symbol) and the rest of the message
    symbol = message[:2]  # First two characters (e.g., "✅ ", "❌ ", "⚠️ ")
    rest_of_text = message[2:]  # Everything after the first two characters

    # Insert the symbol with color
    log_text.insert(tk.END, symbol, symbol_color)
    # Insert the rest of the text in black
    log_text.insert(tk.END, rest_of_text + "\n", "black")

    log_text.yview(tk.END)
    root.update()

# ============================= #
# 🗑 Remove Selected Ignored Folder #
# ============================= #
def remove_selected_folder():
    selected_items = ignored_listbox.curselection()
    if not selected_items:
        messagebox.showwarning("No Selection", "Please select a folder to remove from the ignored list.")
        return

    for index in reversed(selected_items):
        ignored_listbox.delete(index)

# ============================= #
# 📂 Select Folders to Ignore    #
# ============================= #
def select_ignored_folders():
    selected_folder = filedialog.askdirectory(mustexist=True)
    if selected_folder:
        ignored_listbox.insert(tk.END, selected_folder)

# ============================= #
# 🚀 Push function (UI Integrated) #
# ============================= #
def push_project_in_chunks():
    start_button.config(state=tk.DISABLED)  # Disable button while running
    repo_path = folder_path.get()
    repo_url = repo_url_entry.get()
    chunk_size_mb = int(chunk_size_entry.get())

    if not repo_path or not repo_url:
        messagebox.showerror("Error", "Please select a project folder and enter a GitHub repository URL.")
        start_button.config(state=tk.NORMAL)
        return

    log_text.delete("1.0", tk.END)  # Clear log

    # ✅ Ensure Git is not locked
    subprocess.run(["git", "rm", "-f", ".git/index.lock"], cwd=repo_path, check=False)

    # 📝 Get Ignored Folders
    ignored_folders_list = [ignored_listbox.get(i) for i in range(ignored_listbox.size())]

    # 🔄 Initialize Git Repo if not exists
    if not os.path.exists(os.path.join(repo_path, ".git")):
        subprocess.run(["git", "init"], cwd=repo_path)
        subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=repo_path)

    # 🚀 Push Files in Chunks
    for dirpath, _, filenames in os.walk(repo_path):
        if ".git" in dirpath or any(dirpath.startswith(folder) for folder in ignored_folders_list):
            log_message(f"⚠️ Skipping: {dirpath}", "yellow")
            continue

        folder_size_mb = get_folder_size(dirpath) / (1024 * 1024)
        if folder_size_mb > chunk_size_mb:
            log_message(f"⚠️ Skipping large folder: {dirpath} ({folder_size_mb:.2f} MB)", "yellow")
            continue

        for file in filenames:
            file_path = os.path.join(dirpath, file)
            try:
                # ✅ Convert Windows paths to proper Git paths
                commit_msg = f"Added {file} from {dirpath.replace(repo_path, '').replace('\\', '/')}"
                
                subprocess.run(["git", "add", file_path], cwd=repo_path, check=True)
                subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_path, check=True)
                subprocess.run(["git", "push", "origin", "main"], cwd=repo_path, check=True)

                log_message(f"✅ Pushed: {file_path}", "green")

            except subprocess.CalledProcessError as e:
                log_message(f"❌ Failed: {file_path} - {str(e)}", "red")

    log_message("\n✅ Push Process Completed!", "blue")
    start_button.config(state=tk.NORMAL)  # Re-enable button

# ============================= #
# 🎨 UI Setup                    #
# ============================= #
root = tk.Tk()
root.title("Git Auto Push In Chunks")
root.geometry("800x600")
root.resizable(True, True)

# Responsive Grid Layout
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

btn_frame = tk.Frame(root)
btn_frame.grid(row=3, column=2, sticky="w", padx=5, pady=5)
tk.Button(btn_frame, text="Add", command=select_ignored_folders).pack(side=tk.TOP, fill="x", pady=2)
tk.Button(btn_frame, text="Remove", command=remove_selected_folder).pack(side=tk.TOP, fill="x", pady=2)

# 🚀 Start Push Button
start_button = tk.Button(root, text="Start Push", command=push_project_in_chunks, bg="green", fg="white", font=("Arial", 12, "bold"))
start_button.grid(row=4, column=1, pady=10)

# 📜 Log Area (Scrollable)
log_text = scrolledtext.ScrolledText(root, width=90, height=20)
log_text.grid(row=5, column=0, columnspan=3, sticky="nsew", padx=10, pady=5)

# 🏁 Run UI
root.mainloop()
