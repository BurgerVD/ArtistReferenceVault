# ArtistReferenceVault

--STILL IN DEVELOPMENT --

A small PyQt6 desktop tool for keeping reference images close while you work.

Drop a folder of images into the window, pick it from the sidebar, and you’ll get a clean thumbnail grid. You can also drag one or multiple images out of the grid into other apps (Photoshop, PureRef, your file explorer, etc.).

## What it does

- Drag-and-drop a **folder** of images into the app
- Shows a **thumbnail grid** for quick browsing
- Sidebar keeps the dropped folders so you can switch between sets
- **Drag images out** of the app into other programs
- Loads thumbnails on a background thread so the UI doesn’t lock up on bigger folders

Supported formats: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.webp`

## Requirements

- Python 3.x
- PyQt6

## Install

```bash
pip install PyQt6
```

## Run

```bash
python main.py
```

## How to use

1. Launch the app
2. Drag a folder of reference images into the main window
3. Click the folder name on the left to view it
4. Select one or more thumbnails and drag them into whatever you’re working in

## Notes / Known quirks

- This is intentionally simple right now: it doesn’t copy/move files or manage a library database — it just points at folders you drop in for the current session.
- If you switch folders quickly while thumbnails are still loading, the previous load gets interrupted so it doesn’t keep chewing through the filesystem in the background.

## Roadmap 

- Remember folders and images between sessions
- Automatic tagging / favorites
- Search/filter
- Adjustable thumbnail size
- Delete, reorder, create new folder
- Menu 
---

If you end up using it in your workflow and something feels annoying, open an issue — that’s usually the best way to decide what to add next.
