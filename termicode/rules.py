import os


def generate_termicode_rules() -> str:
    """Auto-generates AGENT.md rules based on the detected project type."""
    project_type = "generic"
    rules = []

    if os.path.exists("package.json"):
        try:
            with open("package.json", "r", encoding="utf-8") as f:
                content = f.read()
                if "next" in content:
                    project_type = "nextjs"
                    rules.extend([
                        "This is a Next.js project using the App Router.",
                        "Use App Router conventions: app/ directory, page.tsx, layout.tsx",
                        "Use Tailwind CSS for styling (if present in dependencies).",
                        "Use Server Components by default, only use Client Components when necessary.",
                        "For API routes, use app/api/ directory with route.ts files.",
                        "Use next/image for images, not standard img tags.",
                    ])
                elif "react" in content:
                    project_type = "react"
                    rules.extend([
                        "This is a React project.",
                        "Use functional components with hooks.",
                        "Follow React best practices for state management.",
                    ])
        except Exception:
            pass

    if os.path.exists("requirements.txt"):
        project_type = "python"
        try:
            with open("requirements.txt", "r", encoding="utf-8") as f:
                content = f.read()
                if "django" in content:
                    rules.extend([
                        "This is a Django project.",
                        "Follow Django MTV (Model-View-Template) pattern.",
                        "Use Django ORM for database operations.",
                        "Create apps for modular functionality.",
                    ])
                elif "fastapi" in content:
                    rules.extend([
                        "This is a FastAPI project.",
                        "Use async/await for async operations.",
                        "Use Pydantic models for request/response validation.",
                        "Follow RESTful API conventions.",
                    ])
                else:
                    rules.extend([
                        "This is a Python project.",
                        "Follow PEP 8 style guidelines.",
                        "Use virtual environments for dependency management.",
                    ])
        except Exception:
            pass

    if not rules:
        rules.extend([
            "This is a general software project.",
            "Follow best practices for the detected language/framework.",
            "Write clean, readable, and maintainable code.",
            "Add comments for complex logic.",
        ])

    termicode_content = "# Auto-Generated AGENT.md Rules\n\n"
    termicode_content += f"**Detected Project Type:** {project_type}\n\n"
    termicode_content += "## Project-Specific Rules\n\n"
    for rule in rules:
        termicode_content += f"- {rule}\n"

    termicode_content += "\n## General Guidelines\n\n"
    termicode_content += "- Always follow existing code style and conventions in the project.\n"
    termicode_content += "- Test your changes before committing.\n"
    termicode_content += "- Use meaningful variable and function names.\n"
    termicode_content += "- Keep functions small and focused on a single responsibility.\n"

    if not os.path.exists("AGENT.md"):
        try:
            with open("AGENT.md", "w", encoding="utf-8") as f:
                f.write(termicode_content)
            return f"Success: Generated AGENT.md for {project_type} project with {len(rules)} custom rules."
        except Exception as e:
            return f"Error writing AGENT.md: {e}"

    return "AGENT.md already exists. Delete it first to auto-generate new rules."
