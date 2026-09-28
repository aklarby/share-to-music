# Validation record

Initial validation: September 28, 2026, macOS 26.5.1, Python 3.14.7, yt-dlp 2026.08.19, FFmpeg 9.0.1.

| Check | Result |
| --- | --- |
| Unit/integration suite | 19 tests passed locally |
| Audio conversion | Generated a one-second test tone, converted it with real FFmpeg, verified AAC and metadata with ffprobe |
| URL and argument safety | Tested host allowlisting, bad schemes/ports, collection URLs, hostile input, Base64, and redirect restrictions |
| Queue and recovery | Tested duplicate shares, failed downloads, import retries without redownloading, interrupted-job recovery, and concurrent-worker exclusion |
| Installer | Installed and uninstalled in an isolated temporary path containing spaces/quotes; retained audio and verified generated command/plist |
| Music AppleScript | Compiled against the installed Music scripting dictionary |
| YouTube network smoke check | Successfully resolved metadata for `jNQXAC9IVRw`; no audio or library changes from this check |
| SoundCloud network smoke check | Successfully resolved metadata for the upstream `123998367` test fixture; no audio or library changes from this check |
| Shortcut signing | Apple's `shortcuts sign --mode anyone` produced the distributable |
| Shortcut import | Imported into macOS Shortcuts; checked shared-input, first-item, Base64, SSH command/authentication placeholders, output variable, and Share Sheet setting in the native editor |
| Tailscale action definitions | Read from an export of the user's native iPhone Connect/Use Exit Node actions; app intent IDs and metadata are included in the generator |
| Documentation screenshots | Captured from the macOS Shortcut, plus a real iPhone screenshot supplied by the user |

An older yt-dlp test video (`BaW_jenozKc`) was unavailable during the network smoke check; it remains a syntactically valid offline fixture in the automated tests.

## Checks that still need a configured device pair

The initial release has **not** been verified through a real iPhone → Tailscale/exit node → SSH → background Music import → iPhone cloud-sync round trip. Automated Music import calls are mocked. Real media downloading, VPN connection and exit-node selection, a live SSH connection, and background Automation permission also need device-level validation.

Before relying on the workflow, follow the [first-run check](setup.md#first-run-check) with a short recording you own. Confirm the Mac's import independently from the phone's sync. This is especially important because macOS Automation approval is tied to the process launching the Music request.

## Updating screenshots or the Shortcut

Generate and sign with `python3 scripts/build_shortcut.py --sign`. Import the signed file into Shortcuts and inspect every variable connection. The URL-input and Show Result actions use text-token strings; bare attachment dictionaries can import without visibly connecting the fields.

Capture only the Shortcut editor with placeholder Host/User values. Do not include account settings, private keys, personal shortcuts, unrelated windows, or private URLs. After editing the generator, rebuild both source files and the signed file together.
