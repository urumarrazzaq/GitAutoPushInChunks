import os
import subprocess

# Set size threshold (25MB in bytes)
SIZE_THRESHOLD = 25 * 1024 * 1024  

def get_size(path):
    """Calculate the size of a directory or file."""
    if os.path.isfile(path):
        return os.path.getsize(path)
    total_size = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size

def chunk_push(folder, repo_url, branch="main", git_root=None):
    """Recursively push files in chunks to GitHub."""
    folder_size = get_size(folder)
    
    if git_root is None:
        git_root = folder

    if folder_size <= SIZE_THRESHOLD:
        # If folder size is within limits, push it directly
        push_to_git(folder, repo_url, branch, git_root)
    else:
        # If folder is too large, dive into subfolders
        for item in os.listdir(folder):
            item_path = os.path.join(folder, item)
            if os.path.isdir(item_path):
                chunk_push(item_path, repo_url, branch, git_root)
            else:
                push_to_git(item_path, repo_url, branch, git_root)

def push_to_git(path, repo_url, branch, git_root):
    """Push a file or folder to GitHub from the Git root directory."""
    try:
        os.chdir(git_root)  # Always run git commands from the root repo
        subprocess.run(["git", "add", path], check=True)
        subprocess.run(["git", "commit", "-m", f"Adding {path}"], check=True)
        subprocess.run(["git", "push", repo_url, branch], check=True)
        print(f"✅ Successfully pushed: {path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error pushing {path}: {e}")

if __name__ == "__main__":
    repo_url = input("Enter your GitHub repository URL: ")
    main_folder = input("Enter the path to your main project folder: ")
    
    # Ensure the script is being run inside a Git repo
    if not os.path.isdir(os.path.join(main_folder, ".git")):
        print("❌ Error: Not a Git repository. Run 'git init' first.")
        exit(1)
    
    chunk_push(main_folder, repo_url)
