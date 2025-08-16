# vcenter_netbox_compare Role

This Ansible role compares **hosts in vCenter** with **devices in NetBox** and generates an **HTML report**.

## Variables

Define in `defaults/main.yml` or override in playbook:

```yaml
vcenter_hostname: "your-vcenter.example.com"
vcenter_username: "administrator@vsphere.local"
vcenter_password: "yourpassword"

netbox_url: "https://netbox.example.com"
netbox_token: "NETBOX_API_TOKEN"

compare_output_file: "/tmp/vcenter_netbox_report.html"
