from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys # <-- IMPORT ADDED
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.firefox import GeckoDriverManager
import time
import os
import re
import getpass

LOCATORS = { # centralized locators to maintain the script if site UI changes
    "LOGIN_IDENTIFIER_INPUT": (By.NAME, "text"),
    "NEXT_BUTTON": (By.XPATH, "//button[.//span[text()='Next']]"),
    "PASSWORD_INPUT": (By.NAME, "password"),
    "LOGIN_BUTTON": (By.XPATH, "//button[.//span[text()='Log in']]"),
    "HOME_FEED_LINK": (By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']"),
    "PROFILE_LINK": (By.CSS_SELECTOR, "a[data-testid='AppTabBar_Profile_Link']"),
    "TWEET_ARTICLE": (By.CSS_SELECTOR, "article[data-testid='tweet']"),
    "TWEET_AUTHOR_HANDLE": (By.XPATH, ".//div[@data-testid='User-Name']//span[starts-with(text(), '@')]"),
    "TWEET_PERMALINK": (By.XPATH, ".//a[./time]"),
    "BOOKMARK_BUTTON_EXISTS": (By.XPATH, ".//button[@data-testid='removeBookmark']"),
    "MORE_OPTIONS_BUTTON": (By.XPATH, ".//button[@data-testid='caret' or @data-testid='menuButton']"),
    "DELETE_MENU_ITEM": (By.XPATH, "//div[@role='menuitem'][.//span[text()='Delete']]"),
    "DELETE_CONFIRM_BUTTON": (By.XPATH, "//button[@data-testid='confirmationSheetConfirm'][.//span[text()='Delete']]"),
    "BODY": (By.TAG_NAME, 'body'),
}
# --- Helper Functions ---
def get_user_settings(): # gets login credentials from user
    # TO DO: using environment variables for non-interactive use
    login_identifier_raw = os.getenv("TWITTER_USER") or input("Enter your Twitter @handle or username: ")
    password = os.getenv("TWITTER_PASS") or getpass.getpass("Password: ")
    # normalize the username input to handle both "user" and "@user"
    login_identifier = login_identifier_raw.strip()
    if login_identifier.startswith('@'):
        target_username = login_identifier[1:]
    else:
        target_username = login_identifier
    while True:
        try:
            num_to_delete_str = input("Enter number of tweets to delete (or enter 0 to delete ALL unbookmarked replies): ")
            num_to_delete = int(num_to_delete_str)
            if num_to_delete < 0:
                print("... a POSITIVE integer, or 0 to delete all: ")
            else:
                break
        except ValueError:
            print("Needs to be an integer, or input 0 to delete all: ")
    return login_identifier, password, target_username, num_to_delete
def login_to_twitter(driver, wait, login_identifier, password): # handles the login process with a manual fallback.
    print("Navigating to login page...")
    driver.get("https://x.com/login")
    try:
        # 1: enter username
        username_field = wait.until(EC.element_to_be_clickable(LOCATORS["LOGIN_IDENTIFIER_INPUT"]))
        username_field.send_keys(login_identifier)
        next_button = wait.until(EC.element_to_be_clickable(LOCATORS["NEXT_BUTTON"]))
        driver.execute_script("arguments[0].click();", next_button)
        # 2: enter password
        password_field = wait.until(EC.element_to_be_clickable(LOCATORS["PASSWORD_INPUT"]))
        password_field.send_keys(password)
        # 3: attempt to login
        login_button = wait.until(EC.element_to_be_clickable(LOCATORS["LOGIN_BUTTON"]))
        driver.execute_script("arguments[0].click();", login_button)
        # 4: confirm login by through home feed
        WebDriverWait(driver, 15).until(EC.presence_of_element_located(LOCATORS["HOME_FEED_LINK"]))
        print("Home feed detected. Login successful.")
        return True
    except Exception as e:
        print(f"Automated login failed — please complete login manually. {e}")
        print("After you've logged in and see the home feed, press Enter here to continue...")
        input()
        # final check to ensure we are logged in before proceeding
        try:
            WebDriverWait(driver, 30).until(EC.presence_of_element_located(LOCATORS["HOME_FEED_LINK"]))
            print("Login confirmed manually.")
            return True
        except TimeoutException:
            print("Could not manually confirm login. Exiting.")
            return False
# --- Main Script ---
if __name__ == "__main__":
    print("STARTING SCRIPT - CTRL+C TO ABORT")
    login_id, pwd, target_user, num_to_delete = get_user_settings()
    if not login_id or not pwd:
        print("Login identifier and password cannot be empty. Exiting.")
        exit()
    driver = None
    try:
        # webdriver-manager for automatic driver handling
        service = FirefoxService(GeckoDriverManager().install())
        firefox_options = FirefoxOptions()
        firefox_options.set_preference("layout.css.devPixelsPerPx", "0.8") # zoom out
        print("Initializing Firefox Session...")
        driver = webdriver.Firefox(service=service, options=firefox_options)
        driver.maximize_window()
        print("Firefox active and resized.")
        wait = WebDriverWait(driver, 10)
        long_wait = WebDriverWait(driver, 20)
        if not login_to_twitter(driver, wait, login_id, pwd):
            exit()
        target_username = target_user
        if not target_username:
            print("Cannot proceed without a target username. Exiting.")
            exit()
        # navigate to user's replies page
        profile_url = f"https://x.com/{target_username}/with_replies"
        print(f"Navigating to {profile_url}...")
        driver.get(profile_url)
        long_wait.until(EC.url_contains(f"/{target_username}/with_replies"))
        print(f"Arrived at @{target_username} reply page.")
        time.sleep(2) # pause for page to settle
        print("STARTING TWEET DELETION — CTRL+C TO ABORT")
        if num_to_delete == 0:
            print("Infinite mode: Attempting to delete ALL unbookmarked replies.")
        else:
            print(f"Finite mode: Attempting to delete {num_to_delete} unbookmarked replies.")
        deleted_count = 0
        processed_tweet_permalinks = set()
        stalls = 0
        while True:
            if num_to_delete > 0 and deleted_count >= num_to_delete:
                print(f"Target of {num_to_delete} deletions reached.")
                break
            tweets_on_page = driver.find_elements(*LOCATORS["TWEET_ARTICLE"])
            found_new_tweet_in_pass = False # tracks if we made progress by seeing a new tweet
            for tweet in tweets_on_page:
                try:
                    permalink_element = tweet.find_element(*LOCATORS["TWEET_PERMALINK"])
                    permalink = permalink_element.get_attribute('href')
                except (NoSuchElementException, StaleElementReferenceException):
                    continue # tweet structure is weird or gone, skip it.
                if permalink in processed_tweet_permalinks:
                    continue
                # If we get here, it's a new tweet. Reset stall counter later.
                found_new_tweet_in_pass = True
                processed_tweet_permalinks.add(permalink)
                # Check if tweet qualifies for deletion
                try:
                    author_handle = tweet.find_element(*LOCATORS["TWEET_AUTHOR_HANDLE"]).text[1:]
                    if author_handle.lower() != target_username.lower():
                        continue # Not our tweet
                    if tweet.find_elements(*LOCATORS["BOOKMARK_BUTTON_EXISTS"]):
                        print(f"Skipped (bookmarked): {permalink}")
                        continue
                except (NoSuchElementException, StaleElementReferenceException):
                    continue # Tweet parts disappeared, skip
                print(f"QUALIFIES FOR DELETION: {permalink}")
                try:
                    # Action sequence
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tweet)
                    time.sleep(0.5)
                    more_options_button = tweet.find_element(*LOCATORS["MORE_OPTIONS_BUTTON"])
                    driver.execute_script("arguments[0].click();", more_options_button)
                    delete_item = wait.until(EC.element_to_be_clickable(LOCATORS["DELETE_MENU_ITEM"]))
                    driver.execute_script("arguments[0].click();", delete_item)
                    confirm_button = wait.until(EC.element_to_be_clickable(LOCATORS["DELETE_CONFIRM_BUTTON"]))
                    driver.execute_script("arguments[0].click();", confirm_button)
                    # Confirmation of success
                    wait.until(EC.staleness_of(tweet))
                    deleted_count += 1
                    print(f"  -> TWEET DELETED. TOTAL THIS SESSION: {deleted_count}")
                    break # to re-scan from top
                except (TimeoutException, StaleElementReferenceException, NoSuchElementException) as e:
                    # If any part of the deletion fails, a menu might be open.
                    print(f"  - Action failed: {type(e).__name__}. Attempting to close menu and re-scan.")
                    # Sending ESCAPE key is the most reliable way to close pop-up menus/dialogs
                    driver.find_element(*LOCATORS["BODY"]).send_keys(Keys.ESCAPE)
                    time.sleep(0.5) # Give UI a moment to react
                    break # to re-scan from top with a clean slate
            # This 'else' block runs ONLY if the 'for' loop completed without a 'break'.
            # This means no tweets were deleted and no errors occurred that required a re-scan.
            else: 
                if found_new_tweet_in_pass:
                    # We saw new tweets, but they were all skipped (e.g., bookmarked). Reset stalls.
                    stalls = 0
                    print("All new tweets in view processed. Scrolling down...")
                else:
                    # We saw NO new tweets on the screen. This is a potential stall.
                    stalls += 1
                    print(f"No new tweets found in view. Scrolling down... (Stall count: {stalls}/3)")
                if stalls >= 3:
                    print("Stalled 3 times. Assuming end of timeline.")
                    break
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
        print(f"TWEET DELETION COMPLETE — TOTAL: {deleted_count}")
    except KeyboardInterrupt:
        print("\nScript interrupted by user.")
    except Exception as e:
        print(f"\nCritical Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            print("Closing Firefox session.")
            driver.quit()
        print("Exiting Script.")