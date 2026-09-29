# Troubleshooting

## Names or artwork were not updated

AI runs on the Mac before a new audio file is imported. Run `doctor` to check whether AI setup passed, and inspect the job log for model/artwork fallback messages. Import **Clean Music Tags** on that Mac, keep its exact name, turn **Follow Up** off, then run `"$HOME/.local/bin/share-to-music" setup-ai` to complete permissions and verify JSON output. After a model invocation fails, setup must pass again before later jobs invoke the model.

The model's title and artist are used directly. A missing field uses the source tag. Artwork can fall back to the source thumbnail or be absent if retrieval/embedding fails. Completed imports and retained M4As are deliberately unchanged; sharing the same URL again does not retag an existing track. See the [metadata guide](metadata.md).

## The phone keeps spinning

The Share Sheet Shortcut connects the network, logs into SSH, and **queues** one URL. It does not wait for downloading, conversion, Music import, or phone syncing. Those happen later. If a queue-confirmation result is already visible, dismiss that result to finish the Shortcut.

Check the Mac in Terminal:

```sh
"$HOME/.local/bin/share-to-music" status
```

| Mac status | Meaning |
| --- | --- |
| No jobs yet | No link has reached this user's queue; investigate the phone actions or SSH |
| `queued` | Saved on Mac, waiting for the worker (normally up to 15 seconds when idle) |
| `resolving` | Resolving the link and checking media metadata |
| `downloading` | Downloading **or converting** audio; this version groups both under this state |
| `importing` | Asking Music to add the converted file |
| `complete` | Music confirmed the Mac import; phone/cloud sync has its own timing |
| `failed` | Read the error with `status JOB_ID`; correct the cause, then retry |

This reports stages, not a percentage. For an active job, `status JOB_ID` also shows its log path. If older jobs exist, look for a new job ID or use `status --json` to inspect timestamps instead of assuming an old entry is the current share.

On the iPhone, inspect which action is highlighted: **Connect**, **Use Exit Node**, or **Run Script Over SSH**. Finish any VPN permission or SSH host-key prompt. A server fingerprint prompt proves the server was reached, not that the phone's key was accepted. Compare the phone's public-key fingerprint using the [SSH guide](ssh.md).

### Test SSH without downloading

Duplicate the Shortcut and name the copy **Check Share to Music**. Remove **Get URLs** and **First Item** (plus **Base64 Encode** if upgrading an older template); clear the SSH action’s **Input**; turn off **Show in Share Sheet** for the copy. Keep the two Tailscale actions, SSH settings, and Show Result.

First replace only the copy's SSH script with this one-line connection check (press Return after it):

```sh
/usr/bin/printf 'SSH_OK\n'
```

Run the copy directly on the iPhone. Seeing `SSH_OK` confirms that the phone authenticated and executed this command. It does not yet confirm that the helper works or that a URL reached the queue. If it hangs with a `.local` Host, keep the same test command and try the Mac's numeric LAN IPv4 address from **System Settings → Network → active connection → Details → TCP/IP**, while the phone has a route to that LAN. Do not use the exit node's address as the Mac's address. [Address and routing guide](tailscale.md#choose-the-right-ssh-address)

Once the minimal command works, replace it with the helper checks below. Keep the same Host, User, and SSH Key:

```sh
/usr/bin/printf 'SSH connected as: '
/usr/bin/whoami
"$HOME/.local/bin/share-to-music" doctor
"$HOME/.local/bin/share-to-music" status
```

Run the copy directly on the iPhone with no shared input. It should show the login name, helper checks, and recent queue stages. It does not download/import anything or check Music's separate Automation permission. If `SSH_OK` worked but these checks stall, compare command execution and helper behavior with the connection settings unchanged; a successful minimal test alone does not validate the whole workflow. If the helper checks succeed, set the original Shortcut to the same tested Host and User. Run it directly and paste a supported link when asked, or use **Share → Share to Music**. A queue confirmation or “Already imported into Music” confirms submission; phone sync is separate.

### Diagnostics work, but the main SSH action hangs

In a real iPhone test, the helper/status commands succeeded while the older Base64-variable submission action stalled. Version 0.1.2 passes the plain URL through SSH **Input** as **Text** and uses only this script:

```sh
"$HOME/.local/bin/share-to-music" enqueue --stdin
```

Update the repo and run `python3 scripts/install.py` on the Mac **before** updating the Shortcut. Remove the old Base64 action and the variable from the script text. Set SSH **Input → Item from List**, then tap that variable and select **Type → Text**. Keep the tested Host, User, and SSH Key. The new flow returned a queue confirmation on the phone and completed the background Mac import in testing; the precise cause of the older action's stall was not established. Older `--base64` clients remain supported by the helper.

If `--stdin` reports “unrecognized arguments,” the installed helper is still old; rerun the installer. If the action hangs with an empty Input, connect it to the First Item output as shown above.

## The Shortcut cannot connect

Check the selected home exit node, then the route to the **Host** you chose. For LAN addressing, verify home Wi-Fi or your approved home subnet route. For direct Tailscale addressing, verify the Mac is connected to the tailnet. In both cases, the Mac needs Remote Login enabled for the correct user and TCP 22 reachable. [Network choices](tailscale.md#choose-the-right-ssh-address)

“Permission denied” normally points to authentication or allowed-user settings; “connection refused” points to SSH not listening; a timeout points to routing, name resolution, access policy, or sleep. A `.local` name working on home Wi-Fi does not prove it resolves over cellular. Test both environments. No public router port forwarding is needed.

## “Scripting actions are disabled”

Enable **Allow Running Scripts** in Shortcuts' advanced settings on the device running the Shortcut. On iPhone, look under **Settings → Apps → Shortcuts → Advanced**; older iOS versions put Shortcuts directly in Settings. On Mac, look in **Shortcuts → Settings → Advanced**. This is a user-controlled security setting; the installer does not change it.

## “Command not found”

Use the full command path from the template: `"$HOME/.local/bin/share-to-music"`. SSH does not load your usual interactive shell setup. Install the helper as the same user specified in the Shortcut. Rerun `python3 scripts/install.py` if the command or its Python interpreter moved after a Homebrew upgrade.

## A job stays queued

Run:

```sh
"$HOME/.local/bin/share-to-music" doctor
launchctl print "gui/$(id -u)/com.share-to-music.worker"
```

The worker runs only while the user's desktop session is logged in. A locked screen is different from being logged out. Queue polling is every 15 seconds, and a previous job can keep later jobs waiting. Inspect the worker logs in `~/Library/Application Support/Share to Music/logs/`. Rerun the installer to reload a missing agent.

## Download or conversion failed

Use `status JOB_ID` to locate the log. Update with `brew upgrade yt-dlp ffmpeg deno`, then `retry JOB_ID`. Sites change their download interfaces; `yt-dlp` can also encounter region limits, login requirements, rate limits, or unavailable videos. These are reported as failures rather than successful imports.

The helper intentionally ignores personal yt-dlp configs/plugins and does not extract browser cookies. Try a public track you have permission to download. Use a full SoundCloud track URL if a shortened link opens an app landing page. Some private SoundCloud links work with their built-in token; this is not general account authentication support.

Tracks need a known duration no longer than two hours. Downloads have a 250 MB advertised-size limit; converted output must be at most 190 MB. Failed partial downloads may remain in `staging/`. Remove only the failed job's staging directory if you want to discard partial data, then retry.

## Music import timed out (-1712) or returned file permission error (-54)

Version 0.1.0 scanned all library track comments for duplicates and rewrote the comment after importing. In a live test, the first query timed out; a later attempt added the track but the redundant write failed. Version 0.1.1 uses Music's indexed search, confirms an exact marker match, and keeps the comment already embedded in the M4A.

Update the repo and rerun `python3 scripts/install.py`, then `retry JOB_ID`. The retry reuses the audio and checks for an existing import. If the error persists on the current version, inspect Music for dialogs and use `status JOB_ID`; a timeout by itself does not prove that Automation permission was denied.

## Music import / Automation error (-1743)

Open Music on the Mac first. Check **System Settings → Privacy & Security → Automation** for the process macOS identifies as requesting Music control, and approve it if you trust this installation. Keep the desktop unlocked during initial setup so you can see permission dialogs.

macOS can distinguish a Terminal-launched process from the LaunchAgent. `doctor --music` tests the former, not the latter. If the background worker cannot obtain approval, stop it and process the queue from an approved Terminal as a fallback:

```sh
launchctl bootout "gui/$(id -u)/com.share-to-music.worker"
"$HOME/.local/bin/share-to-music" retry JOB_ID
"$HOME/.local/bin/share-to-music" worker
```

This fallback requires you to run `worker` again for future shares. After fixing background permission, rerun the installer to restore automatic processing. Do not disable system-wide macOS security controls. The converted file remains in `audio/` after an import failure, so retry normally does not download it again.

## The job completed, but the song is missing on iPhone

First find and play it in Music on the Mac. Then check Sync Library, subscription, Apple Account, and the track's cloud status. Apple decides whether and when an imported track is uploaded or matched. The helper cannot force or verify cloud availability.

Without cloud syncing, sync the selected music with Finder. Download a synced track inside the iPhone Music app for offline playback. See [Apple's Sync Library troubleshooting](https://support.apple.com/118287).

## Repeated shares, deleted songs, or a different Music library

Sharing the same normalized URL returns its existing job. SoundCloud short/full links may create separate queue rows, but a common source ID and Music comment marker prevent repeated imports made by this tool. Files previously imported outside this tool can still be duplicates.

Do not edit/remove the `share-to-music:...` comment on imported tracks if you want import retries to remain idempotent. A completed queue entry stays complete even if you later delete the track or switch Music libraries. To restore a deleted track, import its retained file from the `audio/` directory using Music's File menu. This version assumes one active Music library per Mac user.

## Reporting a bug

Include macOS/iOS versions, `share-to-music --version`, `yt-dlp --version`, the failed stage, and a redacted error. Remove private links, tokens, IPs/hostnames, usernames, and local paths from logs/screenshots. Please do not attach audio, SSH keys, passwords, or your queue database.
