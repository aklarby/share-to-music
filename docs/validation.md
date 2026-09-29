# Validation record

Initial validation: September 28, 2026, macOS 26.5.1, Python 3.14.7, yt-dlp 2026.08.19, FFmpeg 9.0.1.

| Check | Result |
| --- | --- |
| Unit/integration suite | 22 tests passed locally |
| Audio conversion | Generated a one-second test tone, converted it with real FFmpeg, verified AAC and metadata with ffprobe |
| URL and argument safety | Tested host allowlisting, bad schemes/ports, collection URLs, hostile input, bounded plain-URL stdin (including missing/oversized/multiple URLs), legacy Base64, and redirect restrictions |
| Queue and recovery | Tested duplicate shares, failed downloads, import retries without redownloading, interrupted-job recovery, and concurrent-worker exclusion |
| Installer | Installed and uninstalled in an isolated temporary path containing spaces/quotes; retained audio and verified generated command/plist |
| Music AppleScript | Compiled against the installed Music scripting dictionary |
| YouTube network smoke check | Successfully resolved metadata for `jNQXAC9IVRw`; no audio or library changes from this check |
| SoundCloud network smoke check | Successfully resolved metadata for the upstream `123998367` test fixture; no audio or library changes from this check |
| Shortcut signing | Apple's `shortcuts sign --mode anyone` produced the distributable |
| Shortcut import | Imported into macOS Shortcuts; checked shared-input, first-item, plain URL SSH Input coerced to Text, fixed command/authentication placeholders, output variable, and Share Sheet setting in the native editor |
| Tailscale action definitions | Read from an export of the user's native iPhone Connect/Use Exit Node actions; app intent IDs and metadata are included in the generator |
| SoundCloud local end-to-end test | User-provided short link resolved, downloaded, converted, and imported into the real Music library through the installed background worker; completed with a persistent Music ID |
| Music import recovery | Reproduced a library-query timeout and a post-import metadata write error; fixed indexed duplicate lookup and removed redundant comment write in v0.1.1; retry confirmed the existing track, with one matching library entry |
| Direct Shortcut launch | Native no-input behavior set to Ask For → Text and copied from an exported workflow into the template; Share Sheet input remains supported |
| iPhone SSH and helper diagnostics | User confirmed `SSH_OK`, then a separate diagnostic returned the correct login, all dependency checks, a loaded worker, and the completed queue entry. Tested using the Mac’s LAN IPv4 address on home Wi-Fi with the selected exit node. The older Base64 submission action stalled; see the successful revised submission test below. |
| iPhone SoundCloud submission and Mac import | With v0.1.2 plain-URL SSH input, a real iPhone returned a queued job ID; the background worker resolved the short link, downloaded, converted, and imported into Music in about 29 seconds on its first attempt. Tested on home Wi-Fi with the selected home exit node. |
| iPhone Music sync | User confirmed the phone-submitted track appeared in the iPhone Music library after the Mac import. Sync timing remains controlled by Music. |
| Key-only SSH documentation | Configuration syntax/effective options verified with a temporary SSH configuration and temporary host key; system settings were not changed |
| Documentation screenshots | Captured from the macOS Shortcut, plus a real iPhone screenshot supplied by the user |

An older yt-dlp test video (`BaW_jenozKc`) was unavailable during the network smoke check; it remains a syntactically valid offline fixture in the automated tests.

## Checks that still need a configured device pair

A real iPhone → Tailscale/exit node → SSH → background Music import path has been verified for a SoundCloud share on home Wi-Fi. The user also confirmed that the newly imported track appeared in Music on the iPhone, validating the full round trip for this test. Cellular routing remains unverified. YouTube audio downloading has not been tested end to end. Automated Music import calls are mocked; the SoundCloud phone submission and background library import above used the real installed helper and Music app.

Before relying on the workflow, follow the [first-run check](setup.md#first-run-check) with a short recording you own. Confirm the Mac's import independently from the phone's sync. This is especially important because macOS Automation approval is tied to the process launching the Music request.

## Updating screenshots or the Shortcut

Generate and sign with `python3 scripts/build_shortcut.py --sign`. Import the signed file into Shortcuts and inspect every variable connection. The URL-input and Show Result actions use text-token strings; bare attachment dictionaries can import without visibly connecting the fields.

Capture only the Shortcut editor with placeholder Host/User values. Do not include account settings, private keys, personal shortcuts, unrelated windows, or private URLs. After editing the generator, rebuild both source files and the signed file together.
