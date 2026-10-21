# Publishing this repository

The prepared project excludes compiled caches and the original private academic report. Do not add those files back to a public repository.

## Create an empty GitHub repository

Create a **public**, **empty** repository at https://github.com/new with:

- Owner: `petroviner-web`
- Name: `PiControl-RaspberryPi`
- Do not initialize with a README, .gitignore, or license. Those decisions have been handled in the prepared files (no license has yet been chosen).

Once the repository exists, the connected ChatGPT GitHub integration can upload the sources. Alternatively, extract the ZIP, open a terminal inside `PiControl-RaspberryPi`, then run:

```bash
git init
git branch -M main
git add .
git commit -m "feat: publish PiControl Raspberry Pi control dashboard"
git remote add origin https://github.com/petroviner-web/PiControl-RaspberryPi.git
git push -u origin main
```

If you already initialized the remote with a README, avoid overwriting it: clone that repository first and copy the cleaned project files into it.

## After publishing

- Verify GitHub Actions under the repository's **Actions** tab.
- Run the GUI on your Windows desktop with PySide6 and take a **real screenshot** for the README. Do not use an illustration as proof of execution.
- Test the hardware mode on Raspberry Pi and only on a protected network.
- Do not publish a token, password, Wi-Fi configuration, real GPIO device secrets, or the original student report.
