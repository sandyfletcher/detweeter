from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.firefox import GeckoDriverManager
import time
import os
import re
import getpass

LOCATORS = { # Centralized locators to maintain the script if site UI changes
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
}
# --- Helper Functions ---
def get_user_settings(): # gets login credentials from user
    # TO DO?: using environment variables for non-interactive use
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
            num_to_delete_str = input("How many tweets to delete? (A number, or 0 to delete ALL unbookmarked replies): ")
            num_to_delete = int(num_to_delete_str)
            if num_to_delete < 0:
                print("a POSITIVE number, or 0 to delete all:")
            else:
                break
        except ValueError:
            print("Needs to be a number, or 0 to delete all.  Try again:")
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
        print(f"Automated login failed, please complete login manually. {e}")
        print("After you've logged in and see the home feed, press Enter here to continue...")
        input()
        # final check to ensure we are logged in before proceeding
        try:
            WebDriverWait(driver, 30).until(EC.presence_of_element_located(LOCATORS["HOME_FEED_LINK"]))
            print("Login confirmed manually. Continuing...")
            return True
        except TimeoutException:
            print("Could not manually confirm login. Exiting.")
            return False
# --- Main Script ---
if __name__ == "__main__":
    print("STARTING - CTRL+C TO ABORT")
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
        print("Initializing Firefox WebDriver...")
        driver = webdriver.Firefox(service=service, options=firefox_options)
        driver.maximize_window()
        print("Firefox active.")
        wait = WebDriverWait(driver, 10)
        long_wait = WebDriverWait(driver, 20)
        very_short_wait = WebDriverWait(driver, 3)
        if not login_to_twitter(driver, wait, login_id, pwd):
            exit()
        target_username = target_user
        if not target_username:
            print("Cannot proceed without a target username. Exiting.")
            exit()
        # navigate to user's replies page
        profile_url = f"https://x.com/{target_username}/with_replies"
        print(f"Navigating to {profile_url}")
        driver.get(profile_url)
        long_wait.until(EC.url_contains(f"/{target_username}/with_replies"))
        print(f"Successfully on @{target_username}'s replies page.")
        time.sleep(2) # pause for page to settle
        print("--- Starting Tweet Deletion ---")
        if num_to_delete == 0:
            print("Infinite mode: Attempting to delete ALL unbookmarked replies.")
        else:
            print(f"Finite mode: Attempting to delete {num_to_delete} unbookmarked replies.")
        deleted_count = 0
        processed_tweet_permalinks = set()
        consecutive_scrolls_without_new_tweets = 0
        last_scroll_height = driver.execute_script("return document.body.scrollHeight")
        while True: # main loop for scrolling and processing
            if num_to_delete > 0 and deleted_count >= num_to_delete:
                print(f"Target of {num_to_delete} deletions reached.")
                break
            deleted_in_this_pass = False
            while True: # inner loop repeatedly finds and deletes one tweet at a time from the current view.
                tweets_on_page = driver.find_elements(*LOCATORS["TWEET_ARTICLE"])
                found_tweet_to_delete = False
                for tweet in tweets_on_page:
                    try:
                        # 1. get tweet permalink to avoid re-processing
                        permalink_element = tweet.find_element(*LOCATORS["TWEET_PERMALINK"])
                        permalink = permalink_element.get_attribute('href')
                        if permalink in processed_tweet_permalinks:
                            continue # already seen this one, skip
                        processed_tweet_permalinks.add(permalink) # add to processed set to avoid race conditions
                        # 2. check if it's our own tweet
                        author_handle = tweet.find_element(*LOCATORS["TWEET_AUTHOR_HANDLE"]).text[1:]
                        if author_handle.lower() != target_username.lower():
                            print(f"{permalink} skipped - not user-authored.")
                            continue
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tweet)
                        time.sleep(0.5)
                        # 3. check if bookmarked
                        if tweet.find_elements(*LOCATORS["BOOKMARK_BUTTON_EXISTS"]):
                            print(f"{permalink} skipped - bookmarked.")
                            continue
                        # 4. if it qualifies, delete
                        print(f"{permalink} qualifies!")
                        more_options_button = tweet.find_element(*LOCATORS["MORE_OPTIONS_BUTTON"]) # click options button
                        driver.execute_script("arguments[0].click();", more_options_button)
                        delete_item = very_short_wait.until(EC.element_to_be_clickable(LOCATORS["DELETE_MENU_ITEM"]))
                        driver.execute_script("arguments[0].click();", delete_item) # click delete from menu
                        confirm_button = wait.until(EC.element_to_be_clickable(LOCATORS["DELETE_CONFIRM_BUTTON"]))
                        driver.execute_script("arguments[0].click();", confirm_button) # confirm delete
                        wait.until(EC.staleness_of(tweet)) # wait for UI to update by confirming tweet is gone
                        deleted_count += 1
                        print(f" TWEET DELETED. TOTAL THIS SESSION: {deleted_count}")
                        deleted_in_this_pass = True
                        found_tweet_to_delete = True
                        break # exit for-loop to restart search from top
                    except StaleElementReferenceException:
                        print("  - Stale element, page changed, re-scanning view.")
                        break # restart search from top
                    except Exception as e:
                        print(f"  - Error processing one tweet: {type(e).__name__}. Skipping it.")
                        try:
                           permalink = tweet.find_element(*LOCATORS["TWEET_PERMALINK"]).get_attribute('href')
                           processed_tweet_permalinks.add(permalink) # mark as processed to not retry a failing tweet
                        except: pass
                        continue
                if found_tweet_to_delete: # if we deleted one, restart "find and destroy" loop
                    if num_to_delete > 0 and deleted_count >= num_to_delete: break
                    time.sleep(0.5) # brief pause before re-scanning
                    continue
                else: # if we looped through all tweets and found none to delete, break to scroll
                    print("No qualifying tweets in view.")
                    break
            if num_to_delete > 0 and deleted_count >= num_to_delete:
                break # exit main while-loop if target met
            # --- Scrolling Logic ---
            print("Scrolling for more tweets...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3) # wait for content to load
            new_scroll_height = driver.execute_script("return document.body.scrollHeight")
            if new_scroll_height == last_scroll_height:
                if not deleted_in_this_pass:
                    consecutive_scrolls_without_new_tweets += 1
                    print(f"Scrolled and found no new content.  Attempt {consecutive_scrolls_without_new_tweets} of 3")
                else:
                    consecutive_scrolls_without_new_tweets = 0 # reset if something is deleted
            else:
                consecutive_scrolls_without_new_tweets = 0 # new content found
            last_scroll_height = new_scroll_height
            if consecutive_scrolls_without_new_tweets >= 3:
                print("Scrolled repeatedly without finding new content. Assuming end of timeline.")
                break
        print(f"Tweet Deletion Complete - Total: {deleted_count}")
    except Exception as e:
        print(f"\nCritical Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            print("Closing Firefox.")
            driver.quit()
        print("Exiting Script.")