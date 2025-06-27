import sys
import time
import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.chrome import ChromeDriverManager
import traceback

# --- LOCATORS (Unchanged) ---
LOCATORS = {
    "LOGIN_IDENTIFIER_INPUT": (By.NAME, "text"),
    "NEXT_BUTTON": (By.XPATH, "//button[.//span[text()='Next']]"),
    "PASSWORD_INPUT": (By.NAME, "password"),
    "LOGIN_BUTTON": (By.XPATH, "//button[.//span[text()='Log in']]"),
    "HOME_FEED_LINK": (By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']"),
    "TWEET_ARTICLE": (By.CSS_SELECTOR, "article[data-testid='tweet']"),
    "TWEET_AUTHOR_HANDLE": (By.XPATH, ".//div[@data-testid='User-Name']//span[starts-with(text(), '@')]"),
    "TWEET_PERMALINK": (By.XPATH, ".//a[./time]"),
    "BOOKMARK_BUTTON_EXISTS": (By.XPATH, ".//button[@data-testid='removeBookmark']"),
    "MORE_OPTIONS_BUTTON": (By.XPATH, ".//button[@data-testid='caret' or @data-testid='menuButton']"),
    "DELETE_MENU_ITEM": (By.XPATH, "//div[@role='menuitem'][.//span[text()='Delete']]"),
    "DELETE_CONFIRM_BUTTON": (By.XPATH, "//button[@data-testid='confirmationSheetConfirm'][.//span[text()='Delete']]"),
    "BODY": (By.TAG_NAME, 'body'),
}

# --- NEW HELPER CLASS FOR LOGGING ---
class QueueWriter:
    """A helper class to redirect stdout to a queue."""
    def __init__(self, queue):
        self.queue = queue

    def write(self, text):
        self.queue.put(text)

    def flush(self):
        # This is needed for compatibility with sys.stdout
        pass

# --- MAIN APPLICATION CLASS ---
class DetweeterApp:
    def __init__(self, root):
        self.root = root
        self.log_queue = queue.Queue()
        self.thread = None
        self.final_message = ""
        self.setup_gui()

    def setup_gui(self):
        """Creates the styled tkinter GUI window."""
        BG_COLOR, FG_COLOR, BTN_COLOR = "#2c3e50", "#ecf0f1", "#2980b9"
        FONT_NORMAL, FONT_BOLD = ("Helvetica", 10), ("Helvetica", 16, "bold")

        self.root.title("DETWEETER")
        try:
            self.root.iconbitmap('icon.ico')
        except tk.TclError:
            print("icon.ico not found, using default icon.")
        self.root.configure(bg=BG_COLOR)
        self.root.resizable(True, True) # Allow resizing for log view

        # --- Settings Frame ---
        settings_frame = tk.Frame(self.root, padx=15, pady=15, bg=BG_COLOR)
        settings_frame.pack(expand=False, fill='x', side='top')
        tk.Label(settings_frame, text="DETWEETER", font=FONT_BOLD, bg=BG_COLOR, fg=FG_COLOR).grid(row=0, column=0, columnspan=2, pady=(0, 15))

        # Browser Selection
        browser_frame = tk.Frame(settings_frame, bg=BG_COLOR)
        browser_frame.grid(row=1, column=1, sticky='w', pady=5)
        tk.Label(settings_frame, text="Browser", font=FONT_NORMAL, bg=BG_COLOR, fg=FG_COLOR).grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.browser_choice = tk.StringVar(value="Firefox")
        self.firefox_rb = tk.Radiobutton(browser_frame, text="Firefox", variable=self.browser_choice, value="Firefox", bg=BG_COLOR, fg=FG_COLOR, selectcolor=BG_COLOR, font=FONT_NORMAL, activebackground=BG_COLOR, activeforeground=FG_COLOR)
        self.firefox_rb.pack(side='left')
        self.chrome_rb = tk.Radiobutton(browser_frame, text="Chrome", variable=self.browser_choice, value="Chrome", bg=BG_COLOR, fg=FG_COLOR, selectcolor=BG_COLOR, font=FONT_NORMAL, activebackground=BG_COLOR, activeforeground=FG_COLOR)
        self.chrome_rb.pack(side='left')

        # Inputs and Labels
        tk.Label(settings_frame, text="Handle (@)", font=FONT_NORMAL, bg=BG_COLOR, fg=FG_COLOR).grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.handle_entry = tk.Entry(settings_frame, width=30, font=FONT_NORMAL)
        self.handle_entry.grid(row=2, column=1, padx=5, pady=5)
        tk.Label(settings_frame, text="Password", font=FONT_NORMAL, bg=BG_COLOR, fg=FG_COLOR).grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.password_entry = tk.Entry(settings_frame, show="*", width=30, font=FONT_NORMAL)
        self.password_entry.grid(row=3, column=1, padx=5, pady=5)
        tk.Label(settings_frame, text="Number to Delete", font=FONT_NORMAL, bg=BG_COLOR, fg=FG_COLOR).grid(row=4, column=0, sticky='w', padx=5, pady=5)
        self.num_entry = tk.Entry(settings_frame, width=30, font=FONT_NORMAL)
        self.num_entry.grid(row=4, column=1, padx=5, pady=5)
        self.num_entry.insert(0, "10")

        # Submit Button
        self.submit_button = tk.Button(settings_frame, text="Start Deletion", command=self.start_deletion_process, font=("Helvetica", 10, "bold"), bg=BTN_COLOR, fg=FG_COLOR, relief='flat', activebackground="#3498db", activeforeground="white")
        self.submit_button.grid(row=5, column=0, columnspan=2, pady=20, ipadx=10, ipady=4)
        
        # --- Log Frame ---
        log_frame = tk.Frame(self.root, padx=15, pady=10, bg="#1e2732")
        log_frame.pack(expand=True, fill='both', side='bottom')
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        self.log_widget = scrolledtext.ScrolledText(log_frame, state='disabled', wrap=tk.WORD, bg="#1e2732", fg="#ecf0f1", font=("Consolas", 9))
        self.log_widget.pack(expand=True, fill='both')

    def start_deletion_process(self):
        """Validates settings and starts the worker thread."""
        handle = self.handle_entry.get().strip().lstrip('@')
        password = self.password_entry.get()
        num_str = self.num_entry.get()

        if not handle or not password:
            messagebox.showerror("Error", "Handle and Password are required.")
            return
        try:
            num_to_delete = int(num_str)
            if num_to_delete < 0:
                messagebox.showerror("Error", "Number to delete must be a positive integer or 0.")
                return
        except ValueError:
            messagebox.showerror("Error", "Number to delete must be a valid integer.")
            return

        settings = {
            'handle': handle,
            'password': password,
            'num_to_delete': num_to_delete,
            'browser': self.browser_choice.get()
        }
        
        # Disable GUI elements to prevent changes during operation
        self.toggle_widgets_state('disabled')
        
        # Clear log widget
        self.log_widget.config(state='normal')
        self.log_widget.delete('1.0', tk.END)
        self.log_widget.config(state='disabled')

        # Start the worker thread
        self.thread = threading.Thread(target=run_detweeter_logic, args=(settings, self.log_queue))
        self.thread.daemon = True # Allows main window to exit even if thread is running
        self.thread.start()

        # Start polling the queue for log messages
        self.poll_log_queue()

    def poll_log_queue(self):
        """Checks the queue for new messages and updates the log widget."""
        while True:
            try:
                message = self.log_queue.get_nowait()
                if message is None: # Sentinel value means the thread is done
                    self.process_finished()
                    return
                self.display_log_message(message)
            except queue.Empty:
                break
        
        # Schedule the next check
        self.root.after(100, self.poll_log_queue)

    def display_log_message(self, message):
        """Appends a message to the log widget and scrolls to the end."""
        self.log_widget.config(state='normal')
        self.log_widget.insert(tk.END, message)
        self.log_widget.see(tk.END) # Auto-scroll
        self.log_widget.config(state='disabled')
        
    def process_finished(self):
        """Called when the worker thread is complete."""
        self.toggle_widgets_state('normal')
        if self.final_message:
             messagebox.showinfo("Complete", self.final_message)
        self.final_message = "" # Reset for next run

    def toggle_widgets_state(self, state):
        """Disables or enables the input widgets."""
        self.handle_entry.config(state=state)
        self.password_entry.config(state=state)
        self.num_entry.config(state=state)
        self.submit_button.config(state=state)
        self.firefox_rb.config(state=state)
        self.chrome_rb.config(state=state)
        
# --- MAIN SELENIUM LOGIC (MOVED INTO A FUNCTION) ---

def login_to_twitter(driver, wait, login_identifier, password):
    print("Navigating to login page...")
    driver.get("https://x.com/login")
    try:
        username_field = wait.until(EC.element_to_be_clickable(LOCATORS["LOGIN_IDENTIFIER_INPUT"]))
        username_field.send_keys(login_identifier)
        next_button = wait.until(EC.element_to_be_clickable(LOCATORS["NEXT_BUTTON"]))
        driver.execute_script("arguments[0].click();", next_button)
        password_field = wait.until(EC.element_to_be_clickable(LOCATORS["PASSWORD_INPUT"]))
        password_field.send_keys(password)
        login_button = wait.until(EC.element_to_be_clickable(LOCATORS["LOGIN_BUTTON"]))
        driver.execute_script("arguments[0].click();", login_button)
        print("Waiting for home feed to confirm login...")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located(LOCATORS["HOME_FEED_LINK"]))
        print("Home feed detected. Login successful.")
        return True
    except Exception:
        print(f"\n--- MANUAL ACTION REQUIRED ---")
        print(f"Automated login failed. You may need to solve a CAPTCHA or verify your identity.")
        print("After you've logged in and see the home feed, press Enter in the console (if visible), or just wait.")
        print("The script will re-check for the home feed in 30 seconds to continue...")
        # Since we can't rely on console input(), we just wait.
        time.sleep(10) # Give some time to read
        try:
            WebDriverWait(driver, 30).until(EC.presence_of_element_located(LOCATORS["HOME_FEED_LINK"]))
            print("Login confirmed manually.")
            return True
        except TimeoutException:
            print("Could not manually confirm login. Exiting.")
            return False

def process_tweet(tweet, settings, wait, driver):
    try:
        author_handle = tweet.find_element(*LOCATORS["TWEET_AUTHOR_HANDLE"]).text[1:]
        if author_handle.lower() != settings['handle'].lower():
            return False
        if tweet.find_elements(*LOCATORS["BOOKMARK_BUTTON_EXISTS"]):
            permalink = tweet.find_element(*LOCATORS["TWEET_PERMALINK"]).get_attribute('href')
            print(f"Skipped (bookmarked): {permalink}")
            return False
        permalink = tweet.find_element(*LOCATORS["TWEET_PERMALINK"]).get_attribute('href')
        print(f"QUALIFIES FOR DELETION: {permalink}")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tweet)
        time.sleep(0.5)
        more_options_button = tweet.find_element(*LOCATORS["MORE_OPTIONS_BUTTON"])
        driver.execute_script("arguments[0].click();", more_options_button)
        delete_item = wait.until(EC.element_to_be_clickable(LOCATORS["DELETE_MENU_ITEM"]))
        driver.execute_script("arguments[0].click();", delete_item)
        confirm_button = wait.until(EC.element_to_be_clickable(LOCATORS["DELETE_CONFIRM_BUTTON"]))
        driver.execute_script("arguments[0].click();", confirm_button)
        wait.until(EC.staleness_of(tweet))
        return True
    except (TimeoutException, StaleElementReferenceException, NoSuchElementException) as e:
        print(f"  - Action failed: {type(e).__name__}. Closing menu and continuing.")
        try:
            driver.find_element(*LOCATORS["BODY"]).send_keys(Keys.ESCAPE)
            time.sleep(0.5)
        except: pass
        return False
        
def run_detweeter_logic(settings, log_queue):
    """The main worker function that runs in a separate thread."""
    # Redirect print statements to the GUI log
    sys.stdout = QueueWriter(log_queue)
    
    driver = None
    final_deleted_count = 0
    final_message = ""
    
    try:
        print("SETTINGS RECEIVED. BOOTING UP SELENIUM...")
        if settings['browser'] == "Firefox":
            service = FirefoxService(GeckoDriverManager().install())
            options = FirefoxOptions()
            options.set_preference("layout.css.devPixelsPerPx", "0.8")
            print("Opening Firefox...")
            driver = webdriver.Firefox(service=service, options=options)
        else:  # Chrome
            service = ChromeService(ChromeDriverManager().install())
            options = ChromeOptions()
            print("Opening Chrome...")
            driver = webdriver.Chrome(service=service, options=options)
        driver.maximize_window()
        wait = WebDriverWait(driver, 10)
        if not login_to_twitter(driver, wait, settings["handle"], settings["password"]):
            raise Exception("Login failed. Please check credentials and try again.")
        profile_url = f"https://x.com/{settings['handle']}/with_replies"
        print(f"Accessing {profile_url}...")
        driver.get(profile_url)
        long_wait = WebDriverWait(driver, 20)
        long_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f"a[href='/{settings['handle']}']")))
        print("\nDETWEETION COMMENCING...")
        time.sleep(2)
        if settings["num_to_delete"] == 0:
            print("Infinite Mode — deleting ALL unbookmarked tweets.")
        else:
            print(f"Finite Mode — deleting {settings['num_to_delete']} most recent unbookmarked tweets.")
        deleted_count = 0
        processed_permalinks = set()
        stalls = 0
        while True:
            if settings["num_to_delete"] > 0 and deleted_count >= settings["num_to_delete"]:
                print(f"\nTarget ({settings['num_to_delete']}) deletions reached.")
                break
            tweets_on_page = driver.find_elements(*LOCATORS["TWEET_ARTICLE"])
            if not tweets_on_page and stalls == 0:
                print("No tweets found on initial load. Scrolling down to find some.")
                stalls += 1
            found_new_tweet_this_pass = False
            for tweet in tweets_on_page:
                try:
                    permalink = tweet.find_element(*LOCATORS["TWEET_PERMALINK"]).get_attribute('href')
                    if permalink in processed_permalinks:
                        continue
                    found_new_tweet_this_pass = True
                    processed_permalinks.add(permalink)
                    if process_tweet(tweet, settings, wait, driver):
                        deleted_count += 1
                        print(f"TWEET DELETED — TOTAL THIS SESSION: {deleted_count}")
                        time.sleep(1)
                        break
                except (NoSuchElementException, StaleElementReferenceException):
                    continue
            else:
                if found_new_tweet_this_pass:
                    stalls = 0
                    print("Visible tweets have been processed/skipped. Scrolling down...")
                else:
                    stalls += 1
                    print(f"No new, unprocessed tweets found. Scrolling stall count: {stalls}/3")
                if stalls >= 3:
                    print("Scrolling has repeatedly stalled — assuming end of timeline.")
                    break
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
        print(f"\nDETWEETER COMPLETE — TOTAL: {deleted_count}")
        final_deleted_count = deleted_count
        final_message = f"Detweeter has finished.\n\nTotal tweets deleted: {final_deleted_count}"
    
    except KeyboardInterrupt:
        print("\nScript interrupted by user.")
        final_message = "Operation cancelled by user."
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        traceback.print_exc(file=sys.stdout)
        final_message = f"A critical error occurred:\n\n{e}\n\nSee log for details."
    finally:
        if driver:
            print("Closing browser...")
            driver.quit()
        print("Exiting Script.")
        # Pass final message to the main thread via the queue
        log_queue.put(final_message)
        # Put the sentinel value to signal the end
        log_queue.put(None)
        # Restore stdout
        sys.stdout = sys.__stdout__


if __name__ == "__main__":
    root = tk.Tk()
    app = DetweeterApp(root)
    # This is a bit of a hack to pass the final message from the thread to the app instance
    # The run_detweeter_logic thread will put the final message string in the queue before the sentinel
    def custom_process_finished():
        """ Override the process finished to grab the final message """
        # The final message is the last non-None item in the queue
        messages = []
        while not app.log_queue.empty():
            msg = app.log_queue.get_nowait()
            if msg is not None:
                messages.append(msg)
            else: # Found the sentinel
                break
        
        # Display any remaining log messages
        for msg in messages[:-1]:
            app.display_log_message(msg)
            
        if messages:
            app.final_message = messages[-1]

        app.toggle_widgets_state('normal')
        if app.final_message:
            messagebox.showinfo("Complete", app.final_message)
        app.final_message = ""

    # Monkey-patch the method to handle the final message correctly
    app.process_finished = custom_process_finished
    
    root.mainloop()