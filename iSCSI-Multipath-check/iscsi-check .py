#!/usr/bin/env python3
import logging
import ssl
import atexit
import getpass
from datetime import datetime
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim

logging.basicConfig(level=logging.DEBUG)

"""
vCenter iSCSI Datastore Path & User Checker
-------------------------------------------
✓ Task 1: Verify each iSCSI datastore has required active paths
✓ Task 2: Verify required users exist in vCenter
"""

# ============================================================================
# ✅ CONFIGURATION (EDIT THESE ONLY)
# ============================================================================
VCENTER_HOST = "your-vcenter.domain.com"          # vCenter hostname or IP
VCENTER_USER = "administrator@vsphere.local"     # vCenter login user
EXPECTED_PATH_COUNT = 2                           # Minimum active iSCSI paths required
USERS_TO_CHECK = [                                # List of accounts that must exist
    "auto.aap.vcenter", 
    "auto.cloudify.vcenter",
    "auto.iceflow"
]

# ============================================================================
# ✅ TEST MODE DATA
# ============================================================================
# Used when vCenter connection fails (for local testing)
FAKE_ISCSI_HOSTS = [
    {"host": "esxi-host1", "datastore": "Datastore-A", "active_paths": 1, "total_paths": 2},
    {"host": "esxi-host2", "datastore": "Datastore-B", "active_paths": 2, "total_paths": 2},
    {"host": "esxi-host3", "datastore": "Datastore-C", "active_paths": 0, "total_paths": 2},
]

FAKE_USERS = {
    "auto.aap.vcenter": False,   # False = missing
    "auto.cloudify.vcenter": True,  # True = exists
    "auto.iceflow": False
}

# ============================================================================
# ✅ CONNECT TO VCENTER
# ============================================================================
def connect_to_vcenter(host, user, password):
    """
    Connect to vCenter and return session handle.
    SSL cert verification is disabled to avoid certificate issues.
    Uses a modern SSL context to avoid deprecated warning.
    """
    try:
        context = ssl.create_default_context()  # Modern context instead of deprecated TLSv1_2
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        si = SmartConnect(
            host=host,
            user=user,
            pwd=password,
            sslContext=context
        )
        atexit.register(Disconnect, si)  # Ensure disconnect on exit
        print(f"✓ Connected to vCenter: {host}\n")
        return si

    except Exception as e:
        print(f"✗ Failed to connect to vCenter: {e}")
        return None

# ============================================================================
# ✅ TASK 1: Check iSCSI Datastore Paths
# ============================================================================
def check_iscsi_datastore_paths(si, expected_paths=2):
    """
    For every ESXi host, check multipath state:
    - Count total paths
    - Count active paths
    - Report datastores with less than expected path count
    """
    content = si.RetrieveContent()

    # Get all ESXi hosts
    container = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.HostSystem], True
    )
    hosts = container.view
    container.Destroy()

    print("=" * 80)
    print("ISCSI DATASTORE PATH CHECK")
    print("=" * 80)

    issues = []

    for host in hosts:
        host_name = host.name
        storage_system = host.configManager.storageSystem

        if not storage_system:
            continue

        multipath_info = storage_system.storageDeviceInfo.multipathInfo

        if not multipath_info:
            print(f"✗ No multipath info found for host {host_name}")
            continue

        for lun in multipath_info.lun:
            total_paths = len(lun.path)
            active_paths = sum(1 for p in lun.path if p.state == "active")

            # Try to find datastore name from LUN
            datastore_name = None
            for datastore in host.datastore:
                if lun.lun in str(datastore.info):
                    datastore_name = datastore.name
                    break
            if not datastore_name:
                datastore_name = f"LUN {lun.lun}"

            # Status check
            status = "✅" if active_paths >= expected_paths else ("⚠" if active_paths > 0 else "✗")
            print(f"{status} Host: {host_name}")
            print(f"  Datastore: {datastore_name}")
            print(f"  Active Paths: {active_paths}/{total_paths}\n")

            if active_paths < expected_paths:
                issues.append({
                    "host": host_name,
                    "datastore": datastore_name,
                    "active_paths": active_paths,
                    "total_paths": total_paths
                })

    return issues

# ============================================================================
# ✅ TASK 2: Verify required users exist
# ============================================================================
def check_users_exist(si, users_to_check):
    """
    Search vCenter identity store and verify if configured users exist.
    """
    content = si.RetrieveContent()
    user_directory = content.userDirectory

    print("=" * 80)
    print("USER EXISTENCE CHECK")
    print("=" * 80)

    missing_users = []

    for user in users_to_check:
        try:
            # Split username and domain if present
            if "@" in user:
                username, domain = user.split("@")
            else:
                username = user
                domain = None

            result = user_directory.RetrieveUserGroups(
                domain=domain,
                searchStr=username,
                exactMatch=True,
                findUsers=True,
                findGroups=False,
                belongsToUser=None,
                belongsToGroup=None
            )

            if result:
                print(f"✓ User exists: {user}\n")
            else:
                print(f"✗ User NOT found: {user}\n")
                missing_users.append(user)

        except Exception as e:
            print(f"✗ Error checking {user}: {e}\n")
            missing_users.append(user)

    return missing_users

# ============================================================================
# ✅ MAIN PROGRAM
# ============================================================================
def main():
    print("\n" + "=" * 80)
    print("vCenter Health Check Script")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")

    # Prompt for password
    password = getpass.getpass(f"Enter password for {VCENTER_USER}: ")

    # Attempt vCenter connection
    si = connect_to_vcenter(VCENTER_HOST, VCENTER_USER, password)

    # Test mode if no connection
    if not si:
        print("\n⚠ Test mode: using fake data since vCenter is not available\n")
        path_issues = FAKE_ISCSI_HOSTS
        missing_users = [user for user, exists in FAKE_USERS.items() if not exists]
    else:
        path_issues = check_iscsi_datastore_paths(si, EXPECTED_PATH_COUNT)
        missing_users = check_users_exist(si, USERS_TO_CHECK)

    # ================= SUMMARY OUTPUT =================
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    # ISCSI Paths
    print("\nISCSI PATHS:")
    for issue in path_issues:
        if issue["active_paths"] >= issue["total_paths"]:
            status = "✅"  # Fully OK
        elif issue["active_paths"] > 0:
            status = "⚠"  # Partially OK
        else:
            status = "✗"  # Failed
        print(
            f"{status} Host: {issue['host']}, Datastore: {issue['datastore']}, "
            f"{issue['active_paths']}/{issue['total_paths']} active paths"
        )

    # Users
    print("\nUSERS:")
    for user in USERS_TO_CHECK:
        if user in missing_users:
            status = "✗"  # Missing
        else:
            status = "✅"  # Exists
        print(f"{status} {user}")

    print("\n" + "=" * 80)

# ============================================================================
# ✅ START PROGRAM
# ============================================================================
if __name__ == "__main__":
    main()
