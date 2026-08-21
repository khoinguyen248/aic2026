# Multimodal Video Retrieval System for Linux

## Project Overview

This project is a submission for the [AI HCM Challenge 2025 - Final Round](https://aichallenge.hochiminhcity.gov.vn/). The system implements a multimodal-based information retrieval system designed to extract and retrieve relevant information from lifelog video data.

The solution leverages advanced deep learning models, particularly vision transformers (BEiT3) and CLIP embeddings, to analyze and understand lifelog video content. The system enables semantic search, metadata-based search, multimodal and temporal retrieval across large-scale video datasets.

**Key Features:**
- Extract semantic embeddings and metadata from keyframes.
- Similarity search based on semantic, metadata, multimodal and temporal keyframes.
- RESTful API backend with Flask.
- User-friendly UI, real-time interactive system for retrieval task.

---

## Getting Started

### Prerequisites

- **Python 3.8+** - For the backend API
- **Node.js 16+** - For the frontend application
- **CUDA 11.0+** (Optional) - For GPU-accelerated model inference
- **Conda** (Recommended) - For Python environment management
- 16GB+ RAM - Minimum for model inference
- 50GB+ Storage - For keyframs, model checkpoints and embeddings

### Installation

#### 1. Clone the Repository

```bash
git clone <repository-url>
cd AIC-2025
```

#### 2. Backend Setup

Navigate to the backend directory:

```bash
cd backendAIC2025
```

Create and activate a Python virtual environment:

```bash
# Using conda (recommended)
conda create -n aic2025 python=3.8
conda activate aic2025

# OR using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

#### 3. Frontend Setup

Navigate to the frontend directory:

```bash
cd frontend-final/vite-project
```

Install Node.js dependencies:

```bash
npm install
```

#### 4. Download Neccessary Resoure

Download the BEiT3 checkpoint, keyframes and keyframes embeddings in [Google Drive Folder](https://drive.google.com/drive/folders/1lLyvVkyQcw4orZvFsQk0bLmtEFiNpBCF?usp=drive_link).

### Running the Application

#### Start the Backend Server

```bash
cd backendAIC2025
python run.py
```

The API server will be available at `http://localhost:5000`

#### Start the Frontend Development Server

In a new terminal:

```bash
cd frontend-final/vite-project
npm run dev
```

The frontend will be available at `http://localhost:5173`

#### Start the Keyframes Backend Server

In a new terminal:

```bash
cd backend-framesAIC2025
node server.js
```

The keyframs backend will be available at `http://localhost:8080`

---

## Project Structure

```
AIC-2025/
├── README.md                          # Project documentation
│
├── backend-framesAIC2025/             # Node.js frame processing service
│   ├── package.json
│   └── server.js
│
├── backendAIC2025/                    # Main Python backend API
│   ├── run.py                         # Application entry point
│   ├── requirements.txt               # Python dependencies
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py                  # Configuration settings
│   │   ├── extensions.py              # Database and extension initialization
│   │   │
│   │   ├── controllers/               # API controllers
│   │   │   ├── search_controller.py   # Search functionality
│   │   │   └── user_controller.py     # User management
│   │   │
│   │   ├── models/                    # Database models
│   │   │   ├── user_models.py         
│   │   │   ├── search_model.py        
│   │   │   ├── eeiot_model.py         
│   │   │   ├── teacher_model.py       
│   │   │   └── teacher_position_model.py  
│   │   │
│   │   ├── routes/                    # API routes
│   │   │   ├── user_routes.py         # User endpoints
│   │   │   └── search_routes.py       # Search endpoints
│   │   │
│   │   └── utils/
│   │       └── helpers.py             # Utility functions
│   │
│   ├── beit3/                         # BEiT3 vision transformer implementation
│   │   └── checkpoints/
│   │
│   ├── embedding-info/                # Keyframe embeddings
│   │   ├── beit3/                     # BEiT3
│   │   └── clip/                      # CLIP 
│   │
│   └── metadata/                      # Keyframe metadata
└── frontend-final/                    # Frontend application
    └── vite-project/
        ├── index.html
        ├── package.json
        ├── vite.config.js
        ├── eslint.config.js
        ├── src/                       # React/Vue components
        └── public/                    # Static assets
```

### Key Components

- **Backend API (Flask)**: RESTful API for search, user management, and video metadata
- **Database Models**: User profiles, search history, lifelog metadata
- **Frontend (Vite)**: Modern web interface for video search and retrieval.
- **Keyframes Embeddings**: `.npy` files containing embedding vectors for fast retrieval in **FAISS**

---

## Results


Our system demonstrates the effectiveness of multimodal approaches in understanding and retrieving information from complex lifelog video data at **Pre-Final Round** and impressivelly participate in the **Final Round**

---

## License

This project is submitted as part of the AI HCM Challenge 2025. Use and distribution are subject to the challenge's terms and conditions.

For inquiries about licensing or usage rights, please refer to the challenge organizers.

---

## Contact & Support

For questions or issues related to this project, please refer to the project structure and documentation files included in the repository.
