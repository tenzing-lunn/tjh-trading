# How to import this into Notion (one-time, ~5 minutes)

This file itself is NOT meant to become a Notion page — delete it after importing, or just
ignore it once you're done. Everything else in this folder is designed to become the new
Notion workspace structure.

## Steps
1. Download this whole `notion-import/` folder from the repo to your computer (if you're
   already looking at it in Cursor/GitHub, you can skip straight to zipping it).
2. Right-click the `notion-import` folder and **compress/zip it** (on Mac: right-click →
   "Compress"). You should end up with `notion-import.zip`.
3. Open Notion (web or desktop app).
4. In the left sidebar, click **"+ Add a page"** or go to **Settings → Import**.
5. Choose **Import → Markdown & CSV**, then select `notion-import.zip`.
6. Notion will create a page structure matching the folder: top-level pages for each
   numbered file (Start Here, What To Do Right Now, Results So Far, Roadmap, Glossary,
   Decisions We've Made), and a **"Roles"** page with sub-pages underneath it, and a
   **"Strategy Ideas (Theses)"** page with sub-pages underneath it.
7. Drag the pages into whatever sidebar order you like — the numbers in the filenames
   (00, 01, 02...) are just there to control the order they import in; feel free to rename
   the pages in Notion afterward (drop the numbers) once they're in.
8. Delete whatever old/disorganized Notion pages existed before, once everyone agrees the
   new structure has everything that mattered from the old one.

## Keeping it in sync going forward
This Notion structure is the **front door for decisions and to-dos** — it's meant to be
readable without touching code. The actual engine, data, and detailed research notes live in
the GitHub repo and are more detailed than what's copied here on purpose (Notion is the
summary, the repo is the full detail). When something changes:
- **New strategy idea →** Tenzing adds a new page under "Strategy Ideas (Theses)" using the template.
- **New test result →** Tenzing adds a row to "Results So Far."
- **Something gets decided →** Tenzing adds a line to "Decisions We've Made."
- **A to-do gets done →** cross it off "What To Do Right Now" (this page should almost always
  be short — if it's growing, something is stuck).
