# 🔒 StegoCrypt AI: Advanced Steganography & Steganalysis 🛡️

**StegoCrypt AI** is a comprehensive, production-grade cybersecurity application that combines advanced steganography, cryptography, and deep learning-based steganalysis. This project serves as an end-to-end platform for securely hiding data within multimedia files and detecting hidden data using AI.

---

## 🌟 Key Features

### 1. Advanced Cryptography & Steganography
* **Military-Grade Encryption**: Supports multiple robust encryption algorithms:
  * **AES-256-GCM** (Authenticated Encryption)
  * **AES-256-CBC**
  * **ChaCha20** (High-speed stream cipher)
* **Advanced Key Derivation**: Uses **PBKDF2** and **scrypt** with dynamic salt and high iterations to protect against brute-force attacks.
* **Multi-Format Support**:
  * **Images**: Supports LSB (Least Significant Bit), DCT (Discrete Cosine Transform), and SVD (Singular Value Decomposition) algorithms.
  * **Audio**: High-fidelity audio steganography using advanced signal processing.
  * **Files**: Embedding files within other files seamlessly.
* **Format-Preserving**: Ensures the visual and auditory integrity of the cover files.

### 2. Deep Learning Steganalysis (AI Detection)
* **Pre-trained ResNet-18 Model**: Utilizes a highly optimized ResNet-18 neural network trained to detect subtle perturbations caused by steganography.
* **High Accuracy**: Capable of detecting LSB and DCT modifications even with minimal payloads.
* **Real-time Analysis**: Drag-and-drop an image to instantly receive an AI-powered safety score and probability analysis.

### 3. Beautiful & Responsive UI
* **Glassmorphism Design**: A sleek, modern interface with interactive elements and smooth animations.
* **Full-Stack Architecture**: Built with a Flask backend and a vanilla JS/HTML/CSS frontend for maximum performance and portability.

---

## 🛠️ Technologies Used

* **Backend**: Python, Flask, Flask-CORS
* **AI & Deep Learning**: PyTorch, TorchVision, ResNet-18
* **Image & Signal Processing**: OpenCV, NumPy, Pillow (PIL)
* **Cryptography**: PyCryptodome (AES-256-GCM)
* **Frontend**: HTML5, CSS3, JavaScript (Vanilla)

---

## 🚀 Setup & Installation Guide

### Prerequisites
* Python 3.10 or 3.11 installed.
* Make sure Python is added to your system `PATH`.

### Step-by-Step Instructions

1. **Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/StegoCrypt-AI.git
   cd StegoCrypt-AI
   ```

2. **Create a Virtual Environment**
   ```bash
   python -m venv env1
   ```

3. **Activate the Virtual Environment**
   * **Windows**:
     ```bash
     .\env1\Scripts\activate
     ```
   * **Linux/Mac**:
     ```bash
     source env1/bin/activate
     ```

4. **Install Dependencies**
   ```bash
   pip install flask flask-cors opencv-python numpy pycryptodome Pillow
   ```

5. **Install PyTorch (Critical for AI)**
   * **With GPU (NVIDIA)**:
     ```bash
     pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
     ```
   * **Without GPU (CPU only)**:
     ```bash
     pip install torch torchvision
     ```

6. **Run the Application**
   ```bash
   python start.py
   ```
   > The application will automatically start both the Flask backend and the frontend server, and open your browser to `http://localhost:8000`.

---

## 🌍 نظرة عامة (Arabic Overview)

**StegoCrypt AI** هو تطبيق أمن سيبراني متقدم يجمع بين التشفير، وإخفاء البيانات (Steganography)، وتحليل البيانات المخفية باستخدام الذكاء الاصطناعي (Steganalysis). تم بناء هذا المشروع ليكون أداة احترافية تضمن سرية البيانات المخبأة من جهة، وتوفر تقنيات متطورة للكشف عن البيانات المخبأة في الصور باستخدام نموذج ذكاء اصطناعي يعتمد على شبكة ResNet-18.

### الميزات الأساسية:
- **تشفير قوي**: يتم تشفير جميع البيانات باستخدام AES-256-GCM قبل إخفائها.
- **خوارزميات إخفاء متعددة**: يدعم LSB, DCT, SVD للصور، بالإضافة إلى إخفاء الملفات والصوتيات.
- **كشف عبر الذكاء الاصطناعي**: يحتوي على نموذج ResNet-18 مدرب بدقة عالية لاكتشاف التعديلات الطفيفة في الصور.
- **واجهة مستخدم عصرية**: تصميم تفاعلي وسهل الاستخدام (Glassmorphism).

---

## ⚠️ Important Notes
* **Model Size**: Ensure you have the `steg_model.pth` (approx. 45MB) inside the `backend/` directory for the AI Steganalysis to work correctly.
* **PyTorch Environment**: If you encounter a "Model not loaded" error, verify that your virtual environment is active and PyTorch is installed successfully.

---
*Built for the future of digital forensics and secure communications.*
