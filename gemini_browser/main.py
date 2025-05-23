# In gemini_browser/main.py
import sys
import time
import os # For os.remove
from gemini_browser.interface.api import GeminiBrowserAPI

if __name__ == "__main__":
    print("Starting Gemini Browser through API...")
    api = GeminiBrowserAPI()
    
    print("Launching browser...")
    api.launch_browser()

    if not api.browser_ready_event.is_set():
        print("Browser did not become ready. Exiting main.py.")
        # Attempt a shutdown if qt_thread was started
        if api.qt_thread and api.qt_thread.is_alive():
            api.shutdown_browser()
        sys.exit(1)

    print("Browser launched. You can interact with the Gemini window.")
    print("This script will demonstrate a few API calls after a short delay.")
    
    # Example: Let the user interact or automatically send a message after a delay
    try:
        # Wait for a few seconds to allow manual interaction or page loading
        time.sleep(10) 

        print("\nSending a test message via API...")
        api.send_text("Hello Gemini, this is a test from main.py!")
        
        # Wait for Gemini to respond
        print("Waiting for response (10 seconds)...")
        time.sleep(10) 
        
        print("Attempting to get the last response via API...")
        response = api.get_last_response()
        print(f"API received response: {response}\n")

        # Demonstrate file upload attempt (which is expected to fail gracefully)
        # Create a dummy file for the test
        dummy_file_main_path = "dummy_main_test_upload.txt"
        with open(dummy_file_main_path, "w") as f:
            f.write("Test content from main.py")
        
        print(f"Attempting to 'upload' file: {dummy_file_main_path}")
        upload_success = api.upload_file(dummy_file_main_path)
        print(f"File upload attempt result: {upload_success}\n")
        
        try:
            os.remove(dummy_file_main_path)
        except OSError:
            pass # Ignore if removal fails

        print("You can continue to use the browser window.")
        print("Close the browser window or press Ctrl+C in this terminal to shut down.")
        
        # Keep the main thread alive so the browser window stays open until the user closes it
        # or the script is interrupted. The api.qt_thread.join() will handle waiting.
        if api.qt_thread and api.qt_thread.is_alive():
            api.qt_thread.join() # Wait for browser thread to finish

    except KeyboardInterrupt:
        print("\nCtrl+C received, shutting down browser...")
    finally:
        print("Shutting down browser from main.py...")
        api.shutdown_browser()
        print("Browser shut down. Exiting main.py.")
