import sys
import time
import tkinter as tk
from tkinter import messagebox
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.firefox import GeckoDriverManager

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

def create_gui_and_get_settings():
    """Creates a tkinter GUI window to get user settings."""
    
    # This dictionary will hold our settings
    settings = {}
    
    # This function is called when the "Start" button is clicked
    def on_submit():
        handle = handle_entry.get().strip().lstrip('@')
        password = password_entry.get()
        num_str = num_entry.get()

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
        
        # Store valid settings in the dictionary
        settings['handle'] = handle
        settings['password'] = password
        settings['num_to_delete'] = num_to_delete
        
        # Close the window
        root.destroy()

    # --- GUI Layout ---
    root = tk.Tk()
    root.title("Detweeter Setup")
    root.geometry("350x200") # Set window size
    root.resizable(False, False) # Make window not resizable

    frame = tk.Frame(root, padx=10, pady=10)
    frame.pack(expand=True, fill='both')

    # Title
    tk.Label(frame, text="DETWEETER", font=("Helvetica", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 10))

    # Inputs and Labels
    tk.Label(frame, text="Handle (@)").grid(row=1, column=0, sticky='w', padx=5, pady=5)
    handle_entry = tk.Entry(frame, width=30)
    handle_entry.grid(row=1, column=1, padx=5, pady=5)

    tk.Label(frame, text="Password").grid(row=2, column=0, sticky='w', padx=5, pady=5)
    password_entry = tk.Entry(frame, show="*", width=30)
    password_entry.grid(row=2, column=1, padx=5, pady=5)

    tk.Label(frame, text="Number to Delete").grid(row=3, column=0, sticky='w', padx=5, pady=5)
    num_entry = tk.Entry(frame, width=30)
    num_entry.grid(row=3, column=1, padx=5, pady=5)
    num_entry.insert(0, "10") # Default value

    tk.Label(frame, text="Enter 0 to delete all unbookmarked tweets.", font=("Helvetica", 8)).grid(row=4, column=1, sticky='w', padx=5)

    # Submit Button
    submit_button = tk.Button(frame, text="Start Deletion", command=on_submit, bg='green', fg='white')
    submit_button.grid(row=5, column=0, columnspan=2, pady=15)

    # Start the GUI event loop
    root.mainloop()
    
    # Return the settings dictionary (or an empty one if the window was closed)
    return settings if 'handle' in settings else None

# login_to_twitter and process_tweet functions remain identical
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
        print(f"Automated login failed. You may need to solve a CAPTCHA or verify your identity.")
        print("After you've logged in and see the home feed, press Enter here to continue...")
        input()
        try:
            WebDriverWait(driver, 30).until(EC.presence_of_element_located(LOCATORS["HOME_FEED_LINK"]))
            print("Login confirmed manually.")
            return True
        except TimeoutException:
            print("Could not manually confirm login. Exiting.")
            return False
        
def process_tweet(tweet, settings, wait, driver): # check if tweet is eligible for deletion (authored by user, not bookmarked) and attempts to delete it. Returns True if deleted, False otherwise.
    try:
        # check 1: is it our tweet?
        author_handle = tweet.find_element(*LOCATORS["TWEET_AUTHOR_HANDLE"]).text[1:]
        if author_handle.lower() != settings['handle'].lower():
            return False # not our tweet, skip
        # check 2: is it bookmarked?
        if tweet.find_elements(*LOCATORS["BOOKMARK_BUTTON_EXISTS"]):
            permalink = tweet.find_element(*LOCATORS["TWEET_PERMALINK"]).get_attribute('href')
            print(f"Skipped (bookmarked): {permalink}")
            return False
        # if all checks pass, it qualifies — proceed with deletion
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
        driver.find_element(*LOCATORS["BODY"]).send_keys(Keys.ESCAPE)
        time.sleep(0.5)
        return False

if __name__ == "__main__":
    settings = create_gui_and_get_settings()
    if not settings:
        print("Operation cancelled by user. Exiting.")
        sys.exit()
    print("SETTINGS RECEIVED. BOOTING UP SELENIUM — PRESS CTRL+C IN THIS WINDOW TO ABORT")
    driver = None
    try:
        service = FirefoxService(GeckoDriverManager().install())
        firefox_options = FirefoxOptions()
        firefox_options.set_preference("layout.css.devPixelsPerPx", "0.8")
        print("Opening Firefox...")
        driver = webdriver.Firefox(service=service, options=firefox_options)
        driver.maximize_window()
        wait = WebDriverWait(driver, 10)
        if not login_to_twitter(driver, wait, settings["handle"], settings["password"]):
            sys.exit()
        profile_url = f"https://x.com/{settings['handle']}/with_replies"
        print(f"Accessing {profile_url}...")
        driver.get(profile_url)
        long_wait = WebDriverWait(driver, 20)
        long_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f"a[href='/{settings['handle']}']")))
        print("DETWEETION COMMENCING...")
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
                print(f"Target ({settings['num_to_delete']}) deletions reached.")
                break
            tweets_on_page = driver.find_elements(*LOCATORS["TWEET_ARTICLE"])
            if not tweets_on_page and stalls > 0: # avoid stalling on initial load
                stalls += 1
                print(f"No eligible tweets found. Scrolling stall count: {stalls}/3)")
                if stalls >= 3: break
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
                continue
            found_new_tweet = False
            for tweet in tweets_on_page:
                try:
                    permalink = tweet.find_element(*LOCATORS["TWEET_PERMALINK"]).get_attribute('href')
                    if permalink in processed_permalinks:
                        continue
                    found_new_tweet = True
                    processed_permalinks.add(permalink)
                    if process_tweet(tweet, settings, wait, driver):
                        deleted_count += 1
                        print(f"TWEET DELETED — TOTAL THIS SESSION: {deleted_count}")
                        time.sleep(1) # pause for UI to settle after deletion
                        break # re-scan from the top after a successful deletion
                except (NoSuchElementException, StaleElementReferenceException):
                    continue
            else: # this 'else' block runs only if the 'for' loop completes without a 'break'
                if found_new_tweet:
                    stalls = 0
                    print("Visible tweets have been processed. Scrolling...")
                else:
                    stalls += 1
                    print(f"No eligible tweets found. Scrolling stall count: {stalls}/3")
                if stalls >= 3:
                    print("Scroll has repeatedly stalled — assuming end of timeline.")
                    break
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
        print(f"DETWEETER COMPLETE — TOTAL: {deleted_count}")
    except KeyboardInterrupt:
        print("Script interrupted by user.")
    except Exception as e:
        print(f"Critical error: {e}")
        import traceback
        traceback.print_exc()
        messagebox.showerror("Critical Error", f"A critical error occurred:\n\n{e}\n\nSee console for details.")
    finally:
        if driver:
            print("Closing Firefox.")
            driver.quit()
        print("Exiting Script.")
        time.sleep(1)