<div align="center">
  <img src="logo.png" alt="AI Surveillance Logo" width="300" />
  <h1>AI Surveillance System</h1>
  <p><strong>A GSSoC-Friendly Missing Person Detection Engine</strong></p>
</div>

Welcome to the AI Surveillance System! This project uses YOLOv12 and DeepFace to track missing persons across concurrent video feeds. We have intentionally simplified this architecture so that college students and open-source contributors can easily run the entire stack locally without relying on heavy containerization.

---

## 🚀 Prerequisites

Before you begin, ensure you have the following installed on your machine:
- **Python 3.10+** (Required for OpenCV and deep learning models)
- **Node.js 20+** (Required for the Next.js frontend)
- **Git**

---

## 🛠️ Step 1: Backend Setup (FastAPI + YOLO)

The backend processes the video feeds locally on your machine using FastAPI BackgroundTasks and stores state in a local SQLite database.

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   - **Windows:**
     ```powershell
     .\venv\Scripts\activate
     ```
   - **Mac/Linux:**
     ```bash
     source venv/bin/activate
     ```

4. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Start the backend server:**
   ```bash
   uvicorn app:app --reload --port 8001
   ```
   *The backend will now be running at `http://127.0.0.1:8001`.*

---

## 🎨 Step 2: Frontend Setup (Next.js)

The frontend is a beautifully designed "Soft UI" Command Center that connects to your local backend to render the video and bounding boxes.

1. **Open a NEW terminal window** (leave the backend running) and navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. **Install the Node dependencies:**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```

4. **View the App:** Open your browser and go to [http://localhost:3000](http://localhost:3000).

---

## ⚠️ Troubleshooting Guide (For Windows Users)

Machine learning libraries can sometimes be tricky to install on Windows. If you encounter errors during `pip install -r requirements.txt` (specifically for `opencv-python` or `dlib`/`deepface`), it usually means your system is missing C++ compilers.

### Fix: "Microsoft Visual C++ 14.0 or greater is required"
1. Download the [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/).
2. Run the installer.
3. In the installer, select the **"Desktop development with C++"** workload.
4. Ensure the **"MSVC v143 - VS 2022 C++ x64/x86 build tools"** and **"Windows 10/11 SDK"** are checked on the right side.
5. Click Install. Once finished, restart your terminal and try `pip install -r requirements.txt` again.

### Fix: "ImportError: DLL load failed while importing cv2"
This means Windows is missing media foundation libraries.
1. Open your Windows Start Menu and search for "Media Feature Pack".
2. Alternatively, install it via PowerShell as Administrator:
   ```powershell
   Enable-WindowsOptionalFeature -Online -FeatureName "MediaPlayback" -All
   ```

---

## 🤝 Contributing for GSSoC

We are thrilled to be part of the GirlScript Summer of Code! To start contributing:
1. Fork this repository.
2. Read the `CONTRIBUTING.md` file for our PR guidelines.
3. Check out the Issues tab for any tasks tagged with `GSSoC` or `good first issue`.

Happy Coding!
