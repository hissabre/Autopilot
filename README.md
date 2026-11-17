# Autopilot for Windows

A desktop app that finds local businesses without a website, designs one for each, emails the owner, follows up, answers replies and hands you the interested ones. Python and everything else are bundled into one installer, so there's nothing extra to install.

## Get the installer (one time, about 10 minutes, free)

GitHub builds `Autopilot-Setup.exe` for you on a Windows machine:

1. Go to **github.com → New repository** and name it `autopilot`. Choose **Private**, then **Create**.
2. Click **"uploading an existing file"**. Unzip this folder and drag **everything inside it** onto the page, including the hidden `.github` folder. On Windows, turn on *View → Show → Hidden items* to see it. Then click **Commit changes**.
3. Open the **Actions** tab. "Build Windows installer" starts by itself and takes about 5 minutes.
4. When it shows a green tick, open the run and download **Autopilot-Setup** under *Artifacts*. Unzip it to get `Autopilot-Setup.exe`.

You'll find later builds in the same place. To get a permanent download link, create a tag such as `v1.0.0` (*Releases → Draft a new release → choose a tag*). The installer is then attached to that release.

## Install

Double-click `Autopilot-Setup.exe`. It installs just for your account, so it doesn't ask for admin rights.

- **"Windows protected your PC"**: the app isn't code-signed yet. Click **More info → Run anyway**. A code-signing certificate (about $100–300 a year) removes this warning for good.
- The window is drawn by Microsoft Edge WebView2, which is built into Windows 11 and most Windows 10 PCs. If yours doesn't have it, the installer offers Microsoft's download.

## First launch

A short setup asks for your studio name, the cities to search and your keys. Start in **Test mode**: the app simulates businesses, emails and replies, so you can try every screen without sending anything or paying for anything. When you're ready, go to **Settings → Connections**, paste your keys, test each one, and turn off Test mode.

| Screen | What it's for |
|---|---|
| **Overview** | Monthly revenue, the pipeline, a live progress bar, emails sent per day |
| **Leads** | Every business found. Filter, search, and click one for its details, demo site and full email thread |
| **Needs you** | Interested businesses. Mark one as a client, reply, or mark it handled |
| **Websites** | A gallery of every demo site the autopilot designed |
| **Activity** | A live log of everything it does |
| **Settings** | Studio details, connections, markets, plans and prices, limits, AI calls, app options |

The autopilot runs every hour, or whatever interval you set, while the app is open. When you close the window it keeps running in the **system tray** (near the clock). Right-click the tray icon to pause it or quit. Turn on *Settings → App → Launch with Windows* to have it start whenever you sign in.

Your data is saved in `%APPDATA%\Autopilot`: settings, keys, leads, the generated sites and `autopilot.log`. Uninstalling the app leaves this folder in place.

## Build on your own PC instead (optional)

Install Python 3.12, then run these in this folder:
```
pip install -r requirements.txt pyinstaller
pyinstaller build/autopilot.spec --noconfirm
```
Then compile `build\installer.iss` with Inno Setup 6.

## Command-line mode (for a server)

`python run.py cycle` runs the same engine without the app, for example on a $5 VPS with cron.
