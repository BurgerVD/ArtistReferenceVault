# 🗃️ Reference Vault

![Version](https://img.shields.io/badge/version-1.0.2-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Copyright-red)

Reference Vault is a fast, multithreaded desktop application designed specifically for digital artists to manage massive reference libraries. It uses local, on-device AI to automatically analyze and tag thousands of images in the background, allowing for instant global search without relying on cloud APIs or paid subscriptions.

<div align="center">
  <img src="https://github.com/user-attachments/assets/e4868e2a-f6aa-4d2e-976d-17b180b1962b" width="400" height="400" />
</div>

## ✨ Key Features

* **🧠 Local AI Auto-Tagging:** Powered by the WD14 ONNX neural network, the vault automatically scans and tags your images locally. Zero cloud tracking, zero API costs.
* **⚡ Asynchronous Architecture:** Built with Python `QThread` workers. The app handles heavy machine learning inference and OS-level file operations in the background, ensuring the main UI never drops a frame.
* **📂 Smart Hierarchical Trees:** Drop complex, nested folder structures into the app, and it will automatically map and render them as an interactive tree-view sidebar.
* **🔍 Global Instant Search:** An SQLite-backed database allows you to search for concepts (e.g., "sword", "dynamic pose", "blue lighting") and instantly pull matching references from across your entire hard drive.
* **🔄 Live UI Tracking:** Real-time visual feedback for the AI queue, background image caching, and automatic GitHub release update checks.

## 🛠️ Under the Hood (Technical Architecture)

This application was engineered to handle large-scale datasets (70,000+ images) efficiently on standard consumer hardware.

* **Frontend:** Built with `PyQt6` for a modular, object-oriented, and highly responsive native desktop interface.
* **Inference Engine:** Utilizes `onnxruntime` for CPU-optimized machine learning inference. The AI worker thread is strictly governed by custom OpenMP thread caps and micro-sleep cycle yielding to prevent OS-level UI locking.
* **Data Management:** Implements `SQLite3` for lightweight, ACID-compliant tag storage and rapid localized querying.
* **Concurrency:** Features a multi-threaded producer-consumer pipeline. Background crawlers locate untagged files and feed them into a thread-safe `queue.Queue()`, which is processed asynchronously by the AI worker.

## 📥 Installation (For Artists)

1. Go to the [Releases Page](../../releases/latest).
2. Download the latest `ReferenceVault_Setup.exe`.
3. Run the installer and launch the app.
4. Drag and drop your master reference folder into the canvas to start tagging!
*(Note: Windows SmartScreen may flag the installer as it is currently an unsigned indie application. Click **More info -> Run anyway**).*

## 💻 Building from Source (For Developers)

If you want to fork this project or build the executable yourself:

1. Clone the repository:
   ```bash
   git clone [https://github.com/ShaheerVD/ArtistReferenceVault.git](https://github.com/ShaheerVD/ArtistReferenceVault.git)
2. Create a virtual environment and install dependencies
    ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
3. Run the application locally:
   ```bash
   python main.py
4.Build using PyInstaller:
  ```bash
  pyinstaller --name "ReferenceVault" --windowed --onedir --icon="app_icon.ico" --hidden-import=sqlite3 --hidden-import=PIL --collect-all onnxruntime main.py
