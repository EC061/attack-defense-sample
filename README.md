# Project Setup

## Prerequisites

- Python 3.12 or higher
- **OpenAI API Key in .env file!!!!!!!!**

## Project Structure

- `run_attack_comparison.py`: Sample attack and defense pipeline
    - This is the only file I recommend running since attack_workflow take a long time with lots of token usage. It will run three attacks, one with no defense, one with input filter, and one with PII filter.
    - I ran a sample output and you can see the results in `success_attack.md`
        - Check the first successful attack [output](success_attack.md?plain=1#58) and [final confirmation](success_attack.md?plain=1#96).
- `pdf_description_gen`: Folder containing PDF description generation loop
- `recommendation_system`: Folder containing recommendation and defense filter
- `attack_client.py`: Unified endpoint for prompt injection attack
- `attack_workflow.py`: Automated attack prompt generation



## Setup Instructions

### 1. Install `uv`

If you haven't installed `uv` yet, you can do so with a single command:

**macOS and Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

For other installation methods, refer to the [uv documentation](https://github.com/astral-sh/uv).

### 2. Create a Virtual Environment

Run the following command to create a virtual environment in the `.venv` directory:

```bash
uv venv --python=3.12
```

### 3. Activate the Virtual Environment

Before installing dependencies, activate the virtual environment:

**macOS and Linux:**
```bash
source .venv/bin/activate
```

### 4. Install Dependencies (Note: this includes some non-needed dependencies for other parts of the agent that is not related to the attack-defense pipeline)

Install the project dependencies from `requirements.txt` using `uv`:

```bash
uv pip install -r requirements.txt
```

## Running the Project

Once the dependencies are installed, you can proceed with running the application.

### Attack Defense Pipeline

To run the sample attack defense pipeline, run:

```bash
python -u run_attack_comparison.py > attack_comparison.md 2>&1
```









