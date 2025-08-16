# 🔍 vCenter ↔ NetBox ESXi Host Comparator

Compare your **ESXi host inventory** between **vCenter** and **NetBox**, detect configuration **drift**, and generate clean, actionable **HTML reports** (and optional JSON).

This repo provides **two options**:

1. 🐍 A powerful **Python script** for manual or automated CLI usage  
2. 🛠️ An **Ansible role & playbook** for automation, CI/CD, or scheduled drift detection

---

## ✨ Features

- ✅ Compares ESXi hosts across vCenter and NetBox
- 🧠 Name aliasing & normalization (\`esx01.domain.tld\` ↔ \`esx01\`)
- 🧾 Output clean **HTML** and optional **JSON**
- 🛑 No modifications made to vCenter or NetBox — **read-only**
- 💡 Detect mismatches in:
  - CPU cores
  - RAM (GB)
  - Datastores
  - Physical NICs (\`vmnic*\`)
  - VMkernel interfaces (\`vmk*\`)
  - VMkernel VLANs (standard vSwitch only)
  - Mgmt IP address

---

## 📁 Repo Structure

\`\`\`
comparison/
├── vcenter_netbox_host_compare.py        # ← Python script
├── playbook.yml                          # ← Ansible playbook
├── roles/
│   └── vcenter_netbox_compare/
│       ├── tasks/main.yml
│       ├── templates/report.html.j2
│       ├── defaults/main.yml
│       └── README.md
\`\`\`

---

## 🔧 Option 1: Python Script (\`vcenter_netbox_host_compare.py\`)

### 🛠️ Requirements

- Python **3.9+**
- Install dependencies:
  \`\`\`bash
  pip install pyvmomi pynetbox
  \`\`\`

---

### 🔐 Access You’ll Need

- **vCenter**: Read-Only account (hosts, networks, datastores)
- **NetBox**: API Token with read access to DCIM & IPAM
- Disable SSL verification (if using self-signed certs):
  \`\`\`bash
  export VCENTER_VERIFY_SSL=false
  export NETBOX_VERIFY_SSL=false
  \`\`\`

---

### 🧱 NetBox Custom Fields

Create the following **custom fields** on your ESXi hosts in NetBox:

| Field (name) | Type    | Example             |
|--------------|---------|---------------------|
| \`cpu_cores\`  | Integer | \`40\`                |
| \`ram_gb\`     | Integer | \`512\`               |
| \`datastores\` | Text    | \`["DS1","DS2"]\` or \`DS1,DS2\` |

> ✅ Also model \`vmnic*\` and \`vmk*\` as interfaces; set VLANs on \`vmk*\` as **untagged** for comparison.

---

### ⚙️ Configuration

Edit config in one of 3 ways:

#### ➤ A. In-file (\`CONFIG — EDIT THESE\`)
\`\`\`bash
python vcenter_netbox_host_compare.py
\`\`\`

#### ➤ B. Environment Variables
\`\`\`bash
export VCENTER_HOST="vcenter.corp.tld"
export VCENTER_USER="administrator@vsphere.local"
export VCENTER_PASS="********"
export NETBOX_URL="https://netbox.corp.tld"
export NETBOX_TOKEN="xxxxxxxxxxxxxxx"
export NB_DEVICE_ROLE_SLUG="esxi-host"
export NAME_MATCH_MODE="short"  # or fqdn / lowercase

python vcenter_netbox_host_compare.py
\`\`\`

#### ➤ C. CLI Flags
\`\`\`bash
python vcenter_netbox_host_compare.py \
  --vcenter-host vcenter.corp.tld \
  --vcenter-user administrator@vsphere.local \
  --vcenter-pass '********' \
  --netbox-url https://netbox.corp.tld \
  --netbox-token xxxxxxxxxxxxxxxx \
  --nb-role esxi-host \
  --name-match-mode short \
  --output-html report.html \
  --output-json report.json
\`\`\`

---

### ✅ What’s Compared?

| Attribute       | Description |
|-----------------|-------------|
| Hostname        | Name matching via short/FQDN/alias |
| Mgmt IP         | \`vmk0\` IP in vCenter vs NetBox Primary IP |
| CPU Cores       | \`cpu_cores\` custom field |
| RAM (GB)        | \`ram_gb\` custom field |
| Datastores      | NetBox \`datastores\` CF (JSON or CSV) |
| Physical NICs   | \`vmnic*\` interfaces |
| VMkernel NICs   | \`vmk*\` interfaces |
| VMK VLANs       | Compares vSwitch VLAN vs NetBox untagged VLAN |

---

### 🛠 Exit Codes

| Code | Meaning              |
|------|-----------------------|
| \`0\`  | No mismatches         |
| \`1\`  | Error occurred        |
| \`2\`  | Hosts mismatch/missing |

---

## 🚀 Option 2: Ansible Role & Playbook

Automate host comparison using Ansible.

### 🔧 Requirements

- Python **3.8+**
- Ansible **2.15+**
- Python packages:
  \`\`\`bash
  pip install pyvmomi pynetbox jmespath
  \`\`\`
- Required collections:
  \`\`\`bash
  ansible-galaxy collection install community.vmware community.general
  \`\`\`

---

### 📁 Inventory Example (\`inventory.ini\`)
\`\`\`ini
[local]
localhost ansible_connection=local
\`\`\`

---

### 📝 Configuration (\`defaults/main.yml\`)
\`\`\`yaml
# vCenter credentials
vcenter_hostname: "vcenter.example.com"
vcenter_username: "administrator@vsphere.local"
vcenter_password: "your-password"

# NetBox API
netbox_url: "https://netbox.example.com"
netbox_token: "your-api-token"

# Output
report_output: "/tmp/vcenter_netbox_report.html"
\`\`\`

---

### ▶️ Run the Playbook

\`\`\`bash
ansible-playbook -i inventory.ini playbook.yml
\`\`\`

🧾 Result:
\`\`\`
/tmp/vcenter_netbox_report.html
\`\`\`

---

## 🧪 Example Report Output

- ✅ Green: Matched attributes  
- ⚠️ Yellow: Mismatched values (CPU, RAM, NICs, VLANs)  
- ❌ Red: Host missing in one system  

---

## 💡 Tips & Notes

- Use \`NB_NAME_ALIASES\` for custom name mapping:
  \`\`\`bash
  export NB_NAME_ALIASES='{"esx01.corp.tld":"esx01-prod"}'
  \`\`\`
- Set \`NB_SITE_SLUG\` to limit scope by site
- Standard vSwitch only for VLAN check (no DVSwitch trunk detection)
- Set untagged VLAN on NetBox \`vmk*\` interfaces to enable comparison

---

## 📬 Next Steps

- 🕒 Schedule in CI/CD (e.g., GitHub Actions or Jenkins)
- 📧 Email HTML reports using \`ansible.builtin.mail\`
- 💽 Extend comparisons (e.g., disks, cluster, tags)

---

## 🤝 Contributing

PRs welcome! Suggestions, improvements, or fixes — feel free to fork and contribute.

---

## 🧾 License

MIT — feel free to use, modify, and share.

---

## 🙌 Acknowledgements

- Powered by [pyvmomi](https://github.com/vmware/pyvmomi) & [pynetbox](https://github.com/digitalocean/pynetbox)  
- Built with ❤️ for VMware + NetBox users

---

**Start comparing today and catch those config drifts early!** 🚀
