# IPA Client → IPA Server Firewall Connectivity Verification

This repo provides **two ways** to automatically verify that **IPA clients** can reach **IPA servers** on all **required FreeIPA ports** (HTTP, LDAP/LDAPS, Kerberos, DNS, NTP) *from within each Availability Zone (AZ)*.

- **Method A — Python**: `ipa_fw_connectivity_check.py` SSHes into each client and tests connectivity to all IPA servers, then writes an **HTML** + **JSON** report.
- **Method B — Ansible**: `ansible/ipa_fw_check.yml` runs the same checks from each client and builds a consolidated **HTML** report.

> ✅ Both methods test **from the client hosts** (not from your laptop), which is what you need to validate firewall rules inside the AZ.

---

## Required Ports (from Red Hat IdM)
- HTTP/HTTPS: `80/tcp`, `443/tcp`
- LDAP/LDAPS: `389/tcp`, `636/tcp`
- Kerberos: `88/tcp` + `88/udp`, `464/tcp` + `464/udp` (kpasswd)
- DNS: `53/tcp` + `53/udp`
- NTP (optional): `123/udp`

UDP checks are best-effort: success means the datagram was sent without a local error, but no response is required by UDP.

---

## Method A — Python

### 1) Install dependency
```bash
pip install paramiko
```

### 2) Configure
Open `connectivity_check.py` and edit the **CONFIG — EDIT THESE** section:

- `CLIENTS`: IPA client hosts with SSH user, key, and (optional) `bastion`.
- `IPA_SERVERS`: map each environment/AZ to its IPA servers.
- `REQUIRED_PORTS`: leave as-is unless you need to add/remove services.
- `TCP_TIMEOUT`, `UDP_TIMEOUT`: tweak timeouts if links are slow.
- `OUTPUT_JSON`, `OUTPUT_HTML`: paths for artifacts.

> The script uses **Bash `/dev/tcp` and `/dev/udp`** on the clients. That keeps targets clean without extra packages.

### 3) Run
```bash
python connectivity_check.py
```

### 4) Results
- JSON: `ipa_fw_results.json`
- HTML: `ipa_fw_report.html` (open in a browser)

---

## Method B — Ansible

### 1) Install Ansible
```bash
pip install ansible
# or on macOS
brew install ansible
```

### 2) Inventory
Create an inventory with your IPA clients (example file: `ansible/inventory.ini.example`). If you need a jump host, add:
```
ansible_ssh_common_args='-o ProxyJump=bastion.mycorp.local'
```

### 3) Variables
Edit `ansible/group_vars/all.yml`:
- `ipa_servers`: your environments/AZs → IPA servers list (e.g. `VE_AZ1`, `APP_PROD_DE_AZ2`, etc.).
- `required_ports`: list of dicts with `service`, `port`, `proto`.
- `tcp_timeout`, `udp_timeout`: timeouts in seconds.

### 4) Run
```bash
cd ansible
ansible-playbook -i inventory.ini ipa_fw_check.yml
```

### 5) Results
- Per-host JSON files in `./artifacts/`
- Consolidated HTML: `./artifacts/ipa_fw_report.html`

Open the HTML report in a browser.

---

## Tips

- **SSH access**: Make sure your laptop (control node) can SSH to IPA clients. Use VPN and/or a **bastion**.
- **Validation depth**: These checks verify port reachability. For end-to-end protocol tests:
  - Kerberos: run `kinit` or `kvno` against the realm.
  - DNS: run a `dig` query against the IPA DNS server.
  - NTP: run `chronyc sourcestats` or `ntpdate -q`.

---

## Bonus: vCenter ↔ NetBox Script Note

You pasted a `vCenter ↔ NetBox ESXi Host Comparator` earlier. Quick fix: the last line should be
```python
if __name__ == "__main__":
    main()
```
(not `_name_`/`_main_`). Everything else looked good for a first pass.