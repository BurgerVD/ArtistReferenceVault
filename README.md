# 🖼️ Reference Vault v1.0

A high-performance desktop tool for digital artists to keep their inspiration organized and accessible. **Reference Vault** doesn't just store images; it uses AI to "see" your references, making your entire library searchable in seconds.

## ✨ What it does

- **AI Auto-Tagging**: Automatically analyzes images in the background and assigns descriptive tags (e.g., "blue eyes," "sword," "cyberpunk").
- **Global Search**: Instantly find images across your entire vault using the search bar with predictive autocomplete.
- **Thumbnail Cache**: High-speed MD5-based caching allows folders with thousands of 4K images to load instantly.
- **Double-Click Lightbox**: View your references at full resolution in a borderless, immersive overlay.
- **Seamless Workflow**: Drag-and-drop folders or web images into the app, and drag them out directly into Photoshop, PureRef, or Blender.
- **Smart Deletion**: Choose between removing a reference from the app or permanently deleting the file from your PC.

## 📦 Requirements

- **Python 3.10+**
- **PyQt6** (GUI)
- **ONNX Runtime** (AI Engine)
- **NumPy < 2.0**

## 🛠️ Installation

1. **Clone or Download** this repository.
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## 🚀 How to use

1. Launch: Run python main.py.

2. Import: Drag any folder of images (or a link from Pinterest/Google) into the main window.

3. Tagging: Give the AI a moment to "warm up"—it will begin tagging your images in the background.

4. Search: Use the top bar to filter by tags. As you type, the app will suggest tags that exist in your library.

5. View: Double-click any thumbnail to see the full-res version. Click anywhere to close it.

6. Drag Out: Select one or multiple images and drag them into your painting software

## 🛡️ Privacy & Performance

Everything happens locally on your machine. Your images are never uploaded to a cloud, and the AI tagging engine runs on your CPU, ensuring it doesn't interfere with your GPU while you're painting or rendering.
