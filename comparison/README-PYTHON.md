# vCenter ↔ NetBox ESXi Host Comparator (HTML Report)

This tool compares **ESXi hosts** between **vCenter** and **NetBox** and produces a clean **HTML report** (and optional JSON) showing mismatches (CPU cores, RAM, datastores, pNIC names, VMkernel presence & VLANs). It **does not** modify either system.

---

## Requirements

- Python **3.9+**
- Packages (install on the machine that will run the script):
  ```bash
  pip install pyvmomi pynetbox
  ```

## Access you’ll need

- **vCenter** account with at least **Read-Only** to Datacenter/Cluster (needs to read host summary, network and datastore info).
- **NetBox** API token with permission to read DCIM + IPAM.
- If using self-signed certs, you can disable SSL verification via config/env (see below).

## NetBox data model prerequisites

Create (or verify) the following **custom fields** on **Devices** (Admin → Customization → Custom Fields):

| Field (name) | Type            | Example value               |
|--------------|-----------------|-----------------------------|
| `cpu_cores`  | Integer         | `40`                        |
| `ram_gb`     | Integer         | `512`                       |
| `datastores` | Text (JSON/CSV) | `["DS1","DS2"]` or `DS1,DS2`|

Also make sure your ESXi hosts in NetBox have a **Device Role** (e.g., `esxi-host`) and (optionally) a **Primary IP** (used as Mgmt IP in comparisons).

> pNICs & VMkernels: model interface names in NetBox (e.g., `vmnic0`, `vmnic1`, `vmk0`, `vmk1`). For VMkernel VLAN checks, set the **untagged VLAN** on the `vmk*` interface (this script compares that to the Standard vSwitch Portgroup VLAN on vCenter).

---

## Configure

You can edit the **CONFIG — EDIT THESE** block at the top of the script or override via **environment variables** / **CLI flags**.

### Key settings (all have inline `# TODO` comments in the script)
- `VCENTER_HOST`, `VCENTER_USER`, `VCENTER_PASS`, `VCENTER_VERIFY_SSL`
- `NETBOX_URL`, `NETBOX_TOKEN`, `NETBOX_VERIFY_SSL`
- Filters: `NB_DEVICE_ROLE_SLUG` (e.g., `esxi-host`) and optional `NB_SITE_SLUG`
- **Name matching**: `NAME_MATCH_MODE` = `short` (default), `fqdn`, or `lowercase`
  - Default `short` makes `esx01.domain.tld` ↔ `esx01` match.
- **Aliases** (optional): `NB_NAME_ALIASES` — JSON dict for hard mappings when names differ:
  ```bash
  export NB_NAME_ALIASES='{"esx01.corp.tld":"esx01-prod"}'
  ```
- Custom field names: `CF_CPU_CORES`, `CF_RAM_GB`, `CF_DATASTORES`
- Output HTML path: `OUTPUT_HTML`

---

## Run

### Option A — edit in-file config
```bash
python vcenter_netbox_host_compare.py
```

### Option B — environment variables
```bash
export VCENTER_HOST="vcenter.corp.tld"
export VCENTER_USER="administrator@vsphere.local"
export VCENTER_PASS="********"
export NETBOX_URL="https://netbox.corp.tld"
export NETBOX_TOKEN="xxxxxxxxxxxxxxxxxxxx"
export NB_DEVICE_ROLE_SLUG="esxi-host"
export NAME_MATCH_MODE="short"         # or fqdn / lowercase
# If using self-signed certs:
export VCENTER_VERIFY_SSL=false
export NETBOX_VERIFY_SSL=false

python vcenter_netbox_host_compare.py
```

### Option C — CLI flags
```bash
python vcenter_netbox_host_compare.py   --vcenter-host vcenter.corp.tld   --vcenter-user administrator@vsphere.local   --vcenter-pass '********'   --netbox-url https://netbox.corp.tld   --netbox-token xxxxxxxxxxxxxxxxxxxx   --nb-role esxi-host   --name-match-mode short   --output-html drift.html   --output-json drift.json   --vcenter-verify-ssl   --netbox-verify-ssl
```

> Exit codes: **0** (no mismatches), **2** (mismatches or missing hosts), **1** (error).

---

## What’s compared

- **Mgmt IP** (vCenter vmk0 IP ↔ NetBox primary IP)
- **CPU cores** (vCenter) ↔ `cpu_cores` (NetBox CF)
- **RAM (GB)** (vCenter) ↔ `ram_gb` (NetBox CF)
- **Datastores** (names; set list/CSV in NetBox `datastores` CF)
- **Physical NICs** (names like `vmnic0`… from vCenter ↔ NetBox interfaces named `vmnic*`)
- **VMkernel presence** (names like `vmk0`, `vmk1`)
- **VMkernel VLAN** (best-effort): compares Standard vSwitch Portgroup VLAN (vCenter) to **untagged VLAN** on the `vmk*` NetBox interface. (DVSwitch/trunks appear as unknown VLAN = not compared).

---

## Known limitations

- DVSwitch portgroup VLANs behind trunks may not yield a single VLAN ID; we compare only Standard vSwitch VMkernel VLANs.
- If your NetBox uses different naming (e.g., `esx-01a`) use `NB_NAME_ALIASES` to map to vCenter names.
- The script reads data; it does **not** modify vCenter/NetBox.

---

## Troubleshooting

- **SSL issues** with lab/self-signed certs: set `VCENTER_VERIFY_SSL=false` and/or `NETBOX_VERIFY_SSL=false`.
- **No hosts found**: check `NB_DEVICE_ROLE_SLUG`/`NB_SITE_SLUG` filters and your API token permissions.
- **Empty Mgmt IP** on vCenter: ensure `vmk0` has an IP on each ESXi host.
- **Custom fields missing**: create the CFs in NetBox (names must match `CF_*` settings).

---

## Changelog vs your original snippet

- Fixed the `if __name__ == "__main__":` guard.
- Added **name normalization/aliasing** for robust host matching.
- Added **CLI flags**, optional **JSON output**, and **exit codes**.
- Hardened vCenter/NetBox collection with better error handling.
- Improved parsing of NetBox `datastores` custom field (JSON or CSV).
- Left all **TODO** comments so you can see exactly what to edit.