# Optional: automatic song names with a Mac model

The basic workflow works without AI. The upload's own artwork is embedded automatically; this optional step adds model-generated song names. The iPhone Shortcut still submits only a URL and returns a queue confirmation. All enrichment runs on the Mac before the new M4A is imported into Music.

## Enable the Mac model helper

1. Use a Mac that supports Apple Intelligence and has it enabled in **System Settings → Apple Intelligence & Siri**. The native **Use Model** action requires macOS 26 or later. For ChatGPT, enable the ChatGPT extension there too. No API key is needed.
2. Download [Clean Music Tags.shortcut](https://github.com/aklarby/share-to-music/raw/refs/heads/main/shortcuts/Clean%20Music%20Tags.shortcut) and open it on that Mac. Keep the name **Clean Music Tags**, since the worker invokes that name. If Shortcuts adds a numeric suffix, rename the current helper to the exact name and give older copies different names.
3. Open the helper. Its actions are **Text (Shortcut Input) → Use Model → Text (Response)**. Expand Use Model and check **ChatGPT**, **Follow Up off**, and **Output: Text** (the prompt requests JSON). You can select Apple's on-device or cloud model instead; the worker uses whatever the helper is configured to use.
4. Install/update the Python helper with `python3 scripts/install.py`. Open Music and run `"$HOME/.local/bin/share-to-music" doctor --music` to finish Music automation setup.
5. Run this while at the Mac, with Shortcuts available to show any first-run permission requests:

   ```sh
   "$HOME/.local/bin/share-to-music" setup-ai
   ```

   This sends example metadata, checks that the helper receives it and returns the expected title/artist, then records successful setup in the private runtime directory. A failed check leaves AI disabled. Complete any model permissions and rerun the command. Setup does not import a track or change your Music library.
6. Queue a real track and check its job log and Music entry. macOS permissions can differ between Terminal and the background LaunchAgent; this last check is necessary before relying on unattended use.

### What the Mac helper looks like

The first **Text** action receives **Shortcut Input**. The prompt includes that **Text** variable at the bottom, and the last **Text** action returns the model's **Response**. Shortcuts also shows the output footer. Importing the downloadable helper wires these fields for you.

![Clean Music Tags in the native Mac editor, showing the input, cleanup prompt, Response variable, and output.](images/metadata-workflow.png)

Click the small disclosure arrow beside **ChatGPT** to reveal the model options. Leave **Follow Up** unchecked and choose **Text** for **Output**. The prompt itself asks for JSON. Dictionary output caused a ChatGPT model-service error on the Mac used for testing.

![Expanded Use Model action with Follow Up off and Output set to Text.](images/metadata-settings.jpg)

After importing, run `setup-ai` in Terminal as shown above. Approve any native first-run requests while you are at the Mac. A successful result enables model calls in the background worker; opening the Shortcut alone does not enable them.

[Apple's Use Model guide](https://support.apple.com/guide/shortcuts-mac/use-apple-intelligence-in-shortcuts-mchl91750563/mac) describes available models and the Follow Up setting. The worker uses the [Shortcuts command-line interface](https://support.apple.com/guide/shortcuts-mac/run-shortcuts-from-the-command-line-apd455c82f02/mac) with input and output files.

## What the model returns

```json
{"title":"Song title","artist":"Artist"}
```

The model is asked for a clean display name: no file extension, promotional clutter, or live/unreleased/remix/version labels. The returned title and artist are used directly. Collaborating artists use **&**, not **x**. There is no confidence score or comparison of model names against source wording. A missing/null field uses its source value instead. Albums and artwork URLs are never taken from model output.

These examples were run through the native ChatGPT helper with file input and output:

| Source title | Returned title | Returned artist |
| --- | --- | --- |
| `Drake x Partynextdoor - Late Nights (Unreleased).mp3` | Late Nights | Drake & Partynextdoor |
| `Partynextdoor x Justine Bieber - Think Before (Unreleased).mp3` | Think Before | Partynextdoor & Justin Bieber |

Model responses can vary; these are observed results, not a hardcoded correction table.

The worker supplies a small JSON file containing title, track, artist, uploader, album, and duration when available. It excludes URLs, descriptions, cookies, and private-track access tokens. The prompt treats all source metadata as data rather than instructions. Temporary model files are removed after the call. With ChatGPT or Apple's cloud model, this metadata is processed by the selected provider; choose On-Device if you want the model step to remain local. Source artwork retrieval still uses the internet.

## Fallbacks and runtime

Before setup succeeds, the worker skips the model. Once enabled, each model invocation has a 45-second timeout. Missing shortcuts, permission errors, model-service errors, timeouts, invalid JSON, and oversized or unusable output fall back to source tags. A failed invocation disables later AI attempts until you rerun `setup-ai`, avoiding repeated unattended failures. Valid responses with null fields do not disable AI.

If permissions or model settings change later, macOS may show a new prompt. The worker stops waiting at its deadline and continues with source tags; it cannot dismiss system dialogs. Finish those permissions interactively before re-enabling AI.

To stop model calls while keeping automatic artwork:

```sh
"$HOME/.local/bin/share-to-music" setup-ai --disable
```

`doctor` reports whether setup has enabled AI. The per-job log records whether AI ran, the selected tags, and which artwork source succeeded. Review logs before sharing, since they can include song names and source download URLs.

## Artwork and existing tracks

For **SoundCloud links**, the worker downloads the upload's own artwork directly from thumbnail URLs supplied by SoundCloud through yt-dlp. For **YouTube links**, it uses the video's thumbnail. This works for unreleased songs too: there is no Apple catalog lookup or attempt to match an official release, and the model never supplies image URLs.

Images must come from SoundCloud or YouTube image hosts, use HTTPS, and stay within download/dimension limits. If an image fails, the worker tries another source thumbnail size, up to three distinct URLs. If none succeeds, it imports the audio without new artwork.

Tags are embedded during AAC conversion. Artwork is attached afterward by copying the AAC stream, without another lossy audio encode. If artwork embedding fails, the valid audio is retained and imported without new artwork.

All new imports, including YouTube links, use the album **SoundCloud**. A shared album artist of **Various Artists** and the compilation flag keep songs together in one Music album while preserving each song's individual artist. Source album names do not override this grouping. Each file contains its own artwork; Music's grouped album view displays one cover for the album.

This applies to newly converted audio. Already-retained M4As, completed jobs, and existing Music entries are preserved. Retrying a failed Music import reuses its existing audio and does not rerun the model or download. This is not a batch retagging command for your current library.

## Build the downloadable helper

```sh
python3 scripts/build_metadata_shortcut.py
python3 scripts/build_metadata_shortcut.py --sign
```

The generator produces reviewable JSON and an unsigned plist; Apple's signing tool produces the distributable file. It contains only the prompt and variable wiring, with no account or network credentials. The iPhone **Share to Music** template is unchanged.
