import sys
import threading
import time
import os # Added for file path operations

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QMetaObject, Q_ARG, Q_RETURN_ARG, Qt, QTimer # Added QTimer for shutdown, may not be needed here
from gemini_browser.browser_core.browser_window import BrowserWindow

class GeminiBrowserAPI:
    """
    Provides a Python API to control a headless or headed browser instance
    navigating to Gemini, allowing for programmatic interaction.

    The API manages a Qt-based browser window in a separate thread.
    Interactions with the browser (like sending text or getting responses)
    are achieved by invoking methods on the BrowserWindow object in the Qt thread
    using `QMetaObject.invokeMethod`.
    """
    def __init__(self):
        """
        Initializes the GeminiBrowserAPI.

        Sets up internal state, including the application instance, browser window reference,
        Qt thread reference, and an event for browser readiness synchronization.
        """
        self.app = None
        self.browser_window = None
        self.qt_thread = None
        self.browser_ready_event = threading.Event()

    def launch_browser(self, headless: bool = False):
        """
        Launches the Gemini browser window in a separate thread.

        If the browser is already launched and ready, this method returns early.
        It sets up and starts a new thread for the Qt application loop.
        The method waits for a signal (up to a timeout) indicating that the
        browser window has been initialized and shown.

        Args:
            headless (bool): If True, attempts to launch the browser in a headless
                             fashion. Currently, this is a placeholder and the window
                             will still show. Defaults to False.

        Prints:
            Informational messages about the browser launch status.
            A warning if the browser window does not become ready within the timeout.
        
        Returns:
            None. Callers should check `self.browser_ready_event.is_set()` to confirm
            if the browser is ready for interaction.
        """
        if self.browser_ready_event.is_set(): # Check if already launched and ready
            print("Browser is already launched and ready.")
            return

        self.browser_ready_event.clear() # Clear event for this launch attempt

        def run_qt_app():
            current_app = QApplication.instance()
            if not current_app:
                # This is where the app is created for the first time in this thread
                QApplication.setApplicationName("GeminiBrowser")
                QApplication.setOrganizationName("MyCompany") # Or any placeholder
                self.app = QApplication(sys.argv)
            else:
                self.app = current_app
                # If app already exists, ensure names are set if not already
                if not self.app.applicationName():
                     self.app.setApplicationName("GeminiBrowser")
                if not self.app.organizationName():
                     self.app.setOrganizationName("MyCompany")
            
            self.browser_window = BrowserWindow()
            if headless:
                print("Headless mode requested, but window will show for now.")
                # Future: Implement true headless if possible by not calling show()
                # or using offscreen rendering.
                self.browser_window.show() 
            else:
                self.browser_window.show()
            
            self.browser_ready_event.set() # Signal that browser window is created and shown
            
            self.app.exec()
            
            # Cleanup after event loop finishes
            self.browser_window = None
            self.app = None # QApplication instance
            self.browser_ready_event.clear() # Ensure it's clear after shutdown

        self.qt_thread = threading.Thread(target=run_qt_app)
        self.qt_thread.setName("QtBrowserThread") # Give the thread a name for easier debugging
        self.qt_thread.start()
        
        if not self.browser_ready_event.wait(timeout=10): # Wait for 10 seconds
            print("API Warning: Browser window did not become ready within timeout.")
            if self.qt_thread and self.qt_thread.is_alive():
                # If app started but window didn't signal, something is wrong.
                # Attempt a graceful shutdown of the partially launched Qt thread.
                print("API: Attempting to shutdown partially launched browser...")
                self.shutdown_browser() 
            return 
        
        print("Browser launched and ready.")


    def send_text(self, text: str):
        """
        Sends the given text to the Gemini chat input field and clicks the send button.

        This method checks if the browser is ready before attempting to send text.
        It uses `QMetaObject.invokeMethod` to call the internal `_set_chat_input_text`
        and `_click_send_button` methods of the `BrowserWindow` instance, ensuring
        these actions are performed on the Qt GUI thread.

        A short delay is introduced between setting the text and clicking the button
        to allow the web page to register the input.

        Args:
            text (str): The text message to send to Gemini.

        Prints:
            An "API Error..." message if the browser is not ready.
            An informational message upon successful queuing of the send actions.
        
        Returns:
            None. Success or failure is indicated by printed messages. Consider
            returning a boolean in future versions for explicit status.
        """
        if not self.browser_window or not self.qt_thread or not self.qt_thread.is_alive() or not self.browser_ready_event.is_set():
            print("API Error: Browser not launched, not ready, or Qt thread not alive. Cannot send text.")
            return

        # Note: Text sanitization for JS embedding is handled within BrowserWindow._set_chat_input_text
        
        # Call _set_chat_input_text in the Qt thread
        QMetaObject.invokeMethod(
            self.browser_window,
            "_set_chat_input_text", # Slot name in BrowserWindow
            Qt.QueuedConnection,    # Connection type
            Q_ARG(str, text)        # Argument type and value
        )
        
        time.sleep(0.3) # Small delay for input to register on the page. Consider alternatives.

        # Call _click_send_button in the Qt thread
        QMetaObject.invokeMethod(
            self.browser_window,
            "_click_send_button",    # Slot name in BrowserWindow
            Qt.QueuedConnection      # Connection type
        )
        print(f"API: Queued sending text and clicking send button for: '{text[:50]}...'")

    def get_last_response(self) -> str:
        """
        Retrieves the text content of the last response from the Gemini interface.

        This method checks if the browser is ready. It then constructs and executes
        JavaScript code within the `BrowserWindow` to find the element containing
        the last response and extract its inner text. The JavaScript execution
        happens on the Qt GUI thread via a blocking call to `_execute_js_and_get_string_result`.

        Args:
            None

        Returns:
            str: The text of the last response found on the page.
                 Returns an error message string if:
                 - The browser is not ready.
                 - The JavaScript execution fails or times out.
                 - The response element cannot be found using the defined selector.
        """
        if not self.browser_window or not self.qt_thread or not self.qt_thread.is_alive() or not self.browser_ready_event.is_set():
            print("API Error: Browser not launched, not ready, or Qt thread not alive. Cannot get last response.")
            return "Error: Browser not available or not ready."

        js_code_to_get_response = f"""
            (function() {{
                var elements = document.querySelectorAll('{BrowserWindow.LAST_RESPONSE_SELECTOR}');
                if (elements && elements.length > 0) {{
                    return elements[elements.length - 1].innerText; // Get text of the last element
                }}
                return 'No response element found for selector: {BrowserWindow.LAST_RESPONSE_SELECTOR}';
            }})();
        """
        
        response_text = ""
        # The return_value must be a mutable type if Q_RETURN_ARG is used for non-standard types or complex ones.
        # For simple types like str, it's more straightforward.
        # We expect a string back from _execute_js_and_get_string_result
        
        # We need a way to get the return value. Q_RETURN_ARG is tricky with Python types directly sometimes.
        # Let's assume _execute_js_and_get_string_result is a @Slot(result=str)
        # and can be called with BlockingQueuedConnection.

        returned_value = QMetaObject.invokeMethod(
            self.browser_window,
            "_execute_js_and_get_string_result",
            Qt.BlockingQueuedConnection, # Must be blocking to get the result
            Q_RETURN_ARG(str),           # Specify return type
            Q_ARG(str, js_code_to_get_response) # Argument
        )
        
        if returned_value is not None:
            response_text = returned_value
        else:
            # This case might occur if the invokeMethod call itself fails,
            # or if the slot doesn't return a string as expected.
            response_text = "Error: Failed to retrieve response or invalid return from JS execution."
            
        print(f"API: get_last_response attempt, received: '{response_text[:100]}...'") # Log first 100 chars
        return response_text

    def get_debug_html(self) -> str:
        """
        Retrieves the full HTML content of the currently loaded page in the browser.

        This is primarily a debugging tool. It checks for browser readiness and then
        calls the `get_current_page_html_for_debug` method on the `BrowserWindow`
        instance (via `QMetaObject.invokeMethod` in a blocking manner) to get the HTML.

        Args:
            None

        Returns:
            str: The full HTML content of the page as a string.
                 Returns an error message string if the browser is not ready or
                 if the HTML retrieval fails.
        """
        if not self.browser_window or not self.qt_thread or not self.qt_thread.is_alive() or not self.browser_ready_event.is_set():
            print("API Error: Browser not launched, not ready, or Qt thread not alive. Cannot get debug HTML.")
            return "Error: Browser not available for debug HTML."

        html_content = ""
        # Call get_current_page_html_for_debug using BlockingQueuedConnection
        returned_value = QMetaObject.invokeMethod(
            self.browser_window,
            "get_current_page_html_for_debug",
            Qt.BlockingQueuedConnection,
            Q_RETURN_ARG(str) # Expecting a string return
        )

        if returned_value is not None:
            html_content = returned_value
        else:
            html_content = "Error: Failed to retrieve debug HTML."
        
        return html_content

    def shutdown_browser(self):
        """
        Shuts down the browser and the associated Qt application thread.

        This method attempts a graceful shutdown by:
        1. Asking the `BrowserWindow` to close (if it exists).
        2. Asking the `QApplication` to quit (if it exists).
        3. Joining the Qt thread with a timeout to allow it to terminate.

        It handles cases where the browser might not be running or might have
        already been shut down. State variables are reset after successful shutdown.

        Args:
            None

        Prints:
            Informational messages about the shutdown process.
            A warning if the Qt thread does not terminate within the timeout.
        
        Returns:
            None.
        """
        if not self.qt_thread or not self.qt_thread.is_alive():
            print("API: Browser not running or already shut down.")
            if self.qt_thread and not self.qt_thread.is_alive(): 
                 self.qt_thread.join(timeout=1) # Attempt to clean up thread object
            self.qt_thread = None
            self.app = None 
            self.browser_window = None 
            self.browser_ready_event.clear()
            return

        print("API: Attempting to shutdown browser...")

        if self.browser_window:
            QMetaObject.invokeMethod(self.browser_window, "close", Qt.QueuedConnection)

        if self.app:
            QMetaObject.invokeMethod(self.app, "quit", Qt.QueuedConnection)
        
        self.qt_thread.join(timeout=10) 
        if self.qt_thread.is_alive():
            print("API Warning: Qt thread did not terminate after shutdown request.")
        else:
            print("API: Qt thread terminated.")

        # Reset state
        self.app = None
        self.browser_window = None
        self.qt_thread = None
        self.browser_ready_event.clear()
        print("API: Browser shutdown process completed.")

    def upload_file(self, file_path: str) -> bool:
        """
        Attempts to 'upload' a file by interacting with a file input element on the page.

        Note: This is currently a placeholder implementation. Due to web security
        restrictions, JavaScript cannot programmatically set the value of a file input
        element. This method will simulate the attempt and log warnings. It is
        expected to return `False`.

        The method checks for browser readiness and file existence before proceeding.
        The actual (simulated) file handling is done by `_handle_file_upload` in
        `BrowserWindow`, called via `QMetaObject.invokeMethod`.

        Args:
            file_path (str): The local path to the file to be "uploaded".

        Returns:
            bool: Always `False` in the current placeholder implementation,
                  indicating the "upload" did not truly occur. Also `False` if the
                  browser is not ready or the file does not exist.
        """
        if not self.browser_window or not self.qt_thread or not self.qt_thread.is_alive() or not self.browser_ready_event.is_set():
            print("API Error: Browser not launched, not ready, or Qt thread not alive for file upload.")
            return False

        absolute_file_path = os.path.abspath(file_path)
        if not os.path.exists(absolute_file_path):
            print(f"API Error: File not found at path: {absolute_file_path}")
            return False

        upload_successful = False
        returned_value = QMetaObject.invokeMethod(
            self.browser_window,
            "_handle_file_upload",
            Qt.BlockingQueuedConnection,
            Q_RETURN_ARG(bool),
            Q_ARG(str, absolute_file_path)
        )

        if returned_value is not None: # Should be bool
            upload_successful = returned_value
        else:
            # This case implies an issue with the invokeMethod call itself or return type mismatch
            print(f"API Warning: QMetaObject.invokeMethod for _handle_file_upload returned None (expected bool). Path: {absolute_file_path}")
            upload_successful = False 
            
        print(f"API: Attempted file upload for '{absolute_file_path}'. Result: {upload_successful}")
        return upload_successful


if __name__ == '__main__':
    # This block provides a basic demonstration of the API.
    # For more comprehensive examples, see `gemini_browser/main.py`.
    
    print("GeminiBrowserAPI self-test/demonstration (run gemini_browser/main.py for a better example)")
    api = GeminiBrowserAPI()
    
    print("Launching browser...")
    api.launch_browser()

    if api.browser_ready_event.is_set():
        print("\nBrowser is ready. Demonstrating API calls:")
        
        # Basic text sending and response retrieval
        test_message = "Hello Gemini, this is a test from api.py's __main__."
        print(f"\nSending text: '{test_message}'")
        api.send_text(test_message)
        
        print("Waiting for 10 seconds for potential response...")
        time.sleep(10) 
        
        print("\nGetting last response...")
        response = api.get_last_response()
        print(f"API received response: '{response}'")
        
        # Debug HTML
        # print("\nGetting debug HTML (first 200 chars)...")
        # html = api.get_debug_html()
        # print(html[:200] + "..." if html else "No HTML retrieved.")

        # File upload (placeholder)
        # Create a dummy file for the test
        dummy_api_file_path = "dummy_api_test_upload.txt"
        try:
            with open(dummy_api_file_path, "w") as f:
                f.write("Test content from api.py")
            print(f"\nAttempting placeholder file upload for: {dummy_api_file_path}")
            upload_status = api.upload_file(dummy_api_file_path)
            print(f"Placeholder upload status: {upload_status}")
        except IOError as e:
            print(f"Error creating dummy file: {e}")
        finally:
            if os.path.exists(dummy_api_file_path):
                os.remove(dummy_api_file_path)
                
        print("\nDemonstration complete. Browser window will remain open if not headless.")
        print("Press Ctrl+C in terminal or close the browser window to exit.")
        
        if api.qt_thread and api.qt_thread.is_alive():
            api.qt_thread.join() # Wait for browser thread to finish if user closes window

    else:
        print("\nBrowser did not become ready. API demo skipped.")

    print("\nShutting down browser from api.py __main__...")
    api.shutdown_browser()
    
    if api.qt_thread and api.qt_thread.is_alive(): # Final check
        print("Main thread: Waiting for lingering Qt thread to finish after shutdown call...")
        api.qt_thread.join(timeout=5)
        if api.qt_thread.is_alive():
             print("Main thread: Qt thread still alive after final join attempt in __main__.")
    
    print("\nAPI __main__ demonstration finished.")
