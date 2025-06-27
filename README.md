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