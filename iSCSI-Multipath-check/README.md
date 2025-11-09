# vCenter iSCSI Datastore Path & User Checker

A Python script to check the health of iSCSI datastore paths on ESXi hosts and verify that required users exist in vCenter. Includes a **test mode** to run without a real vCenter connection for testing and demo purposes.

---

## Features

- ✅ Check that each ESXi host has the expected number of active iSCSI paths per datastore.  
- ✅ Verify that required users exist in vCenter.  
- ⚠ Test mode with fake hosts and users for local testing without vCenter.  
- ✅ Clear summary output using symbols:
  - ✅ Fully OK  
  - ⚠ Partially OK  
  - ✗ Failed / Missing  

---

## Requirements

- Python 3.8+  
- [`pyvmomi`](https://pypi.org/project/pyvmomi/) Python library  
- Access to vCenter (for real checks)

Install dependencies with:

```bash
pip install pyvmomi
```

## Configuration
# Edit the configuration section at the top of the script:

```python
VCENTER_HOST = "your-vcenter.domain.com"
VCENTER_USER = "administrator@vsphere.local"
EXPECTED_PATH_COUNT = 2
USERS_TO_CHECK = [
    "auto.aap.vcenter",
    "auto.cloudify.vcenter",
    "auto.iceflow"
]
```
## run the script

```
python3 iscsi-check.py
```