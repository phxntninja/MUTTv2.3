import os
import glob

def summarize_docs():
    """
    Summarizes all markdown files in the project directory.
    """
    markdown_files = glob.glob("**/*.md", recursive=True)
    report = []

    for file_path in markdown_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                word_count = len(content.split())
                summary = " ".join(content.splitlines()[:3])
                report.append({
                    "file_path": file_path,
                    "word_count": word_count,
                    "summary": summary
                })
        except Exception as e:
            report.append({
                "file_path": file_path,
                "word_count": 0,
                "summary": f"Error reading file: {e}"
            })

    # Sort the report by file path
    report.sort(key=lambda x: x["file_path"])

    # Print the report
    for item in report:
        print(f"File: {item['file_path']}")
        print(f"  Word Count: {item['word_count']}")
        print(f"  Summary: {item['summary']}")
        print("-" * 20)

if __name__ == "__main__":
    summarize_docs()
