# CAD Multi-Agent System

This is a proof-of-concept multi-agent system for generating OpenSCAD 3D models from natural language descriptions.

## Architecture

The system uses **LangGraph** to orchestrate a team of AI agents:

1.  **Planner Agent**: Decomposes the user request into specific 3D parts and coordinates.
2.  **Workers (Loop/Profile/Solid)**: Generate specific OpenSCAD code for each part.
3.  **Generator Agent**: Assembles the parts into a complete `.scad` file.
4.  **Inspector Agent**: Checks the result (visually if OpenSCAD is installed, otherwise logically) and provides feedback.
5.  **Loop**: If the Inspector fails the model, the Planner revises the plan based on feedback.

## Requirements

- Python 3.9+
- OpenSCAD (optional, for image rendering and visual inspection)
- OpenAI API Key

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure API Key:
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

3. (Optional) Install OpenSCAD:
   - macOS: `brew install --cask openscad`
   - Linux: `sudo apt-get install openscad`
   - Windows: Download from openscad.org

## Usage

Run the main script:

```bash
python main.py
```

Enter your prompt (e.g., "Design a mug with a handle") and watch the agents work. The final model will be saved as `model.scad`.
