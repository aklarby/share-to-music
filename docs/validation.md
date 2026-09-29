# Validation record

## SoundCloud album grouping and direct artwork (v0.2.1)

- Removed catalog lookup in favor of each upload's own artwork, as requested for a library of mostly unreleased tracks.
- 47 tests passed, including real FFmpeg checks that source artwork and enrichment failures retain `album=SoundCloud`, `album_artist=Various Artists`, and the compilation flag, with unchanged AAC packet hashes. Tests also verify direct source-image retrieval, alternate thumbnail sizes, bounded failures, and no network lookup when source artwork is missing.
- Applied the tested model names to the two user-identified existing Music entries in place, then set their shared SoundCloud album, Various Artists album artist, and compilation flag. Confirmed both clean titles and their individual artists together in the native Music album view. Persistent track IDs and artwork were preserved; original metadata was backed up privately.
- Updated the retained test M4A's album grouping without re-encoding, verified all AAC packets were unchanged, and preserved its title, artist, import marker, and artwork. Kept a private backup outside the repository.
- Retrieved artwork for both example tracks directly from SoundCloud's image CDN using the final implementation. Added the missing source cover to the existing **Late Nights** entry; both tracks now have artwork without a catalog lookup.

## Automatic metadata and artwork (v0.2)

Validated on September 28–29, 2026, macOS 26.6.2, using the native ChatGPT extension and real FFmpeg. The iPhone Shortcut and its command are unchanged.

| Check | Result |
| --- | --- |
| Automated suite | 45 tests passed, including real AAC conversion, embedded artwork, unchanged AAC packet hashes after artwork attachment, model failure/source fallback, image/mux failure, generated helper wiring, and existing queue/retry behavior |
| Native model setup | `setup-ai` passed through `shortcuts run` with a small JSON input file and plain-text JSON output; no API key |
| User-provided examples | Actual ChatGPT outputs were **Late Nights — Drake & Partynextdoor** and **Think Before — Partynextdoor & Justin Bieber**; recorded as regression fixtures |
| Native output format | ChatGPT Dictionary output returned a model-service error on this Mac. Text output with a JSON prompt and CLI `--output-type public.plain-text` succeeded and is used in the downloadable helper |
| Downloadable helper | Signed with Apple's Shortcuts CLI. Decrypted signing envelope confirmed that all three actions and their variable connections match the reviewable source; signing normalizes workflow-level metadata |
| Live catalog artwork | Apple's catalog matched **Zoo Station — Nine Inch Nails**, including duration, and returned artwork for **(Ǎhk-to͝ong Bāy-Bi) Covered**; the image downloaded and normalized successfully. This check did not download or import the song |
| Live source artwork and background AI | Installed worker downloaded the provided SoundCloud track, ran the model, and produced AAC with **Think Before**, **Partynextdoor & Justin Bieber**, the import identity marker, and attached JPEG artwork |
| Queued Music completion and retry | First import attempt returned an AppleEvent timeout. After unlocking the Mac, the installed worker completed the retry using retained audio, without another download/model run. Its exact import marker matched one existing Music entry, so deduplication preserved that entry and its original title rather than creating or retagging it |
| Native Music verification | Inspected the existing track's Song Info and confirmed its source marker; read back the same persistent ID recorded by the completed queue job, with one matching entry |
| Setup screenshots | Included the user-supplied native helper screenshot and a native capture of the expanded model settings. Images show no account credentials or personal network configuration |

The newly generated M4A's clean tags and attached artwork were verified with ffprobe. Since this source already existed in Music, the live queue test verified deduplication/recovery, not insertion of a second copy with new tags. A new-source Music insertion with v0.2 and a fresh iPhone sync test remain unverified; the importer itself is unchanged. The previous device-pair checks below apply to v0.1.2.

## Original workflow (v0.1.2)

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
