#!/usr/bin/env python3
"""
vCenter iSCSI Datastore Path and User Checker

What this script does:
1) Connects to a vCenter Server using pyVmomi.
2) Iterates over all ESXi hosts.
3) Finds iSCSI LUNs (using a simple heuristic: 'iscsi' in canonicalName).
4) For each iSCSI LUN, determines Active/Total paths (prefers multipathInfo).
5) Prints a compact, human-readable per-host/per-LUN output.
6) Checks if specific users exist in vCenter identity sources.
7) Prints a clean summary.

Output symbols:
    ✓  = OK / Found / Pass
    ✗  = Problem / Missing / Fail

Notes:
- SSL certificate verification is disabled for convenience (like your original).
  For production, consider using proper CA trust.
- iSCSI detection is heuristic. If you have a better environment-specific
  indicator, you can tighten `is_iscsi_lun()`.
"""

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim

import ssl
import atexit
import getpass
from datetime import datetime


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
VCENTER_HOST = "demfra13-z1-b1.infra.nzero.group"
VCENTER_USER = "lu3782@infra.nzero.group"

# Required minimum number of active paths per iSCSI LUN
EXPECTED_PATH_COUNT = 2

# Users to verify in vCenter's identity sources
USERS_TO_CHECK = [
    "auto.aap.vcenter@infra.nzero.group",
    "auto.cloudify.vcenter@infra.nzero.group",
    "auto.iceflow.vcenter@infra.nzero.group",
]

# Status symbols for human-readable output
OK_MARK = "✓"
FAIL_MARK = "✗"


# -----------------------------------------------------------------------------
# Connection helpers
# -----------------------------------------------------------------------------
def connect_to_vcenter(host: str, user: str, password: str):
    """
    Establish a session to vCenter.

    We create an SSL context and disable certificate verification to
    avoid issues in environments with self-signed certs.

    Returns:
        ServiceInstance object on success, None on failure.
    """
    # Use TLSv1.2 context (matching your original intent)
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)

    # Disable certificate verification (convenience)
    context.verify_mode = ssl.CERT_NONE

    try:
        # Create vCenter connection
        si = SmartConnect(host=host, user=user, pwd=password, sslContext=context)

        # Ensure we disconnect cleanly when the script exits
        atexit.register(Disconnect, si)

        print(f"{OK_MARK} Connected to vCenter: {host}\n")
        return si

    except Exception as e:
        print(f"{FAIL_MARK} Failed to connect to vCenter: {e}")
        return None


def get_all_hosts(content):
    """
    Create a container view that includes all HostSystem objects.

    Why:
    - vCenter inventory can be large.
    - ContainerView efficiently narrows object retrieval.

    Returns:
        List of vim.HostSystem objects.
    """
    container = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.HostSystem], True
    )

    hosts = list(container.view)
    container.Destroy()
    return hosts


# -----------------------------------------------------------------------------
# Storage / Multipath helpers
# -----------------------------------------------------------------------------
def is_iscsi_lun(device) -> bool:
    """
    Identify whether a device appears to be an iSCSI LUN.

    This is a heuristic:
    - We keep the same approach you used: check if canonicalName contains "iscsi".
    - Many environments name iSCSI LUNs in a predictable way, but not all do.

    Returns:
        True if the device looks like an iSCSI disk, False otherwise.
    """
    try:
        # Only consider SCSI disks
        if not isinstance(device, vim.host.ScsiDisk):
            return False

        # canonicalName can be None in some edge cases
        cname = (device.canonicalName or "").lower()

        return "iscsi" in cname

    except Exception:
        # If anything odd happens, treat it as "not iSCSI"
        return False


def get_paths_for_lun(storage_system, device):
    """
    Determine Active/Total path counts for a given LUN.

    Logic:
    1) Prefer multipathInfo (more accurate).
    2) Fallback to operationalState (less accurate, but better than nothing).

    Returns:
        (active_paths, total_paths)
    """
    active_paths = 0
    total_paths = 0

    # -------------------------
    # 1) Preferred path method
    # -------------------------
    try:
        # multipathInfo describes each LUN's path list and states
        mp_info = storage_system.storageDeviceInfo.multipathInfo
        if mp_info and hasattr(mp_info, "lun"):
            for lun in mp_info.lun:
                # In many vSphere builds, lun.lun matches device.key
                if lun.lun == device.key:
                    paths = lun.path or []
                    total_paths = len(paths)

                    # Count paths that are explicitly 'active'
                    active_paths = sum(
                        1 for p in paths if getattr(p, "state", "").lower() == "active"
                    )

                    return active_paths, total_paths
    except Exception:
        # If multipath retrieval fails, we proceed to fallback
        pass

    # -------------------------
    # 2) Fallback method
    # -------------------------
    try:
        # operationalState isn't a path list in all environments,
        # but sometimes provides a rough health signal.
        states = getattr(device, "operationalState", None) or []
        total_paths = len(states)
        active_paths = sum(1 for s in states if str(s).lower() == "ok")
    except Exception:
        pass

    return active_paths, total_paths


def check_iscsi_paths(si, expected_paths: int):
    """
    Check iSCSI LUN paths across all hosts.

    Output format (per LUN per host):
        ✓/✗ Host: <host>
          Datastore: LUN <device.key>
          Active Paths: X/Y

    We label "Datastore" like your example:
        "Datastore: LUN key-..."

    Returns:
        issues: a list of dicts for LUNs with active_paths < expected_paths
                Each dict contains:
                    host, datastore_label, active_paths, total_paths
    """
    content = si.RetrieveContent()
    hosts = get_all_hosts(content)

    print("=" * 80)
    print("ISCSI DATASTORE PATH CHECK")
    print("=" * 80)

    issues = []

    # Iterate each ESXi host
    for host in hosts:
        host_name = host.name

        # Host storage system interface
        storage_system = host.configManager.storageSystem

        # If a host lacks storageSystem (rare), skip safely
        if not storage_system:
            continue

        # SCSI LUN list can be empty or missing in some edge cases
        scsi_luns = getattr(storage_system.storageDeviceInfo, "scsiLun", []) or []

        # Iterate each storage device
        for device in scsi_luns:
            # Only care about iSCSI LUNs
            if not is_iscsi_lun(device):
                continue

            # Active/Total path counting
            active_paths, total_paths = get_paths_for_lun(storage_system, device)

            # Your requested label shape
            datastore_label = f"LUN {device.key}"

            # Decide status by expected minimum active paths
            status = OK_MARK if active_paths >= expected_paths else FAIL_MARK

            # Print readable block
            print(f"{status} Host: {host_name}")
            print(f"  Datastore: {datastore_label}")
            print(f"  Active Paths: {active_paths}/{total_paths}")
            print()

            # Collect issues for summary
            if active_paths < expected_paths:
                issues.append(
                    {
                        "host": host_name,
                        "datastore_label": datastore_label,
                        "active_paths": active_paths,
                        "total_paths": total_paths,
                    }
                )

    return issues


# -----------------------------------------------------------------------------
# User verification helpers
# -----------------------------------------------------------------------------
def user_exists(user_directory, principal: str) -> bool:
    """
    Best-effort check to determine whether a user exists.

    Approach:
    - If principal is user@domain, attempt a search in that domain.
    - If not confirmed, search across all domains returned by vCenter.

    We avoid noisy diagnostics and just return True/False.

    Returns:
        True if a matching user can be found, False otherwise.
    """
    # Parse "user@domain" if present
    if "@" in principal:
        username, domain = principal.split("@", 1)
    else:
        username, domain = principal, None

    # -------------------------
    # 1) Search in hinted domain
    # -------------------------
    try:
        results = user_directory.RetrieveUserGroups(
            domain=domain,
            searchStr=username,
            belongsToGroup=None,
            belongsToUser=None,
            exactMatch=False,
            findUsers=True,
            findGroups=False,
        )

        for r in results or []:
            p = getattr(r, "principal", "") or ""
            # Exact principal match
            if p and principal.lower() == p.lower():
                return True
            # Loose match fallback (helps some directory setups)
            if username.lower() in p.lower():
                return True
    except Exception:
        pass

    # -------------------------
    # 2) Search all domains
    # -------------------------
    try:
        domains = user_directory.RetrieveDomainList()
        for dom in domains or []:
            try:
                results = user_directory.RetrieveUserGroups(
                    domain=dom.name,
                    searchStr=username,
                    belongsToGroup=None,
                    belongsToUser=None,
                    exactMatch=False,
                    findUsers=True,
                    findGroups=False,
                )

                for r in results or []:
                    p = getattr(r, "principal", "") or ""
                    if p and principal.lower() == p.lower():
                        return True
                    if username.lower() in p.lower():
                        return True
            except Exception:
                continue
    except Exception:
        pass

    return False


def check_users(si, users_to_check):
    """
    Print a clean user existence section.

    Output format:
        ================================================================================
        USER EXISTENCE CHECK
        ================================================================================
        ✓ User found: <user>
        ✗ User NOT found: <user>

    Returns:
        missing_users: list of principals not found.
    """
    content = si.RetrieveContent()
    user_directory = content.userDirectory

    print("=" * 80)
    print("USER EXISTENCE CHECK")
    print("=" * 80)

    missing_users = []

    for user in users_to_check:
        try:
            if user_exists(user_directory, user):
                print(f"{OK_MARK} User found: {user}\n")
            else:
                print(f"{FAIL_MARK} User NOT found: {user}\n")
                missing_users.append(user)

        except Exception:
            # If any error occurs, treat as not found for safety
            print(f"{FAIL_MARK} User NOT found: {user}\n")
            missing_users.append(user)

    return missing_users


# -----------------------------------------------------------------------------
# Summary printing
# -----------------------------------------------------------------------------
def print_summary(path_issues, missing_users):
    """
    Print a final summary in your requested style grouping:
        ISCSI PATHS:
        USERS:
    """
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()

    # -------------------------
    # iSCSI summary
    # -------------------------
    print("ISCSI PATHS:")

    if path_issues:
        for issue in path_issues:
            print(
                f"{FAIL_MARK} Host: {issue['host']}, "
                f"Datastore: {issue['datastore_label']}, "
                f"{issue['active_paths']}/{issue['total_paths']} active paths"
            )
    else:
        print(f"{OK_MARK} No iSCSI path issues detected.")

    print()

    # -------------------------
    # Users summary
    # -------------------------
    print("USERS:")

    if missing_users:
        for user in missing_users:
            print(f"{FAIL_MARK} {user}")
    else:
        print(f"{OK_MARK} All specified users exist in vCenter.")

    print()
    print("=" * 80)


# -----------------------------------------------------------------------------
# Main entrypoint
# -----------------------------------------------------------------------------
def main():
    """
    Main execution flow:
    1) Print header
    2) Prompt for password securely
    3) Connect to vCenter
    4) Check iSCSI paths
    5) Check users
    6) Print summary
    """
    print("\n" + "=" * 80)
    print("vCenter Health Check Script")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")

    # Secure password prompt (no echo to terminal)
    password = getpass.getpass(f"Enter password for {VCENTER_USER}: ")

    # Establish vCenter session
    si = connect_to_vcenter(VCENTER_HOST, VCENTER_USER, password)
    if not si:
        # Connection failed; exit gracefully
        return

    # Check iSCSI LUN path health
    path_issues = check_iscsi_paths(si, EXPECTED_PATH_COUNT)

    # Check user existence
    missing_users = check_users(si, USERS_TO_CHECK)

    # Print final summary
    print_summary(path_issues, missing_users)


# Correct Python entrypoint guard
if __name__ == "__main__":
    main()
