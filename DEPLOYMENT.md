# Putting the working system online (PythonAnywhere, free)

GitHub Pages only shows the **design preview**. It cannot run Python or MySQL. To put the
**real, working system** on the internet, use **PythonAnywhere**. Its free plan runs Flask
apps and includes a MySQL database. It takes about 20 minutes.

In the steps below, replace **`YOURNAME`** with your PythonAnywhere username everywhere.

---

## 1. Create the account
1. Go to **https://www.pythonanywhere.com** → *Pricing & signup* → **Create a Beginner account** (free).
2. Your site will be at **`https://YOURNAME.pythonanywhere.com`**.

## 2. Create the MySQL database
1. Open the **Databases** tab.
2. Under *MySQL password*, choose a database password and click **Initialize MySQL**.
   Write the password down. This is the `DB_PASSWORD` used below.
3. Under *Create a database*, type `library_db` and click **Create**.
   PythonAnywhere names it **`YOURNAME$library_db`**.
4. Note the **Database host address** shown on that page:
   `YOURNAME.mysql.pythonanywhere-services.com`

## 3. Download the code
Open the **Consoles** tab → **Bash**, and run:
```bash
git clone https://github.com/sharon-wondergal/library_mgt_system.git
cd library_mgt_system
pip3.10 install --user -r requirements.txt
```

## 4. Create the tables and sample data
Still in the Bash console (put your own database password inside the quotes):
```bash
export DB_HOST="YOURNAME.mysql.pythonanywhere-services.com"
export DB_USER="YOURNAME"
export DB_PASSWORD="your-database-password"
export DB_NAME='YOURNAME$library_db'
python3.10 -m flask --app app init-db
```
You should see `Database 'YOURNAME$library_db' is ready.`

Use **single quotes** around the DB_NAME value. In double quotes, Bash would treat `$library_db` as a variable.

## 5. Create the web app
1. Open the **Web** tab → **Add a new web app** → *Next* → choose **Manual configuration**
   (not "Flask") → **Python 3.10** → *Next*.
2. On the Web tab, find **Code** → *WSGI configuration file* and click the link to edit it.
   **Delete everything** in that file and paste this, filling in your own values:
   ```python
   import os
   import sys

   os.environ["DB_HOST"] = "YOURNAME.mysql.pythonanywhere-services.com"
   os.environ["DB_USER"] = "YOURNAME"
   os.environ["DB_PASSWORD"] = "your-database-password"
   os.environ["DB_NAME"] = "YOURNAME$library_db"
   os.environ["SECRET_KEY"] = "type-a-long-random-sentence-here-nobody-could-guess"

   project = "/home/YOURNAME/library_mgt_system"
   if project not in sys.path:
       sys.path.insert(0, project)

   from app import app as application
   ```
   Click **Save**.
3. Back on the Web tab, under **Static files**, add:
   | URL | Directory |
   |---|---|
   | `/static/` | `/home/YOURNAME/library_mgt_system/static` |
4. Under **Security**, switch **Force HTTPS** on.
5. Click the big green **Reload** button at the top.

Open **https://YOURNAME.pythonanywhere.com** and sign in with `admin` / `admin123`.

## 6. Change the demo passwords (important on a public site)
Everyone can read the demo passwords in this repository's README. In the Bash console
(after the `export` lines from step 4):
```bash
cd ~/library_mgt_system
python3.10 -m flask --app app create-librarian
```
Enter `admin` as the username, choose the `admin` role, and set a new password. Do the
same for `librarian`.

---

## Updating the site after changing the code
Push your changes to GitHub, then in a PythonAnywhere Bash console:
```bash
cd ~/library_mgt_system && git pull
```
Then click **Reload** on the Web tab.

## Good to know
* **Free sites expire after 3 months unless you click a button.** PythonAnywhere emails
  you before that. Log in and click **"Run until 3 months from today"** on the Web tab.
* **Something not working?** On the Web tab, open the **Error log** link. The last lines
  say what went wrong. The most common causes are a typo in the WSGI file or a missing
  static files mapping.
* **"Database unavailable" page?** Check `DB_HOST`, `DB_USER`, `DB_PASSWORD` and
  `DB_NAME` in the WSGI file, then click **Reload**.
