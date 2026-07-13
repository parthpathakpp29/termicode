import sys
import subprocess
import os

def main():
    print("\n🛡️  [TermiCode Guardian] Analyzing staged files...")

    # 1. Ask Git which files are currently staged for this commit
    diff_cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"]
    result = subprocess.run(diff_cmd, capture_output=True, text=True)
    staged_files = [f for f in result.stdout.splitlines() if f.endswith('.py')]

    if not staged_files:
        print("  ↳ No Python files staged. Proceeding.")
        sys.exit(0)
    
    print(f"  ↳ Running deep diagnostic on {len(staged_files)} file(s)...")

    # 2. Run Repowise health check
    cmd = ["repowise", "health"]
    health_result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = health_result.stdout

    # 3. Analyze the output: If the repo has warnings, are our staged files to blame?
    if "[Warning]" in output or "[Alert]" in output or "Worst: " in output:
        # Check if any of our staged files are listed in the "Lowest-scoring files" section
        bad_files_in_commit = [f for f in staged_files if f in output]
        
        if bad_files_in_commit:
            print("\n❌ HIGH RISK COMMIT BLOCKED ❌")
            print("TermiCode has detected architectural flaws or 'God Classes' in the files you are trying to commit.")
            print("-" * 60)
            for file in bad_files_in_commit:
                print(f"  ⚠️  {file} failed the health check.")
            print("-" * 60)
            print("To fix this automatically, open TermiCode and type:")
            for file in bad_files_in_commit:
                print(f"  /heal {file}")
            print("\nCommit aborted. Please refactor before pushing.")
            
            # Returning 1 tells Git to abort the commit completely!
            sys.exit(1)
            
    print("✅  Code health verified. Commit allowed.")
    sys.exit(0)

if __name__ == "__main__":
    main()