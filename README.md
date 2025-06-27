DETWEETER
Tweet Deletion Script

This Python script uses Selenium to automatically log into your X (Twitter) account and delete tweets, designed to run from your own computer.

This script performs permanent actions (deleting tweets) on your account. It is recommended to download your Twitter archive before running a large-scale deletion.

Prerequisites

Before you begin, you must have the following installed on your Windows computer:
Python (LINK) — during installation, check the "Add Python to PATH" box.
Firefox (LINK)

Setup Instructions

1. Download the project files and place them together in a new folder on your computer.

2. Configure your login credentials. The safest method is to create a file named exactly ".env", open it with a text editor, and paste in the following:

    TWITTER_HANDLE=YourHandle

    TWITTER_PASS=YourPassword
    
    NUM_TO_DELETE=10

3. Replace the placeholder text with your information. Twitter handle means the @username, password is self-explanatory, and NUM_TO_DELETE will accept a specific number (or 0 to delete ALL unbookmarked tweets)

4. Open Command Prompt (search "cmd" in taskbar) and navigate to your project folder using the "cd" command. If it's in your Downloads, for instance, the command would be "cd downloads".

5. Install library dependencies in project folder by inputting "pip install -r requirements.txt".  This will install Selenium, Webdriver-Manager, and Python-Dotenv.

6. While still in the project directory in Command Prompt, run the program with the command "python detweeter.py".

7. The script will run, opening a Firefox window to log you in, navigate to the appropriate page, and begin deleting tweets. Progress is tracked in Command Prompt logs and will exit automatically once complete.

LLM-WRITTEN UPDATE:

# DETWEETER
### Tweet Deletion Script

This Python script uses Selenium to automatically log into your X (Twitter) account and delete your tweets. It provides a simple graphical user interface (GUI) to enter your credentials and settings, and it runs directly on your own computer.

> **Warning:** This script performs permanent actions (deleting tweets) on your account. It is highly recommended to [download your Twitter Archive](https://twitter.com/settings/your_twitter_data) before running a large-scale deletion.

---

### Prerequisites

Before you begin, you must have the following installed on your computer:

*   **Python:** [Download from python.org](https://www.python.org/downloads/). During installation, it is crucial that you check the box that says **"Add Python to PATH"**.
*   **A Supported Web Browser:**
    *   [Mozilla Firefox](https://www.mozilla.org/en-US/firefox/new/)
    *   [Google Chrome](https://www.google.com/chrome/)

---

### Setup and Usage

**1. Download the Project**

Download all the project files (`detweeter.py`, `requirements.txt`, etc.) and place them together in a new, empty folder on your computer (e.g., inside `C:\Users\YourUser\Documents\Detweeter`).

**2. Install Dependencies**

*   Open the **Command Prompt** (you can find it by searching for "cmd" in the Windows Start Menu).
*   Navigate to the folder where you saved the project files using the `cd` command. For example:
    ```cmd
    cd Documents\Detweeter
    ```
*   Once you are in the correct directory, run the following command to install the necessary Python libraries:
    ```cmd
    pip install -r requirements.txt
    ```

**3. Run the Script**

*   In the same Command Prompt window, run the script with the following command:
    ```cmd
    python detweeter.py
    ```

**4. Use the GUI**

*   A control panel window will appear.
*   **Select Browser:** Choose either Firefox or Chrome.
*   **Enter Credentials:** Type in your X (Twitter) `@handle` and `Password`.
*   **Set Deletion Count:** Enter the number of recent tweets you wish to delete. To delete **all** of your tweets (except for those you've bookmarked), enter `0`.
*   Click **"Start Deletion"**.

The script will now open your chosen browser, log you in, and begin deleting tweets from your profile page. You can monitor its progress in the Command Prompt window. Once it's finished, the browser will close and a confirmation message will appear.