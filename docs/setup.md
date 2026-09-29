# Setup walkthrough

Follow the [README](../README.md) to install the Mac helper. Then use these guides in order:

1. [Choose the Mac's reachable address and home exit node](tailscale.md#choose-the-right-ssh-address).
2. [Turn on Remote Login for your Mac user](ssh.md#1-turn-on-remote-login).
3. [Find the short login name and authorize the iPhone's public key](ssh.md#3-authorize-the-iphones-public-key).
4. Test a share; then [require public-key authentication on the SSH server](ssh.md#5-disable-password-login-and-require-a-public-key).
5. **Optional:** for clean song names, [install and test the Mac model helper](metadata.md). Artwork lookup is automatic; AI is enabled only after its interactive setup check passes.

## Find your Mac's connection details

Use `whoami` in Mac Terminal for **User**. For **Host**, use the Mac's home-LAN IP or a working local hostname when your phone can reach that network. A direct Tailscale IP/full MagicDNS name is another option if Tailscale is installed on the Mac. Replace the template's example address; use port `22`. A home-Wi-Fi test and an away-from-home test establish different network paths.

## Authorize the Shortcuts SSH key

The [SSH guide](ssh.md) walks through copying the key from the **iPhone**, preserving existing authorized keys, comparing fingerprints, checking the Mac's host identity, and safely disabling password login. A server-fingerprint prompt confirms you reached SSH; successful key authentication is a separate step.

The Mac's SSH server authenticates this connection as your user. The Shortcut sends the plain URL through the SSH action’s **Input** field and runs this fixed command:

```sh
"$HOME/.local/bin/share-to-music" enqueue --stdin
```

Set **Input** to the **Item from List** variable from First Item. Tap that variable and change **Type** to **Text**. The downloadable Shortcut already wires this correctly. Keep the URL out of the script text: sending it as input avoids shell quoting issues. The helper validates it and returns a queue confirmation; it does not wait for downloading or phone sync.

## Build the Shortcut manually

If downloading the signed file is inconvenient, create a Shortcut named **Share to Music**:

| Order | Action | Configure |
| --- | --- | --- |
| 1 | Tailscale: Connect | Connect to the tailnet containing the Mac |
| 2 | Tailscale: Use Exit Node | Select the approved exit node on the Mac's home network |
| 3 | Get URLs from Input | Input = **Shortcut Input** explicitly, not the preceding Tailscale action's output |
| 4 | Get Item from List | **First Item** from **URLs** |
| 5 | Run Script Over SSH | Reachable Mac LAN/Tailscale host, short username, and phone key; fixed command above; **Input = Item from List**, variable **Type = Text** |
| 6 | Show Result / Show Content | **Shell Script Result** from the SSH action |

In the Shortcut's details, enable **Show in Share Sheet**, accepting URLs, text, and Safari webpages. On the device running it, allow scripting in Shortcuts' advanced settings. Set **If there’s no input → Ask For → Text** in the Receive block. The distributed Shortcut already does this: tap Run directly in Shortcuts and paste a link when prompted, or use another app’s Share Sheet as usual.

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
