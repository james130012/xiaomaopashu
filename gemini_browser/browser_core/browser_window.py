# This file will contain the BrowserWindow class.
# It will be responsible for the browser's UI and core logic.

import os
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QApplication
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, QTimer, QEventLoop, QMetaObject, Slot, Signal, Property, Q_ARG, Q_RETURN_ARG, Qt, QStandardPaths

class BrowserWindow(QMainWindow):
    CHAT_INPUT_SELECTOR = "textarea" # Example: "textarea[aria-label='Message Gemini']"
    SEND_BUTTON_SELECTOR = "button[aria-label*='Send']" # Example: "button[aria-label='Send message']"
    LAST_RESPONSE_SELECTOR = "div[class*='response-content'] div[class*='markdown']" # Example, needs verification
    FILE_INPUT_SELECTOR = "input[type='file']" # General selector for file inputs

    _js_result = None
    _js_error = None
    _event_loop = None # For _execute_js_and_get_string_result

    def __init__(self, parent=None): # Added parent=None for consistency
        super().__init__(parent)
        self.setWindowTitle("Gemini Browser")

        # Ensure an application name is set for QStandardPaths
        if not QApplication.applicationName():
            QApplication.setApplicationName("GeminiBrowser")
        if not QApplication.organizationName():
            QApplication.setOrganizationName("MyCompany") # Or some other placeholder

        # Define a path for persistent storage
        storage_location = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
        # Ensure the base directory for the company/app exists before creating web_profile subdir
        if not os.path.exists(storage_location):
            os.makedirs(storage_location, exist_ok=True)
            
        profile_path = os.path.join(storage_location, "web_profile")

        # Create the directory if it doesn't exist
        if not os.path.exists(profile_path):
            os.makedirs(profile_path, exist_ok=True)

        # Create a persistent profile
        # We give it a unique name AND set a persistent storage path.
        self.profile = QWebEngineProfile("GeminiBrowserProfile", self) # "GeminiBrowserProfile" is just a name
        self.profile.setPersistentStoragePath(profile_path)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)

        # Create QWebEnginePage with the custom profile
        self.web_page = QWebEnginePage(self.profile, self)
        
        # Create the QWebEngineView (as before)
        self.web_view = QWebEngineView(self) # Pass self as parent
        # Set the custom page on the QWebEngineView
        self.web_view.setPage(self.web_page)
        
        self.setCentralWidget(self.web_view)

        self.load_url("https://gemini.google.com") # This will now use self.web_page
        self.resize(1024, 768)

    def load_url(self, url_string: str):
        qurl = QUrl(url_string)
        # Ensure this uses the web_page with the custom profile
        if hasattr(self, 'web_page'):
            self.web_page.setUrl(qurl)
        else: # Fallback for some unlikely scenario where web_page isn't init yet
            self.web_view.setUrl(qurl)


    @Slot(str)
    def _set_chat_input_text(self, text: str):
        # Sanitize text for JavaScript single-quoted string
        escaped_text = text.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
        js_code = f"""
            var el = document.querySelector('{BrowserWindow.CHAT_INPUT_SELECTOR}');
            if (el) {{
                el.value = '{escaped_text}';
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                console.log('Chat input text set.');
                // el.focus(); // Optionally focus
            }} else {{
                console.error('Chat input element not found: {BrowserWindow.CHAT_INPUT_SELECTOR}');
            }}
        """
        self.web_page.runJavaScript(js_code) # Changed from self.web_view.page()

    @Slot()
    def _click_send_button(self):
        js_code = f"""
            var el = document.querySelector('{BrowserWindow.SEND_BUTTON_SELECTOR}');
            if (el) {{
                el.click();
                console.log('Send button clicked.');
            }} else {{
                console.error('Send button element not found: {BrowserWindow.SEND_BUTTON_SELECTOR}');
            }}
        """
        self.web_page.runJavaScript(js_code) # Changed from self.web_view.page()

    @Slot(object)
    def _js_callback(self, result):
        BrowserWindow._js_result = result
        BrowserWindow._js_error = None # Reset error on successful callback
        if BrowserWindow._event_loop and BrowserWindow._event_loop.isRunning():
            BrowserWindow._event_loop.quit()

    @Slot(str, result=str)
    def _execute_js_and_get_string_result(self, js_code_to_run: str) -> str:
        BrowserWindow._js_result = None # Reset previous result
        BrowserWindow._js_error = None  # Reset previous error
        
        # Ensure the event loop is created on the correct thread if this method is called from a non-GUI thread
        # For BlockingQueuedConnection, this method runs in the thread of the QObject (BrowserWindow), which is the GUI thread.
        if not BrowserWindow._event_loop or not BrowserWindow._event_loop.thread() == self.thread():
             BrowserWindow._event_loop = QEventLoop(self) # Parent to self for thread affinity

        timer = QTimer(self) # Parent to self for thread affinity
        timer.setSingleShot(True)
        timer.timeout.connect(BrowserWindow._event_loop.quit) # Quit loop on timeout

        # Important: The callback (_js_callback) will be invoked in the main Qt thread.
        # The runJavaScript function itself is asynchronous.
        self.web_page.runJavaScript(js_code_to_run, self._js_callback) # Changed from self.web_view.page()
        
        timer.start(3000) # 3-second timeout
        BrowserWindow._event_loop.exec() # Start event loop, blocks until quit() or timeout

        timer.stop()

        if BrowserWindow._js_error:
            return f"JavaScript Error: {BrowserWindow._js_error}"
        if BrowserWindow._js_result is None: # Timeout occurred
            return "Error: JavaScript execution timed out or no result."
        
        if isinstance(BrowserWindow._js_result, str):
            return BrowserWindow._js_result
        else:
            # Attempt to convert non-string results, or handle them as errors/warnings
            try:
                return str(BrowserWindow._js_result)
            except Exception as e:
                return f"Error: Could not convert JS result to string: {e}"


    @Slot(result=str)
    def get_current_page_html_for_debug(self) -> str:
        # This method is designed to be called from other threads via QMetaObject.invokeMethod
        # with Qt.BlockingQueuedConnection, so it will execute in this (BrowserWindow's) thread.
        return self._execute_js_and_get_string_result("document.documentElement.outerHTML;")

    @Slot(str, result=bool)
    def _handle_file_upload(self, file_path: str) -> bool:
        # Research Note:
        # QWebEnginePage has a `fileChooserRequested` signal. This signal is emitted when a file input
        # on a web page is clicked by the user. We can connect to this signal and then programmatically
        # select a file using QFileDialog, and then call `QWebEnginePage.chooseFiles()` with the selected
        # file(s). This is the standard way to handle file uploads initiated by user interaction.
        #
        # However, for *programmatic* setting of a file input's value *without user interaction*
        # (i.e., from our API directly setting which file to upload), QWebEngine does not offer a direct
        # JavaScript-bridgeable API to set the `value` of an `<input type="file">` element due to
        # browser security models. Standard web browser JavaScript also cannot do this.
        #
        # Possible workarounds (complex and not guaranteed):
        # 1. If the page uses a library that creates a custom file upload widget, it might expose
        #    JavaScript functions to interact with it, but this is page-specific.
        # 2. For testing/automation, some browser automation tools might use devtools protocols
        #    or other means to bypass this, but that's outside normal QWebEngine usage.
        #
        # Conclusion for this placeholder: We acknowledge the limitation. The JS below will reflect this.

        # Sanitize file_path for use in JS string. This is a basic example.
        # A more robust approach would be to pass it differently if it contained complex characters,
        # but for a file path, this level of escaping for single quotes and backslashes is often sufficient.
        escaped_file_path = file_path.replace('\\', '\\\\').replace("'", "\\'")

        js_code = f"""
            (function(filePath) {{
                var fileInput = document.querySelector('{self.FILE_INPUT_SELECTOR}');
                if (!fileInput) {{
                    console.error('File input element not found with selector: {self.FILE_INPUT_SELECTOR}');
                    return 'false'; // Return string "false"
                }}
                console.warn("JavaScript cannot directly set the 'value' of a file input due to security restrictions.");
                console.warn("This file upload attempt (path: '" + filePath + "') via direct JS manipulation is a placeholder and likely will not function.");
                console.warn("Further research into QWebEngine-specific APIs (e.g., handling file choosers programmatically via QWebEnginePage.chooseFiles after fileChooserRequested signal) is required for robust file upload functionality when initiated by web content. Programmatic API-driven upload remains challenging.");
                // Always return string "false" from JS to indicate this limitation for now.
                return 'false';
            }})('{escaped_file_path}');
        """
        
        raw_result = self._execute_js_and_get_string_result(js_code)
        
        # Check the string result from JavaScript
        if isinstance(raw_result, str) and raw_result.lower() == 'false':
            return False
        
        # If it's not the string "false" (e.g., an error string from _execute_js_and_get_string_result,
        # or if the JS somehow returned something else), we still treat it as failure.
        print(f"BrowserWindow._handle_file_upload: JS execution returned non-'false' or error: {raw_result}")
        return False
