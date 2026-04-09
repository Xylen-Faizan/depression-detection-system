# Depression Detection System

A multimodal depression detection system using voice and video analysis.

## Tech Stack
- **Backend**: FastAPI + Python
- **Frontend**: React
- **AI**: Groq (LLaMA), OpenAI Whisper, TensorFlow

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/depression-detection-system.git
cd depression_detection_system
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Add your API keys
Create a `.env` file in the root folder:
```
GROQ_API_KEY=your_groq_api_key_here
```

### 4. Add the face model
Place your `face_model.h5` file inside `backend/models/`

### 5. Run the backend
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 6. Run the frontend
```bash
cd frontend
npm install
npm start
```

Open http://localhost:3000 in your browser.
