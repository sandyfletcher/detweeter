from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException
from selenium.webdriver.common.keys import Keys
import time
import os
import re
import getpass

# --- Configuration ---
GECKODRIVER_PATH = os.path.join(os.path.dirname(__file__), "geckodriver.exe")
FIREFOX_BINARY_PATH = r"C:\Program Files\Mozilla Firefox\firefox.exe"
# --- Helper Functions ---
def get_user_settings():
    login_identifier = input("Enter your Twitter/X login identifier (email, phone, or @username): ")
    password = getpass.getpass("Please enter your Twitter/X password: ") 
    target_username = None
    if login_identifier.startswith('@'):
        target_username = login_identifier[1:]
    else: 
        match = re.match(r"([a-zA-Z0-9_]+)", login_identifier.split('@')[0])
        if match:
            target_username = match.group(1)
    while True:
        try:
            num_to_delete_str = input("How many tweets would you like to delete? (Enter a number, or 0 to attempt to delete all found): ")
            num_to_delete = int(num_to_delete_str)
            if num_to_delete < 0:
                print("Please enter a non-negative number.")
            else:
                break
        except ValueError:
            print("Invalid input. Please enter a number (e.g., 5, 10, or 0).")     
    return login_identifier.strip(), password, target_username, num_to_delete
# --- Main Script ---
if __name__ == "__main__":
    print("Detweeter Starting on Firefox - Press Ctrl-C to abort")
    login_identifier, password, target_username_for_replies, num_tweets_to_delete = get_user_settings()
    if not login_identifier or not password:
        print("Login identifier and password cannot be empty. Exiting.")
        exit()
    driver = None
    manual_login_required_fallback = False 
    try:
        service = FirefoxService(executable_path=GECKODRIVER_PATH) if os.path.exists(GECKODRIVER_PATH) else FirefoxService()
        if not os.path.exists(FIREFOX_BINARY_PATH):
            print(f"ERROR: Firefox binary not found at {FIREFOX_BINARY_PATH}.")
            exit()
        firefox_options = FirefoxOptions()
        firefox_options.binary_location = FIREFOX_BINARY_PATH
        firefox_options.set_preference("layout.css.devPixelsPerPx", "0.8") # set zoom to 80% to fit more content on screen
        print("Initializing Firefox WebDriver...")
        driver = webdriver.Firefox(service=service, options=firefox_options)
        driver.maximize_window()
        print("Firefox active - zoomed out, full-screen.")
        wait = WebDriverWait(driver, 10) 
        long_wait = WebDriverWait(driver, 15) 
        very_short_wait = WebDriverWait(driver, 3) 
        # --- Login Logic ---
        print("Navigating to Twitter/X login page...")
        driver.get("https://x.com/login")
        time.sleep(1.5)
        try: 
            username_field = wait.until(EC.element_to_be_clickable((By.NAME, "text")))
            username_field.send_keys(login_identifier)
            next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Next']]")))
            driver.execute_script("arguments[0].click();", next_button)
            time.sleep(2.5) 
            password_field = wait.until(EC.element_to_be_clickable((By.NAME, "password")))
            password_field.send_keys(password)
            login_button_locators = [ (By.XPATH, "//button[.//span[text()='Log in']]"), (By.XPATH, "//div[@data-testid='ocfEnterPasswordNextButton']//span[text()='Log in']/ancestor::button[1]"), ]
            login_button_clicked_successfully = False
            for by_type, val in login_button_locators:
                try:
                    login_button_element = wait.until(EC.element_to_be_clickable((by_type, val)))
                    driver.execute_script("arguments[0].click();", login_button_element)
                    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']")))
                    print("Detected home feed. Login successful.")
                    login_button_clicked_successfully = True; break 
                except: pass
            if not login_button_clicked_successfully: manual_login_required_fallback = True
        except Exception as e_login_step:
            print(f"\nAutomated login step failed: {e_login_step}"); manual_login_required_fallback = True
        if manual_login_required_fallback:
            print("\n>>> Automated login failed or needs 2FA. Please complete login manually. <<<")
            print(">>> After FULLY logged in (on home feed), press Enter... <<<"); input()
        print("Continuing after login confirmation.")
        if not target_username_for_replies:
            try:
                profile_link = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-testid='AppTabBar_Profile_Link']")))
                href = profile_link.get_attribute('href'); target_username_for_replies = href.split('/')[-1]
                print(f"Derived @username as: {target_username_for_replies}")
            except: target_username_for_replies = input("Could not auto-derive. Enter your @username for replies: ").strip()
        if not target_username_for_replies: print("Cannot proceed. Exiting."); exit()            
        driver.get(f"https://x.com/{target_username_for_replies}/with_replies")
        long_wait.until(EC.url_contains(f"/{target_username_for_replies}/with_replies"))
        print(f"Successfully on @{target_username_for_replies}'s replies page.")
        time.sleep(2) # initial load pause
        print("\n--- Starting Tweet Deletion Process ---")
        if num_tweets_to_delete == 0:
            print("Attempting to delete ALL qualifying unbookmarked tweets found (infinite mode).")
        else:
            print(f"Attempting to delete up to {num_tweets_to_delete} qualifying unbookmarked tweets.")
        total_tweets_deleted_this_session = 0
        consecutive_scrolls_without_new_tweets = 0
        last_scroll_height = driver.execute_script("return document.body.scrollHeight")
        while True: # main loop for scrolling and processing
            if num_tweets_to_delete > 0 and total_tweets_deleted_this_session >= num_tweets_to_delete:
                print(f"Target of {num_tweets_to_delete} deletions reached.")
                break
            print("Searching for tweets on current view...")
            # always re-fetch tweet elements as DOM changes
            tweet_elements = driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
            if not tweet_elements: 
                tweet_elements = driver.find_elements(By.XPATH, "//div[@data-testid='cellInnerDiv'][.//article[@data-testid='tweet']]") # more specific for cells containing tweets
            if not tweet_elements and total_tweets_deleted_this_session == 0 : # no tweets on page initially
                 print("No tweets found on the page. Double check you're on the correct replies page.")
                 break 
            found_new_tweet_to_process_this_scroll = False
            for tweet_element in tweet_elements:
                if num_tweets_to_delete > 0 and total_tweets_deleted_this_session >= num_tweets_to_delete:
                    break # break inner loop too if target met
                try: 
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", tweet_element)
                    time.sleep(0.5) # short pause
                    author_xpath = ".//div[@data-testid='User-Name']//a[.//span[starts-with(text(), '@')]]"
                    author_span_xpath = ".//span[starts-with(text(), '@')]"
                    try:
                        author_username_element = tweet_element.find_element(By.XPATH, author_xpath)
                        tweet_author_handle = author_username_element.find_element(By.XPATH, author_span_xpath).text[1:]
                    except NoSuchElementException:
                        print("  Could not find author for a tweet element, skipping it.")
                        continue # skip this element if author can't be reliably found
                    if tweet_author_handle.lower() == target_username_for_replies.lower():
                        print(f"\n  Processing tweet by @{tweet_author_handle} (you).")
                        found_new_tweet_to_process_this_scroll = True # found a tweet by user
                        is_bookmarked = False
                        try:
                            tweet_element.find_element(By.XPATH, ".//button[@data-testid='removeBookmark']")
                            is_bookmarked = True
                        except NoSuchElementException: pass 
                        print(f"    Is bookmarked? {is_bookmarked}")
                        if not is_bookmarked: 
                            print("    Tweet qualifies for deletion (not bookmarked).")
                            more_options_button = tweet_element.find_element(By.XPATH, ".//button[@data-testid='caret']")
                            driver.execute_script("arguments[0].click();", more_options_button) 
                            time.sleep(1)
                            delete_option_locator = (By.XPATH, "//div[@role='menuitem'][.//span[text()='Delete']]")
                            delete_button_from_menu = very_short_wait.until(EC.element_to_be_clickable(delete_option_locator)) 
                            driver.execute_script("arguments[0].click();", delete_button_from_menu)
                            print("    Clicked 'Delete' from menu.")
                            time.sleep(1) 
                            final_delete_locator = (By.XPATH, "//button[@data-testid='confirmationSheetConfirm'][.//span[text()='Delete']]")
                            final_delete_btn = wait.until(EC.element_to_be_clickable(final_delete_locator))
                            print("    Clicking final 'Delete'...")
                            driver.execute_script("arguments[0].click();", final_delete_btn)
                            print("    >>> TWEET DELETED <<<")
                            total_tweets_deleted_this_session += 1
                            print(f"    Total deleted this session: {total_tweets_deleted_this_session}")
                            time.sleep(3) # allow UI to update, important before re-fetching elements
                        else: 
                            print("    Tweet is bookmarked. Skipping.")
                    else: # tweet not by target user (can be verbose)
                        print(f"  Tweet by @{tweet_author_handle}, skipping.")
                except StaleElementReferenceException:
                    print("  Stale element encountered. Will re-fetch tweets on next scroll/iteration."); break 
                except Exception as e_tweet_process:
                    print(f"  Error processing one tweet: {e_tweet_process}")
            if num_tweets_to_delete > 0 and total_tweets_deleted_this_session >= num_tweets_to_delete:
                break # exit while loop if target met
            # --- Scrolling Logic ---
            print("\nScrolling down to find more tweets...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3) # wait for new tweets to load after scroll
            new_scroll_height = driver.execute_script("return document.body.scrollHeight")
            if new_scroll_height == last_scroll_height:
                if not found_new_tweet_to_process_this_scroll and not tweet_elements: # if page was empty and stayed empty
                    print("Scrolled, but no new content and no tweets were processed. Likely end of page.")
                    consecutive_scrolls_without_new_tweets +=1
                elif not found_new_tweet_to_process_this_scroll: # scrolled but didn't find new tweets by user
                    print("Scrolled, but no new qualifying tweets by you were found in this view. May be end of your replies.")
                    consecutive_scrolls_without_new_tweets +=1
                else: # processed some tweets, reset counter
                    consecutive_scrolls_without_new_tweets = 0
            else: # scroll height changed, new content loaded
                consecutive_scrolls_without_new_tweets = 0
            last_scroll_height = new_scroll_height
            if consecutive_scrolls_without_new_tweets >= 3: # Stop if 3 scrolls find nothing new
                print("Scrolled multiple times without finding new qualifying tweets. Assuming end of replies.")
                break
        print(f"\n--- Tweet Deletion Process Finished ---")
        print(f"Total tweets deleted this session: {total_tweets_deleted_this_session}")
        time.sleep(3)
    except Exception as e: 
        print(f"A critical error occurred: {e}")
        import traceback; traceback.print_exc() 
    finally:
        if driver: 
            print("Closing Firefox browser...")
            driver.quit()
        print("Script finished.")