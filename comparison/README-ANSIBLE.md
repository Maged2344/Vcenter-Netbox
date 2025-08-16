# vCenter ↔ NetBox Host Comparison with Ansible

This project provides an **Ansible role and playbook** to automatically compare host data between **vCenter** and **NetBox**, then generate an **HTML report** summarizing differences.

---

## 📂 Project Structure
```
comparison/
├── playbook.yml
├── roles/
│   └── vcenter_netbox_compare/
│       ├── tasks/
│       │   └── main.yml
│       ├── templates/
│       │   └── report.html.j2
│       ├── defaults/
│       │   └── main.yml
│       └── README.md
```

---

## 🔹 Requirements

### Control Machine
You need:
- **Python 3.8+**
- **Ansible 2.15+**
- Python packages:
  ```bash
  pip install pyvmomi pynetbox jmespath
  ```

### Ansible Collections
Install required collections:
```bash
ansible-galaxy collection install community.vmware
ansible-galaxy collection install community.general
```

---

## 🔹 Configuration

### 1. Inventory
Create an inventory file (`inventory.ini`) based on the example:
```ini
[local]
localhost ansible_connection=local
```

### 2. Variables
Edit `roles/vcenter_netbox_compare/defaults/main.yml`:
```yaml
# vCenter credentials
vcenter_hostname: "your-vcenter.example.com"
vcenter_username: "administrator@vsphere.local"
vcenter_password: "your-password"

# NetBox API
netbox_url: "https://netbox.example.com"
netbox_token: "your-netbox-api-token"

# Report output
report_output: "/tmp/vcenter_netbox_report.html"
```

---

## 🔹 Usage

Run the playbook:
```bash
ansible-playbook -i inventory.ini playbook.yml
```

When it completes, check the HTML report at:
```
/tmp/vcenter_netbox_report.html
```

---

## 🔹 Example Report

The report shows:
- ✅ Hosts present in both systems with matching attributes
- ⚠️ Hosts with mismatched CPU, RAM, or NICs
- ❌ Hosts missing in one of the systems

---

## 🔹 Notes
- The role currently compares:
  - Hostname
  - CPU count
  - Memory (GB)
  - NIC list (names)
  - NETWORK
- You can expand fields inside `tasks/main.yml`.

---

## 🔹 Next Steps
- Integrate into CI/CD: run nightly to detect drifts
- Send HTML via email with `ansible.builtin.mail` if needed
- Add disk/storage checks if required

---

## ✅ Summary
This playbook automates vCenter ↔ NetBox **host consistency checks** and produces an HTML report you can use for drift detection.