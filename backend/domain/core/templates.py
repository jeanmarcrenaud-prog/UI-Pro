"""Project templates — pre-defined file scaffolds for common project types.

Each template defines a set of files to generate and a prompt suffix that
gets appended to the user's request when the template is applied.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.domain.settings import get_settings

logger = logging.getLogger(__name__)


class Template:
    """A project template with files and a prompt suffix."""

    def __init__(
        self,
        id: str,
        name: str,
        description: str,
        files: dict[str, str],
        prompt_suffix: str,
    ):
        self.id = id
        self.name = name
        self.description = description
        self.files = files
        self.prompt_suffix = prompt_suffix


TEMPLATES: dict[str, Template] = {
    "nextjs-app": Template(
        id="nextjs-app",
        name="Next.js App Router",
        description="Full-stack Next.js 16 app with App Router, TypeScript, and Tailwind",
        files={
            "package.json": """{
  "name": "my-app",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "16.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@types/react": "^18",
    "@types/node": "^20",
    "typescript": "^5",
    "tailwindcss": "^4.0.0",
    "@types/react": "^18"
  }
}""",
            "app/layout.tsx": """import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "My App",
  description: "A Next.js application",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
""",
            "app/page.tsx": """export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center">
      <h1 className="text-4xl font-bold">Hello, World!</h1>
    </main>
  );
}
""",
            "app/globals.css": """@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  body {
    @apply bg-background text-foreground;
  }
}
""",
            "tailwind.config.js": """/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};
""",
            "tsconfig.json": """{
  "compilerOptions": {
    "target": "es5",
    "lib": ["dom", "dom.iterable", "es6"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
""",
        },
        prompt_suffix="Create a Next.js App Router project with TypeScript and Tailwind CSS.",
    ),
    "fastapi": Template(
        id="fastapi",
        name="FastAPI CRUD",
        description="FastAPI with Pydantic v2, SQLAlchemy, and SQLite",
        files={
            "main.py": """from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import sqlite3

app = FastAPI(title="My API", version="1.0.0")


class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tax: Optional[float] = None


@app.get("/")
async def read_root():
    return {"message": "Hello, World!"}


@app.post("/items/", response_model=Item)
async def create_item(item: Item):
    return item


@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}
""",
            "requirements.txt": """fastapi>=0.115.0
uvicorn>=0.30.0
pydantic>=2.0.0
""",
            "README.md": """# My FastAPI App

## Setup

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## API

- `GET /` — health check
- `POST /items/` — create an item
- `GET /items/{item_id}` — read an item
""",
        },
        prompt_suffix="Create a FastAPI application with CRUD endpoints using Pydantic v2 and SQLite.",
    ),
    "tauri": Template(
        id="tauri",
        name="Tauri App",
        description="Rust + React Tauri desktop application",
        files={
            "package.json": """{
  "name": "my-tauri-app",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "tauri": "tauri"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^5.0.0",
    "vite": "^5.0.0",
    "tauri-cli": "^2.0.0"
  }
}
""",
            "src/App.tsx": """import { useState } from "react";
import "./App.css";

function App() {
  const [count, setCount] = useState(0);

  return (
    <main className="flex flex-col items-center justify-center min-h-screen">
      <h1 className="text-3xl font-bold mb-4">Tauri App</h1>
      <button
        className="px-4 py-2 bg-blue-500 text-white rounded"
        onClick={() => setCount(count + 1)}
      >
        Count: {count}
      </button>
    </main>
  );
}

export default App;
""",
            "src/App.css": """main {
  font-family: system-ui, sans-serif;
}
""",
            "src/main.tsx": """import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./App.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
""",
            "src-tauri/tauri.conf.json": """{
  "package": {
    "name": "my-tauri-app",
    "version": "0.1.0"
  },
  "build": {
    "distDir": "../dist",
    "devPath": "http://localhost:5173"
  },
  "tauri": {
    "window": {
      "title": "My Tauri App",
      "width": 1200,
      "height": 800
    }
  }
}
""",
        },
        prompt_suffix="Create a Tauri desktop application with Rust backend and React frontend.",
    ),
}


def list_templates() -> list[dict[str, str]]:
    """Return a list of all available templates (id, name, description)."""
    return [
        {"id": t.id, "name": t.name, "description": t.description, "prompt_suffix": t.prompt_suffix}
        for t in TEMPLATES.values()
    ]


def get_template(template_id: str) -> Template | None:
    """Get a template by ID, or None if not found."""
    return TEMPLATES.get(template_id)


def apply_template(template_id: str, workspace: str | None = None) -> dict[str, Any]:
    """Apply a template by writing its files to the workspace.

    Args:
        template_id: The template ID (e.g. "nextjs-app").
        workspace: Optional workspace path override. Defaults to settings.workspace_path.

    Returns:
        Dict with keys: success, template_id, files_written, errors.
    """
    template = get_template(template_id)
    if template is None:
        return {
            "success": False,
            "template_id": template_id,
            "files_written": [],
            "errors": [f"Template '{template_id}' not found"],
        }

    ws = Path(workspace) if workspace else get_settings().workspace_path
    ws.mkdir(parents=True, exist_ok=True)

    files_written: list[str] = []
    errors: list[str] = []

    for rel_path, content in template.files.items():
        try:
            file_path = ws / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            files_written.append(rel_path)
        except Exception as e:
            errors.append(f"Failed to write {rel_path}: {e}")
            logger.error(f"Template write error for {rel_path}: {e}")

    return {
        "success": len(errors) == 0,
        "template_id": template_id,
        "files_written": files_written,
        "errors": errors,
    }
