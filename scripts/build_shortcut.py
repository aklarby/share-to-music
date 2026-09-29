#!/usr/bin/env python3
"""Generate an inspectable Shortcut plist and optionally sign it on macOS."""

import argparse
import json
from pathlib import Path
import plistlib
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]


def token(value):
    return {"Value": value, "WFSerializationType": "WFTextTokenAttachment"}


def text_token(value):
    return {"Value": {"string": "\ufffc", "attachmentsByRange": {"{0, 1}": value}},
            "WFSerializationType": "WFTextTokenString"}


def build():
    # Stable UUIDs keep the source reviewable and the build reproducible.
    ids = {name: str(uuid.uuid5(uuid.NAMESPACE_URL, "share-to-music/" + name)).upper()
           for name in ("connect", "exit_node", "urls", "first", "encoded", "ssh")}

    def output(name, label):
        return token({"Type": "ActionOutput", "OutputUUID": ids[name], "OutputName": label})

    actions = []

    def action(name, **parameters):
        actions.append({"WFWorkflowActionIdentifier": "is.workflow.actions." + name,
                        "WFWorkflowActionParameters": parameters})

    # Verified against an export of the native iPhone actions, then imported
    # into macOS Shortcuts. Keep device-specific node selections out of source.
    for intent, name in (("ConnectIntent", "connect"), ("UseExitNodeIntent", "exit_node")):
        actions.append({
            "WFWorkflowActionIdentifier": "io.tailscale.ipn.ios." + intent,
            "WFWorkflowActionParameters": {
                "UUID": ids[name],
                "AppIntentDescriptor": {"TeamIdentifier": "W5364U7YZB", "BundleIdentifier": "io.tailscale.ipn.ios",
                                        "Name": "Tailscale", "AppIntentIdentifier": intent},
                **({"ShowWhenRun": False} if name == "connect" else {}),
            },
        })
    action("comment", WFCommentActionText="Setup: connect Tailscale on iPhone and select your home exit node. Enable Remote Login on the Mac. Set Host to its reachable LAN or Tailscale address and User to its short login name. Authorize the iPhone's public SSH key and install the helper. Test on cellular separately from home Wi-Fi. Tailscale stays enabled afterward. This only queues the link; it does not wait for audio conversion or phone sync.")
    action("detect.link", UUID=ids["urls"], WFInput=text_token({"Type": "ExtensionInput"}))
    action("getitemfromlist", UUID=ids["first"], WFInput=output("urls", "URLs"), WFItemSpecifier="First Item")
    action("base64encode", UUID=ids["encoded"], WFInput=output("first", "Item from List"),
           WFEncodeMode="Encode", WFBase64LineBreakMode="None")
    prefix = '"$HOME/.local/bin/share-to-music" enqueue --base64 '
    script = {"Value": {"string": prefix + "'\ufffc'", "attachmentsByRange": {
        "{%d, 1}" % (len(prefix) + 1): {"Type": "ActionOutput", "OutputUUID": ids["encoded"], "OutputName": "Base64 Encoded"}
    }}, "WFSerializationType": "WFTextTokenString"}
    action("runsshscript", UUID=ids["ssh"], WFSSHHost="your-mac.your-tailnet.ts.net", WFSSHPort="22",
           WFSSHUser="your-mac-username", WFSSHAuthenticationType="SSH Key", WFSSHScript=script)
    action("showresult", Text=text_token(output("ssh", "Shell Script Result")["Value"]))
    return {
        "WFWorkflowName": "Share to Music", "WFWorkflowClientVersion": "3030.0.4.2",
        "WFWorkflowMinimumClientVersion": 900, "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowIcon": {"WFWorkflowIconStartColor": 4282601983, "WFWorkflowIconGlyphNumber": 59511},
        "WFWorkflowTypes": ["ActionExtension"],
        "WFWorkflowNoInputBehavior": {"Name": "WFWorkflowNoInputBehaviorAskForInput",
                                      "Parameters": {"ItemClass": "WFStringContentItem"}},
        "WFWorkflowHasShortcutInputVariables": True,
        "WFWorkflowInputContentItemClasses": ["WFURLContentItem", "WFStringContentItem", "WFSafariWebPageContentItem"],
        "WFWorkflowActions": actions, "WFWorkflowImportQuestions": [],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sign", action="store_true")
    args = parser.parse_args()
    shortcut = build()
    directory = ROOT / "shortcuts"
    directory.mkdir(exist_ok=True)
    (directory / "Share to Music.json").write_text(json.dumps(shortcut, indent=2) + "\n")
    source = directory / "Share to Music.unsigned.shortcut"
    source.write_bytes(plistlib.dumps(shortcut, fmt=plistlib.FMT_XML, sort_keys=False))
    if args.sign:
        subprocess.run(["/usr/bin/shortcuts", "sign", "--mode", "anyone", "--input", str(source),
                        "--output", str(directory / "Share to Music.shortcut")], check=True)
    print("Shortcut source generated" + (" and signed for sharing." if args.sign else ". Use --sign on a Mac to produce the downloadable file."))


if __name__ == "__main__":
    main()
