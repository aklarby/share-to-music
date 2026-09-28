# Tailscale and the home exit node

The downloadable Shortcut starts with **Connect to your Tailscale network**, then **Use Exit Node**. These run on the iPhone before SSH. A script on the Mac cannot establish the iPhone's VPN connection, so this belongs in the Shortcut.

<img src="images/iphone-tailscale.png" alt="The Tailscale Connect and Use Exit Node actions at the top of the iPhone Shortcut." width="380">

## One-time setup

1. Install a current [Tailscale client](https://tailscale.com/download) on the iPhone and Mac, sign into the same tailnet, and complete the device's VPN permission/login setup.
2. On a device on the Mac's home network, enable **Run as exit node**. This can be the Mac itself or an always-on device at home. Have your tailnet administrator approve that exit node in the admin console. [Tailscale's exit-node setup](https://tailscale.com/docs/features/exit-nodes/how-to/setup)
3. Open the Shortcut and select that device in **Use Exit Node → Exit Node**. The template intentionally contains no real node or account selection. Select your home node explicitly; do not leave this field unconfigured.
4. Set the SSH **Host** to the Mac's Tailscale IP or full MagicDNS name. Set **User** to the Mac login that installed the helper. Enable macOS Remote Login for that user.
5. If your tailnet uses a custom access policy, it must allow both the phone's connection to the Mac on TCP 22 and use of the exit node. Exit-node permission and permission to reach the Mac are distinct. [Tailscale's exit-node access rules](https://tailscale.com/docs/features/exit-nodes)

The Shortcut uses ordinary macOS SSH over the Tailscale network. Enabling the separate “Tailscale SSH” server feature is not required.

## What happens each time

The iPhone connects to Tailscale, activates the selected exit node, and then runs the SSH command. Native action errors stop the Shortcut before queueing. Keep the iPhone unlocked when invoking the exit-node action. The native Tailscale actions require Tailscale to be installed; current app versions are recommended. [Tailscale's Shortcuts reference](https://tailscale.com/docs/features/mac-ios-shortcuts)

The helper sends a queue confirmation once SSH succeeds. The Shortcut leaves Tailscale connected and the exit node enabled, including when a later SSH step fails. It does not attempt to guess or restore your previous network settings. Choose **None** in Tailscale's exit-node selector when you want to stop using it.

## Choose the right SSH address

Use the Mac's Tailscale address to make it reachable from home Wi-Fi, other Wi-Fi, or cellular. Tailscale assigns stable peer addresses and provides MagicDNS names. [Connecting to Tailscale devices](https://tailscale.com/docs/how-to/connect-to-devices)

An exit node routes the phone's public internet traffic. It is not needed for direct access to another tailnet peer, but this workflow selects the home exit node as part of its network setup. It does not provide `.local`/Bonjour discovery of the remote LAN. “Allow Local Network Access” concerns the phone's current local network; it is not a switch for discovering the Mac's home LAN. [Exit-node routing and local access](https://tailscale.com/docs/features/exit-nodes)

If the Mac cannot run Tailscale and you want to target its home-LAN IP, configure an approved subnet route for that LAN and verify SSH reachability separately. An exit node alone is not the documented substitute for a subnet router. The default guide assumes Tailscale runs directly on the Mac. [Subnet routers](https://tailscale.com/docs/features/subnet-routers)

The media download originates on the **Mac**. Selecting an exit node on the iPhone does not change the Mac's own internet routing.

## If the network actions fail

- **Unknown/unavailable action:** install or update Tailscale on the iPhone, open it once, sign in, and re-open Shortcuts. If necessary, replace the two network actions from the Tailscale action library in the same order.
- **No exit node to select:** check that the home device advertises exit-node capability, that it is approved and online, and that your tailnet allows you to use it.
- **SSH times out after connecting:** verify the Mac's Tailscale address, its online status, Remote Login, and access policy. Re-run after the connection settles; the Mac normalizes duplicate queued URLs.
- **Cannot choose an exit node while locked:** unlock the phone and run again.

No tailnet auth keys, node IDs, actual hostnames, credentials, or account details are included in the repository. Setting up the tailnet and approving an exit node are actions for the device owner/administrator.
