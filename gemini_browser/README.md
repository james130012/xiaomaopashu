# Gemini Browser with Python API

This project provides a lightweight, dedicated browser for interacting with Google's Gemini website (gemini.google.com). It features a Python API to programmatically send messages, retrieve responses, and manage the browser instance.

## Features

*   Launches a dedicated browser window for Google Gemini.
*   Persistent sessions: Remembers your login across uses.
*   Python API (`GeminiBrowserAPI`) to:
    *   Launch and shut down the browser.
    *   Send chat messages to Gemini.
    *   Retrieve the last response from Gemini.
    *   (Placeholder) Attempt file uploads (currently non-functional due to browser security, see Limitations).
    *   Get the full HTML of the current page for debugging.
*   Basic example script (`gemini_browser/main.py`) demonstrating API usage.

## Prerequisites

*   Python 3.7+
*   Operating System: Windows, macOS, or Linux.
*   `pip` for installing Python packages.

## Installation

1.  **Clone the repository (if you have it as a Git repo):**
    ```bash
    # git clone <repository_url>
    # cd <repository_directory>
    ```
    (If not a repo, just navigate to the `gemini_browser` project folder).

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    # On Windows:
    # venv\Scripts\activate
    # On macOS/Linux:
    # source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    This will install `PySide6`, which includes the necessary Qt WebEngine components.

## Usage

### Running the Dedicated Browser

To launch the Gemini browser window directly and interact with it manually:
```bash
python gemini_browser/main.py
```
This script also demonstrates some automated API interactions after a delay.

### Using the Python API

You can integrate the `GeminiBrowserAPI` into your own Python scripts. Here's a basic example:

```python
import time
from gemini_browser.interface.api import GeminiBrowserAPI

# Create an API instance
api = GeminiBrowserAPI()

# Launch the browser
api.launch_browser()

if api.browser_ready_event.is_set():
    print("Browser launched by API.")
    
    # Give the page time to load or for manual login if needed
    time.sleep(10) 
    
    api.send_text("Hello from my script!")
    
    time.sleep(5) # Wait for Gemini's response
    
    response = api.get_last_response()
    print(f"Response from Gemini: {response}")
    
    # ... other API calls ...

    # Shutdown the browser when done
    print("Shutting down browser...")
    api.shutdown_browser()
else:
    print("Browser failed to launch.")
```

Refer to `gemini_browser/interface/api.py` for detailed docstrings on all API methods.

## Important Notes & Limitations

### CSS Selectors
This browser interacts with the Gemini website using CSS selectors to find elements like chat input boxes, send buttons, and response areas. These selectors are defined in `gemini_browser/browser_core/browser_window.py` (e.g., `BrowserWindow.CHAT_INPUT_SELECTOR`).

**If Google updates the Gemini website structure, these selectors may break.** You might need to inspect the Gemini website's HTML and update these selectors in the code for the browser to continue working correctly. The `api.get_debug_html()` method can be helpful for this.

### File Uploads
The `api.upload_file()` method is currently a **placeholder and does not actually upload files.** Modern web browsers have strict security restrictions that prevent JavaScript from programmatically setting the value of file input fields or directly triggering file dialogs in a way that's easily automatable without external OS-level tools. This functionality is included to represent the desired feature, but it will report failure.

## Project Structure

*   `gemini_browser/main.py`: Example script to run the browser and demonstrate API usage.
*   `gemini_browser/requirements.txt`: Python package dependencies.
*   `gemini_browser/browser_core/`: Contains the core browser window implementation.
    *   `browser_window.py`: `BrowserWindow` class with `QWebEngineView`.
*   `gemini_browser/interface/`: Contains the Python API.
    *   `api.py`: `GeminiBrowserAPI` class.
*   `gemini_browser/utils/`: (Currently empty, for future utility functions).

## Troubleshooting

*   **Qt Plugin Errors / Display Issues:** Ensure `PySide6` installed correctly. Sometimes, on Linux, additional Qt system libraries might be needed if not bundled adequately by the pip package for your distribution (though this is less common now).
*   **Selectors Not Working:** As mentioned above, if Gemini's website changes, selectors will need to be updated. Use your browser's developer tools to inspect elements on gemini.google.com and find the new selectors.
```
