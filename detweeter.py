import os
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

LOCATORS = {
    "LOGIN_IDENTIFIER_INPUT": (By.NAME, "text"),
    "NEXT_BUTTON": (By.XPATH, "//button[.//span[text()='Next']]"),
    "PASSWORD_INPUT": (By.NAME, "password"),
    "LOGIN_BUTTON": (By.XPATH, "//button[.//span[text()='Log in']]"),
    "HOME_FEED_LINK": (By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']"),
    "HOME_TIMELINE": (By.CSS_SELECTOR, "[data-testid='primaryColumn']"),
    "USER_AVATAR": (By.CSS_SELECTOR, "[data-testid='SideNav_AccountSwitcher_Button']"),
    "COMPOSE_TWEET": (By.CSS_SELECTOR, "[data-testid='SideNav_NewTweet_Button']"),
    "SEARCH_BAR": (By.CSS_SELECTOR, "[data-testid='SearchBox_Search_Input']"),
    "TWEET_ARTICLE": (By.CSS_SELECTOR, "article[data-testid='tweet']"),
    "TWEET_AUTHOR_HANDLE": (By.XPATH, ".//div[@data-testid='User-Name']//span[starts-with(text(), '@')]"),
    "TWEET_PERMALINK": (By.XPATH, ".//a[./time]"),
    "BOOKMARK_BUTTON_EXISTS": (By.XPATH, ".//button[@data-testid='removeBookmark']"),
    "MORE_OPTIONS_BUTTON": (By.XPATH, ".//button[@data-testid='caret' or @data-testid='menuButton']"),
    "DELETE_MENU_ITEM": (By.XPATH, "//div[@role='menuitem'][.//span[text()='Delete']]"),
    "DELETE_CONFIRM_BUTTON": (By.XPATH, "//button[@data-testid='confirmationSheetConfirm'][.//span[text()='Delete']]"),
    "BODY": (By.TAG_NAME, 'body'),
}

class QueueWriter: # helper to redirect stdout to queue
    def __init__(self, queue):
        self.queue = queue
    def write(self, text):
        self.queue.put(text)
    def flush(self): # needed for sys.stdout compatibility
        pass

class DetweeterApp:
    def __init__(self, root):
        self.root = root
        self.thread = None
        self.log_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.setup_gui()
        self.root.grid_rowconfigure(1, weight=1) # configure main window resizing behavior
        self.root.grid_columnconfigure(0, weight=1)
    def setup_gui(self): # styling
        BG_COLOR = "#282c34"
        FG_COLOR = "#abb2bf"
        LOG_BG_COLOR = "#21252b"
        ENTRY_BG_COLOR = "#3b4048"
        BTN_COLOR = "#61afef"
        BTN_HOVER_COLOR = "#528bcf"
        FONT_FAMILY = "Segoe UI"
        FONT_NORMAL = (FONT_FAMILY, 10)
        FONT_BOLD = (FONT_FAMILY, 16, "bold")
        FONT_MONO = ("Consolas", 10)
        self.root.title("DETWEETER")
        self.root.minsize(550, 650)
        try: # determine base path, accounting for whether it's a script or exe
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS # if app is run as a bundle, PyInstaller bootloader extends sys module by flag frozen=True and sets app path into variable _MEIPASS'
            else: # construct the full path to the icon
                base_path = os.path.dirname(os.path.abspath(__file__)) 
            icon_path = os.path.join(base_path, 'icon.ico')
            self.root.iconbitmap(icon_path)
        except tk.TclError:
            print("Intended icon.ico could not be loaded, using default fallback.")
        self.root.configure(bg=BG_COLOR)
        settings_frame = tk.Frame(self.root, padx=20, pady=20, bg=BG_COLOR)
        settings_frame.grid(row=0, column=0, sticky="ew") # expand east-west
        settings_frame.grid_columnconfigure(1, weight=1) # allow widgets column to expand
        # title
        tk.Label(settings_frame, text="DETWEETER", font=FONT_BOLD, bg=BG_COLOR, fg="white").grid(row=0, column=0, columnspan=2, pady=(0, 20))
        # browser selection
        tk.Label(settings_frame, text="Browser", font=FONT_NORMAL, bg=BG_COLOR, fg=FG_COLOR).grid(row=1, column=0, sticky='w', padx=5, pady=10)
        browser_frame = tk.Frame(settings_frame, bg=BG_COLOR)
        browser_frame.grid(row=1, column=1, sticky='w', pady=5)
        self.browser_choice = tk.StringVar(value="Firefox")
        # radio buttons
        rb_style = {'bg': BG_COLOR, 'fg': FG_COLOR, 'selectcolor': BG_COLOR, 'font': FONT_NORMAL,'activebackground': BG_COLOR, 'activeforeground': 'white', 'highlightthickness': 0, 'borderwidth': 0}
        self.firefox_rb = tk.Radiobutton(browser_frame, text="Firefox", variable=self.browser_choice, value="Firefox", **rb_style)
        self.firefox_rb.pack(side='left', padx=5)
        self.chrome_rb = tk.Radiobutton(browser_frame, text="Chrome", variable=self.browser_choice, value="Chrome", **rb_style)
        self.chrome_rb.pack(side='left', padx=5)
        # input fields and labels
        entry_style = {'width': 35, 'font': FONT_NORMAL, 'bg': ENTRY_BG_COLOR, 'fg': FG_COLOR, 'relief': 'flat', 'insertbackground': FG_COLOR}
        label_style = {'font': FONT_NORMAL, 'bg': BG_COLOR, 'fg': FG_COLOR}
        tk.Label(settings_frame, text="Handle (@)", **label_style).grid(row=2, column=0, sticky='w', padx=5, pady=10)
        self.handle_entry = tk.Entry(settings_frame, **entry_style)
        self.handle_entry.grid(row=2, column=1, padx=5, pady=5, sticky='ew')
        tk.Label(settings_frame, text="Password", **label_style).grid(row=3, column=0, sticky='w', padx=5, pady=10)
        self.password_entry = tk.Entry(settings_frame, show="*", **entry_style)
        self.password_entry.grid(row=3, column=1, padx=5, pady=5, sticky='ew')
        tk.Label(settings_frame, text="Number to Delete", **label_style).grid(row=4, column=0, sticky='w', padx=5, pady=10)
        self.num_entry = tk.Entry(settings_frame, **entry_style)
        self.num_entry.grid(row=4, column=1, padx=5, pady=5, sticky='ew')
        self.num_entry.insert(0, "10")
        # submit button
        self.submit_button = tk.Button(settings_frame, text="Start Deletion", command=self.start_deletion_process, font=(FONT_FAMILY, 10, "bold"), bg=BTN_COLOR, fg="white", relief='flat', borderwidth=0, activebackground=BTN_HOVER_COLOR, activeforeground="white")
        self.submit_button.grid(row=5, column=0, columnspan=2, pady=25, ipadx=10, ipady=5, sticky='ew')
        # log frame uses grid for resizing
        log_frame = tk.Frame(self.root, padx=10, pady=10, bg=LOG_BG_COLOR)
        log_frame.grid(row=1, column=0, sticky='nsew') # 'nsew' = expand in all directions
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        self.log_widget = scrolledtext.ScrolledText(log_frame, state='disabled', wrap=tk.WORD, bg=LOG_BG_COLOR, fg=FG_COLOR, font=FONT_MONO, relief='flat', borderwidth=0)
        self.log_widget.grid(row=0, column=0, sticky='nsew')

    def start_deletion_process(self):
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
        self.toggle_widgets_state('disabled') # disable GUI elements to prevent changes during operation
        self.log_widget.config(state='normal') # clear log widget
        self.log_widget.delete('1.0', tk.END)
        self.log_widget.config(state='disabled')
        self.thread = threading.Thread( # start the worker thread
            target=run_detweeter_logic, 
            args=(settings, self.log_queue, self.result_queue)
        )
        self.thread.daemon = True
        self.thread.start()
        self.poll_thread()
    def poll_thread(self): # check log queue and thread status
        while True: # drain log queue
            try:
                message = self.log_queue.get_nowait()
                self.display_log_message(message)
            except queue.Empty:
                break
        if self.thread.is_alive(): # check if thread has finished
            self.root.after(100, self.poll_thread) # if not, schedule another check
        else: # if it has, run completion logic
            self.process_finished()
    def display_log_message(self, message): # appends a message to log widget and scrolls to end
        self.log_widget.config(state='normal')
        self.log_widget.insert(tk.END, message)
        self.log_widget.see(tk.END)
        self.log_widget.config(state='disabled')
    def process_finished(self): # called when worker thread is complete
        self.toggle_widgets_state('normal')
        try: # get final result from the dedicated result queue
            final_message = self.result_queue.get_nowait()
            if final_message:
                 messagebox.showinfo("Complete", final_message)
        except queue.Empty: # can happen if thread crashes before sending a result
            messagebox.showwarning("Complete", "Process finished, but no final status was received.")
    def toggle_widgets_state(self, state):
        for widget in [self.handle_entry, self.password_entry, self.num_entry, 
                       self.submit_button, self.firefox_rb, self.chrome_rb]:
            widget.config(state=state)

def login_to_twitter(driver, wait, login_identifier, password):
    browser_name = driver.capabilities.get('browserName', 'unknown')
    print(f"Navigating to login...")
    driver.get("https://x.com/login")
    try:
        print("Entering username...")
        username_field = wait.until(EC.element_to_be_clickable(LOCATORS["LOGIN_IDENTIFIER_INPUT"]))
        username_field.send_keys(login_identifier)
        print("Clicking next button...")
        next_button = wait.until(EC.element_to_be_clickable(LOCATORS["NEXT_BUTTON"]))
        driver.execute_script("arguments[0].click();", next_button)
        print("Entering password...")
        password_field = wait.until(EC.element_to_be_clickable(LOCATORS["PASSWORD_INPUT"]))
        password_field.send_keys(password)
        print("Clicking login button...")
        try: # behaviour here varies across browsers — if an exception occurs we move to verification regardless
            login_button = wait.until(EC.element_to_be_clickable(LOCATORS["LOGIN_BUTTON"]))
            driver.execute_script("arguments[0].click();", login_button)
            print("Login command sent.")
        except Exception as e:
            print(f"Login interrupted by page navigation.")
    except Exception as e: # if an exception happens anywhere else in the login sequence (e.g., can't find username field), it's a genuine failure
        print(f"Fatal error occurred during login input sequence: {e}")
        return False
    print("Checking page elements to verify login...")
    max_attempts = 5  # *(1+1) = 10 second timeout
    for attempt in range(max_attempts):
        time.sleep(1)  # pause initially
        print(f"  Login check attempt {attempt + 1}/{max_attempts}...")
        if check_login_success(driver, browser_name): # robust multi-element check
            print("✓ Login successful!")
            return True
        time.sleep(1)  # pause before retrying
    print("--- LOGIN FAILED ---") # if loop finishes login has genuinely failed
    print("Login verification failed. Please check submitted credentials and try again.")
    return False

def check_login_success(driver, browser_name): # checks for multiple indicators of a successful login
    current_url = driver.current_url.lower()
    if 'login' in current_url or 'error' in current_url:
        return False
    success_checks = [
        ("home timeline", LOCATORS["HOME_TIMELINE"]),
        ("home feed link", LOCATORS["HOME_FEED_LINK"]),
        ("user avatar", LOCATORS["USER_AVATAR"]),
        ("compose tweet button", LOCATORS["COMPOSE_TWEET"]),
        ("search bar", LOCATORS["SEARCH_BAR"])
    ]
    for check_name, locator in success_checks:
        try:
            elements = driver.find_elements(*locator) # check if element is present
            if elements:
                if any(el.is_displayed() for el in elements): # extra check for visibility
                    print(f"  ✓ Success indicator found: {check_name}")
                    return True
        except Exception: # ignore errors like StaleElement which indicate page is changing
            continue
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

def run_detweeter_logic(settings, log_queue, result_queue): # main worker function that runs in a separate thread
    sys.stdout = QueueWriter(log_queue)
    driver = None
    final_message = ""
    try:
        print("Request received. Loading...")
        if settings['browser'] == "Firefox":
            service = FirefoxService(GeckoDriverManager().install())
            options = FirefoxOptions()
            options.set_preference("layout.css.devPixelsPerPx", "0.8")
            print("Opening Firefox...")
            driver = webdriver.Firefox(service=service, options=options)
        else:  # chrome
            service = ChromeService(ChromeDriverManager().install())
            options = ChromeOptions()
            options.add_argument("--force-device-scale-factor=0.8")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-gpu")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            print("Opening Chrome...")
            driver = webdriver.Chrome(service=service, options=options)
        driver.maximize_window()
        wait = WebDriverWait(driver, 10)
        if not login_to_twitter(driver, wait, settings["handle"], settings["password"]):
            raise Exception("Login failed. Please check credentials and try again.")
        profile_url = f"https://x.com/{settings['handle']}/with_replies"
        print(f"Navigating to user profile...")
        driver.get(profile_url)
        long_wait = WebDriverWait(driver, 20)
        long_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f"a[href='/{settings['handle']}']")))
        print("DETWEETION COMMENCING...")
        time.sleep(2)
        if settings["num_to_delete"] == 0:
            print("∞ MODE — ALL unbookmarked tweets.")
        else:
            print(f"# MODE — {settings['num_to_delete']} most recent unbookmarked tweets.")
        deleted_count = 0
        processed_permalinks = set()
        stalls = 0
        while True:
            if settings["num_to_delete"] > 0 and deleted_count >= settings["num_to_delete"]:
                print(f"Target ({settings['num_to_delete']}) deletions reached.")
                break
            tweets_on_page = driver.find_elements(*LOCATORS["TWEET_ARTICLE"])
            if not tweets_on_page and stalls == 0:
                print("No tweets found on initial load. Scrolling down to find some.")
            found_new_tweet_this_pass = False
            for tweet in tweets_on_page:
                if settings["num_to_delete"] > 0 and deleted_count >= settings["num_to_delete"]:
                    break # check again in case inner loop reached target
                try:
                    permalink_element = WebDriverWait(tweet, 2).until(
                        EC.presence_of_element_located(LOCATORS["TWEET_PERMALINK"])
                    )
                    permalink = permalink_element.get_attribute('href')
                    if permalink in processed_permalinks:
                        continue
                    found_new_tweet_this_pass = True
                    processed_permalinks.add(permalink)
                    if process_tweet(tweet, settings, wait, driver):
                        deleted_count += 1
                        print(f"TWEET DELETED — TOTAL THIS SESSION: {deleted_count}")
                        time.sleep(0.5) # small pause for UI to settle
                except (NoSuchElementException, StaleElementReferenceException, TimeoutException):
                    print("  - Could not process a tweet element, may have become stale or been an ad.")
                    continue
            else: # runs if the for loop completes without a break
                if found_new_tweet_this_pass:
                    stalls = 0
                    print("Visible tweets have been processed. Scrolling...")
                else:
                    stalls += 1
                if stalls >= 3:
                    print("Scrolling has repeatedly stalled — assuming end of timeline.")
                    break
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
        final_message = f"{deleted_count} TWEETS DELETED"       
    except KeyboardInterrupt:
        print("Script interrupted by user.")
        final_message = "Operation cancelled by user."
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        traceback.print_exc(file=sys.stdout)
        final_message = f"CRITICAL ERROR:\n{str(e)[:200]}"
    finally:
        if driver:
            print("Closing browser, exiting script.")
            driver.quit()
        result_queue.put(final_message)
        sys.stdout = sys.__stdout__

if __name__ == "__main__":
    root = tk.Tk()
    app = DetweeterApp(root)
    root.mainloop()