# Troubleshooting

## The Shortcut cannot connect

Check Tailscale first: both devices must be connected to the same tailnet and the selected home exit node must be online. Confirm the Mac is awake, Remote Login is enabled for the right user, and Host is the Mac's Tailscale IP/full MagicDNS name. “Permission denied” usually means the username/key/password is wrong; “connection refused” usually means SSH is not listening; a timeout usually means network reachability, access policy, or sleep.

The Shortcut connects to Tailscale and uses the selected exit node before SSH. Do not expect a `.local` hostname to work over cellular. See the [Tailscale guide](tailscale.md) for exit-node setup and routing details. You do not need public router port forwarding for this project.

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
