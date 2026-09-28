# Tailscale and the home exit node

The Shortcut starts with **Connect to your Tailscale network → Use Exit Node**, then sends an SSH command to your Mac. Select your own home-network exit node. The iPhone performs these network actions; a script on the Mac cannot connect the phone's VPN for it.

<img src="images/iphone-tailscale.png" alt="The Tailscale Connect and Use Exit Node actions at the top of the iPhone Shortcut." width="380">

## Choose the right SSH address

**Host is the address of the Mac running Music**, not the address of the exit node (unless they are the same device). Use an address your phone can actually reach. Selecting an exit node does not require that Host be a Tailscale address, nor does it forbid one.

| Your connection | SSH Host | Tailscale needed on Mac? |
| --- | --- | --- |
| Phone and Mac on home Wi-Fi | Mac's LAN IP, such as `192.168.1.50`, or its working local name, such as `My-Mac.local` | No |
| Phone away from home, routed to the home LAN | Mac's LAN IP; use a hostname only if remote name resolution is configured | No |
| Phone connects directly to the Mac as a Tailscale device | Mac's `100.x.x.x` address or full MagicDNS name | Yes |

All example addresses are placeholders. For a LAN IP, open **System Settings → Network → active Wi-Fi/Ethernet connection → Details → TCP/IP**. The `.local` name is shown under **General → Sharing**. Reserving the Mac's LAN address in your router's DHCP settings prevents it changing later.

**A successful home-Wi-Fi test does not establish cellular reachability.** `.local` names normally use local-network discovery. Test again with Wi-Fi disabled on the phone before relying on the Shortcut away from home. A working local name can be kept for home use; use a routable IP or properly configured DNS for remote use.

## Reach the Mac through the home network

This option lets the Mac use its built-in **Remote Login** service without running Tailscale itself.

1. Install/sign into Tailscale on the iPhone and your always-on home gateway, such as a Raspberry Pi.
2. Configure the gateway as an exit node, approve it, and select it in the Shortcut. [Exit-node setup](https://tailscale.com/docs/features/exit-nodes/how-to/setup)
3. For predictable remote access to private LAN addresses, also configure and approve a **subnet route** for your home network on that gateway. Permit your phone to reach the Mac on TCP port 22. The gateway can serve both roles; check existing routes before changing its configuration. [Subnet-router setup](https://tailscale.com/docs/features/subnet-routers)
4. Set Host to the Mac's reachable LAN address, User to its short login name, and enable [Remote Login and SSH key authentication](ssh.md).
5. Test on home Wi-Fi, then repeat on cellular.

Tailscale documents exit nodes for internet routing and subnet routers for private-network access. Existing home routing may already make a LAN address reachable; verify your actual path instead of assuming that selecting any exit node supplies LAN access or `.local` discovery. **Allow Local Network Access** refers to the phone's current physical network, not automatic discovery of a remote home LAN. [Exit-node routing and local access](https://tailscale.com/docs/features/exit-nodes)

## Connect directly to Tailscale on the Mac

Alternatively, install Tailscale on both phone and Mac, sign into the same tailnet, and use the Mac's Tailscale IP or full MagicDNS name. Permit TCP 22 and enable macOS Remote Login. This peer connection remains a valid option while the phone uses an exit node; reaching the Mac itself does not require an exit node. [Connecting to Tailscale devices](https://tailscale.com/docs/how-to/connect-to-devices)

The downloadable template's `your-mac.your-tailnet.ts.net` is an example for this option. Replace it with your chosen LAN or Tailscale address. The separate **Tailscale SSH** server feature is not required: this project uses macOS's standard SSH server.

## What happens each time

Keep the phone unlocked for the exit-node action. After network setup, SSH should return a queue confirmation promptly. The Mac then downloads and imports in the background; the phone is not waiting for conversion or Apple syncing. [Tailscale's Shortcuts actions](https://tailscale.com/docs/features/mac-ios-shortcuts)

The Shortcut leaves Tailscale and the selected exit node enabled, even if a later SSH step fails. Choose **None** in Tailscale's exit-node selector when finished. The Mac downloads the media using its own network connection; selecting an exit node on the phone does not change the Mac's routing.

## Connection problems

- **Missing actions:** install/open Tailscale on the phone, sign in, then reopen Shortcuts.
- **No exit node listed:** verify the home node is online, approved, and allowed by your tailnet policy.
- **Works on Wi-Fi, fails on cellular:** check the home subnet route and Host address/name resolution, or use direct Tailscale addressing.
- **Timeout:** check the selected route, Mac power/sleep state, Remote Login, and TCP 22 access policy.
- **Host fingerprint prompt:** the phone reached an SSH server; compare the fingerprint. This does not yet confirm successful login. See [SSH setup](ssh.md#4-understand-the-first-connection-fingerprint-prompt).

No router port forwarding is needed. The public template includes no real node, hostname, account, or credential.
