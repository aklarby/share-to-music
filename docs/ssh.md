# Enable SSH and require a public key

**Remote Login is macOS's SSH server.** It lets the iPhone run the queue command as your Mac user. Tailscale provides a network path; it does not turn Remote Login on or authorize an SSH key.

Do this setup while sitting at your Mac. Keep a local Terminal window open while changing authentication settings so you can undo a mistake without needing SSH.

## 1. Turn on Remote Login

1. Open **System Settings → General → Sharing**.
2. Find **Remote Login** under Advanced and turn it on. Approve the administrator prompt if shown.
3. Click the **ⓘ** beside Remote Login. Under **Allow access for**, choose **Only these users** and add your own Mac account. Use the account that installed Share to Music and owns your Music library.
4. Leave **Allow full disk access for remote users** off for this setup; the helper uses its own Application Support directory. Music automation has a separate permission.

You do not need Screen Sharing, Remote Management, or Remote Application Scripting for this project. Those switches serve other purposes. Do not forward port 22 on your internet router. [Apple's Remote Login instructions](https://support.apple.com/guide/mac-help/mchlp1066/mac)

Remote Login accepts connections at the Mac's reachable addresses. Use the [network guide](tailscale.md#choose-the-right-ssh-address) to choose a home-LAN address or a direct Tailscale address.

## 2. Find the login name

Open **Terminal** on the Mac, paste this, and press Return:

```sh
whoami
```

Put the result in the Shortcut's **User** field. This is the short account name (for example, `alex`), not the computer's name, Apple Account email, or full display name. Set **Port** to `22`.

## 3. Authorize the iPhone's public key

A key pair has two parts: the iPhone keeps the private key, and the Mac stores the public key in a list of allowed keys. Never paste a private key into a chat or public repository.

1. On the **iPhone that will run the Shortcut**, open **Share to Music → Run Script Over SSH**.
2. Choose **SSH Key** under Authentication. Tap the key details, then **Copy Public Key**. Generate a key only if none exists; generating another one changes what the Mac must authorize.
3. Transfer that public-key text to your Mac. It is normally one line beginning with `ssh-ed25519`, followed by a long string and an optional comment. Do not assume a key copied from Mac Shortcuts matches the key used by the phone.
4. In Mac Terminal, run:

   ```sh
   mkdir -p "$HOME/.ssh"
   chmod 700 "$HOME/.ssh"
   touch "$HOME/.ssh/authorized_keys"
   chmod 600 "$HOME/.ssh/authorized_keys"
   nano "$HOME/.ssh/authorized_keys"
   ```

5. Go to a new line at the end and paste the complete public key. Keep each key on one line and preserve existing keys. Press **Control-O**, then **Return** to save; press **Control-X** to exit.

To list fingerprints of the keys authorized on the Mac:

```sh
ssh-keygen -lf "$HOME/.ssh/authorized_keys"
```

Compare the **SHA256** value with the one in the iPhone's key details. Comments such as “Shortcuts on iPhone” are labels, not proof that the key matches.

## 4. Understand the first-connection fingerprint prompt

The phone may ask whether you trust the **Mac's host key**. That identifies the server you reached. It is different from the **iPhone's public key**, which proves that the phone is allowed to log in.

On the Mac, show its host-key fingerprints with:

```sh
for key in /etc/ssh/ssh_host_*_key.pub; do
  ssh-keygen -lf "$key"
done
```

Compare the matching key type/fingerprint before accepting the phone's prompt. Reaching this prompt confirms SSH connectivity; it does **not** prove the phone authenticated or submitted a job.

Test a share and confirm a job ID before disabling other login methods. A “Permission denied (publickey)” error means the server was reached but did not accept an offered key; check the phone's fingerprint, username, authorized key, and file permissions.

## 5. Disable password login and require a public key

Selecting **SSH Key** in the Shortcut only changes that client. To refuse password logins from every SSH client, configure the **Mac's SSH server** too.

The following settings affect all SSH users on this Mac. Confirm every account that still needs SSH has a working key first. They do not change your normal Mac login password. If your Mac is managed by an organization or already has custom SSH rules, consult its administrator instead of replacing those rules.

1. Keep your local Terminal window open. Inspect the existing configuration:

   ```sh
   cat /etc/ssh/sshd_config
   ls /etc/ssh/sshd_config.d
   ```

   Current macOS normally includes `/etc/ssh/sshd_config.d/*` near the top. If that Include line is absent, stop: the drop-in below would not be loaded. If the proposed filename already exists, back it up outside that directory and review it before editing. Do not overwrite someone else's configuration.

2. Create this dedicated configuration file:

   ```sh
   sudo nano /etc/ssh/sshd_config.d/000-share-to-music-key-only.conf
   ```

   `sudo` asks for your Mac administrator password. Terminal deliberately shows no characters while you type it. Paste:

   ```text
   PubkeyAuthentication yes
   AuthenticationMethods publickey
   PasswordAuthentication no
   KbdInteractiveAuthentication no
   PermitRootLogin no
   ```

   Save with **Control-O**, **Return**, then **Control-X**. These settings enable keys, require them, disable both password and keyboard-interactive login paths, and block direct root login. [OpenSSH configuration reference](https://man.openbsd.org/sshd_config)

3. Validate before disconnecting:

   ```sh
   sudo /usr/sbin/sshd -t
   sudo /usr/sbin/sshd -T -C "user=$(whoami),host=localhost,addr=127.0.0.1" |
     grep -E '^(pubkeyauthentication|authenticationmethods|passwordauthentication|kbdinteractiveauthentication|permitrootlogin) '
   ```

   The first command should print nothing and exit successfully. The second should show `pubkeyauthentication yes`, `authenticationmethods publickey`, and `no` for the other three settings. Configuration order and existing `Match` rules can affect the result; if it differs, fix the conflict before relying on key-only login. For source-address-specific `Match` rules, also check with the phone's actual source address instead of `127.0.0.1`.

4. Start a **new** connection from the iPhone and confirm a share reaches the queue. Existing connections do not prove new settings work. macOS normally starts SSH sessions on demand, so a new connection reads the configuration; a reboot is unnecessary.

5. Optionally test that a password-only attempt is rejected. From Terminal, using the same Host and User as the Shortcut, replace both uppercase placeholders:

   ```sh
   ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password,keyboard-interactive USER@HOST
   ```

   After host-key verification, this should fail without requesting the account password. If it offers a password, the server still allows a non-key method.

**Recovery:** if you created this new drop-in and it causes trouble, use the Mac's local Terminal to remove just that file, then validate again:

```sh
sudo rm /etc/ssh/sshd_config.d/000-share-to-music-key-only.conf
sudo /usr/sbin/sshd -t
```

If you edited a file that already existed, restore your backup instead. This reverts only this guide's server configuration; it preserves `authorized_keys`. Other existing SSH policies still apply. Keep Remote Login restricted to your intended users throughout.

## Screen off, locked, asleep, or logged out?

| Mac state | What to expect |
| --- | --- |
| Screen off or locked, desktop user still logged in | The worker can run; you do not need Terminal open |
| Asleep | Processing pauses; wake-up depends on hardware/network settings and must be tested |
| Logged out | SSH may accept a queue command, but this per-user desktop worker cannot import until that user logs in |
| Shut down | No SSH or processing until the Mac starts |

Remote Login enables SSH; it does not keep the machine powered on or create a Music desktop session. **Wake for network access** is a separate setting: on a desktop, look in **System Settings → Energy**; on a laptop, **Battery → Options**. A VPN connection alone does not prove wake-up will work. Initially test with the Mac awake, then test your intended sleep/wake setup. [Apple's wake-for-network-access guide](https://support.apple.com/guide/mac-help/share-your-mac-resources-when-its-in-sleep-mh27905/mac)
