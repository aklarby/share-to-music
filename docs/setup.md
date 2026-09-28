# Setup walkthrough

Follow the [README](../README.md) for installation and the [Tailscale guide](tailscale.md) to connect both devices and approve your home exit node. This guide covers pairing the iPhone and Mac over SSH.

## Find your Mac's connection details

In Mac Terminal:

```sh
whoami
scutil --get LocalHostName
```

Use `whoami`'s output (for example, `alex`) for **User**. For **Host**, copy the Mac's Tailscale IP or full MagicDNS name from Tailscale's device list. The local hostname command helps identify the Mac, but do not use its `.local` name when connecting remotely. The placeholder `your-mac.your-tailnet.ts.net` must be replaced with the actual name of your Mac.

Enable **System Settings → General → Sharing → Remote Login**, restricted to the user whose Music library you want to import into. A different SSH login has a different home directory, queue, LaunchAgent, and Music library. Keep the Mac logged into that user's desktop.

## Authorize the Shortcuts SSH key

1. On the iPhone, open **Share to Music → Run Script Over SSH → Authentication** and select **SSH Key**.
2. Use the action's SSH Key controls to generate a key if necessary, then copy/share its **public key** to the Mac. Keep the private key on your device.
3. On the Mac, create the SSH configuration directory and open the authorized key list:

   ```sh
   mkdir -p "$HOME/.ssh"
   chmod 700 "$HOME/.ssh"
   touch "$HOME/.ssh/authorized_keys"
   chmod 600 "$HOME/.ssh/authorized_keys"
   nano "$HOME/.ssh/authorized_keys"
   ```

4. Append the public key as one complete line. Preserve existing keys. In nano, save with **Control-O**, press **Return**, then exit with **Control-X**.
5. Set **Host**, **Port**, and **User** in the Shortcut. On its first connection, verify that the host is your Mac before accepting its host-key prompt.

If you prefer password authentication, choose **Password** and enter the Mac account password on your own device. Do not distribute a Shortcut with a saved password. Key authentication is the recommended setup for repeated use.

The Mac's SSH server authenticates this connection as your user. The Shortcut always runs a fixed queue command with the URL as Base64 data:

```sh
"$HOME/.local/bin/share-to-music" enqueue --base64 'BASE64_ENCODED_MAGIC_VARIABLE'
```

`BASE64_ENCODED_MAGIC_VARIABLE` represents the **Base64 Encoded** variable token, not literal text to type. The downloadable Shortcut already wires it correctly.

## Build the Shortcut manually

If downloading the signed file is inconvenient, create a Shortcut named **Share to Music**:

| Order | Action | Configure |
| --- | --- | --- |
| 1 | Tailscale: Connect | Connect to the tailnet containing the Mac |
| 2 | Tailscale: Use Exit Node | Select the approved exit node on the Mac's home network |
| 3 | Get URLs from Input | Input = **Shortcut Input** explicitly, not the preceding Tailscale action's output |
| 4 | Get Item from List | **First Item** from **URLs** |
| 5 | Base64 Encode | **Encode** the previous item; Line Breaks = **None** |
| 6 | Run Script Over SSH | Mac Tailscale host/user/key; command above with **Base64 Encoded** inserted between single quotes |
| 7 | Show Result / Show Content | **Shell Script Result** from the SSH action |

In the Shortcut's details, enable **Show in Share Sheet**, accepting URLs, text, and Safari webpages. On the device running it, allow scripting in Shortcuts' advanced settings. If running from the app without shared input, supply a URL first; the normal workflow starts from another app's Share Sheet.

## First-run check

1. Open Music on the Mac and finish its setup dialogs.
2. Run `"$HOME/.local/bin/share-to-music" doctor --music` in Terminal. Resolve missing dependencies or Automation permission prompts.
3. Queue one short recording you own with `enqueue 'YOUR_TRACK_URL'`.
4. Wait for the background worker and check `status`. If Music automation is blocked, use the permission error and [troubleshooting guide](troubleshooting.md) to identify the requesting process. Terminal permission alone does not prove the LaunchAgent has permission.
5. Confirm the track is playable in Music on the Mac.
6. Unlock the iPhone, share another permitted track, confirm the selected Tailscale exit node is active, and confirm the Shortcut returns a job ID. Once local testing works, repeat over cellular to verify remote access.
7. Confirm phone syncing separately. The `complete` job state only validates the Mac import.

## Share a reusable Shortcut

The repo's signed `.shortcut` contains placeholders, not anyone's actual Mac connection details. It can be downloaded through GitHub or attached to a release.

To make an iCloud link, import the template into Shortcuts and use **Share → Copy iCloud Link** (wording depends on OS version). Do this before filling in private connection details. Apple creates that link in your Shortcuts account; the build script cannot manufacture one. An iCloud link is optional because the signed file already provides a downloadable install path.
