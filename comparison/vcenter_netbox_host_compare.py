#!/usr/bin/env python3
"""
vCenter ↔ NetBox ESXi Host Comparator (HTML Report)
---------------------------------------------------
Compares **hosts** (physical ESXi servers) between vCenter and NetBox and
produces an HTML report of mismatches. No updates are performed.

DEPENDENCIES (install on the machine that will run this script):
    python -m pip install --upgrade pip
    pip install pyvmomi pynetbox

USAGE (basic):
    # Option 1: edit the CONFIG section below (marked with TODOs) and run:
    python vcenter_netbox_host_compare.py

    # Option 2: override via env vars/CLI (see README for examples).

OUTPUT:
    - HTML report (default: vcenter_netbox_host_drift_report.html)
    - Optional JSON report if --output-json is provided.

IMPORTANT: Every place marked with "TODO" is where you may need to edit
           values (hostnames, tokens, role slugs, custom-field names, etc.).
"""
import argparse
import json
import os
import ssl
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# VMware SDK
try:
    from pyVim.connect import SmartConnect, Disconnect
    from pyVmomi import vim
except Exception as e:
    print("[!] Missing dependency 'pyvmomi'. Install with: pip install pyvmomi", file=sys.stderr)
    raise

# NetBox SDK
try:
    import pynetbox
except Exception as e:
    print("[!] Missing dependency 'pynetbox'. Install with: pip install pynetbox", file=sys.stderr)
    raise


# ---------------------------
# CONFIG — EDIT THESE (or override with env/CLI)
# ---------------------------

# TODO: vCenter connection details
VCENTER_HOST = os.getenv("VCENTER_HOST", "sdpvvcb1001.infra.dev.pndrs.de")            # vCenter FQDN or IP
VCENTER_USER = os.getenv("VCENTER_USER", "qd0330@infra.dev.pndrs.de")    # vCenter username
VCENTER_PASS = os.getenv("VCENTER_PASS", "password")                      # vCenter password
VCENTER_VERIFY_SSL = os.getenv("VCENTER_VERIFY_SSL", "false").lower() in ("1", "true", "yes")

# TODO: NetBox connection details
NETBOX_URL = os.getenv("NETBOX_URL", "http://netbox-black.bare.pandrosion.org/")         # NetBox base URL
NETBOX_TOKEN = os.getenv("NETBOX_TOKEN", "add token")                      # NetBox API token
NETBOX_VERIFY_SSL = os.getenv("NETBOX_VERIFY_SSL", "true").lower() in ("1", "true", "yes")

# TODO: Filter which devices to compare (commonly by role slug). Leave empty to compare all devices.
NB_DEVICE_ROLE_SLUG = os.getenv("NB_DEVICE_ROLE_SLUG", "esxi-host")        # e.g. "esxi-host" (create this role in NetBox)
NB_SITE_SLUG = os.getenv("NB_SITE_SLUG", "")                                # optional: filter by site slug

# TODO: Name matching rules (helps when NetBox uses short names and vCenter uses FQDNs)
#   - MODE 'short'      : compare on short hostname (strip domain) in lowercase (default)
#   - MODE 'fqdn'       : compare on full FQDN, lowercase
#   - MODE 'lowercase'  : lowercase only, keep whatever is provided
NAME_MATCH_MODE = os.getenv("NAME_MATCH_MODE", "short").lower()

# TODO: Optional static name mappings when names differ between systems
# e.g. {"esx01.mydomain.tld": "esx01-host"} or {"10.0.0.10": "esx01"}
NB_NAME_ALIASES = json.loads(os.getenv("NB_NAME_ALIASES", "{}"))

# TODO: Custom fields in NetBox used to store host specs
CF_CPU_CORES = os.getenv("CF_CPU_CORES", "cpu_cores")                      # integer cores
CF_RAM_GB = os.getenv("CF_RAM_GB", "ram_gb")                               # integer GB
CF_DATASTORES = os.getenv("CF_DATASTORES", "datastores")                   # list of datastore names (JSON or CSV)

# TODO: Output paths (can be overridden via CLI)
OUTPUT_HTML = os.getenv("OUTPUT_HTML", "vcenter_netbox_host_drift_report.html")


# ---------------------------
# Helpers
# ---------------------------

def normalize_name(name: Optional[str]) -> Optional[str]:
    """Normalize a hostname for matching between systems."""
    if not name:
        return None
    n = name.strip().lower()
    if NAME_MATCH_MODE == "short":
        return n.split(".")[0]  # strip domain
    if NAME_MATCH_MODE == "fqdn":
        return n
    if NAME_MATCH_MODE == "lowercase":
        return n
    # fallback
    return n.split(".")[0]

def as_set(x: Optional[List[Any]]) -> set:
    if x is None:
        return set()
    return set(x)

def safe(v):
    return "" if v is None else v

def human(v):
    """Render Python value as friendly text for HTML."""
    if isinstance(v, (list, set, tuple)):
        return ", ".join(map(str, sorted(v)))
    return str(v)


# ---------------------------
# vCenter data collection
# ---------------------------

def connect_vcenter() -> Any:
    """Connect to vCenter and return the ServiceInstance handle."""
    if VCENTER_VERIFY_SSL:
        context = None
    else:
        # Insecure context: skip SSL verification (for labs/self-signed)
        context = ssl._create_unverified_context()

    try:
        si = SmartConnect(host=VCENTER_HOST, user=VCENTER_USER, pwd=VCENTER_PASS, sslContext=context)
    except Exception as e:
        print(f"[!] Failed to connect to vCenter {VCENTER_HOST}: {e}", file=sys.stderr)
        raise
    return si

def extract_vcenter_host_data(host: "vim.HostSystem") -> Dict[str, Any]:
    """Normalize ESXi host attributes into a comparable dictionary."""
    name = host.name

    # CPU / Memory from summary.hardware
    hw = getattr(host.summary, "hardware", None)
    cpu_cores = getattr(hw, "numCpuCores", None) if hw else None
    cpu_threads = getattr(hw, "numCpuThreads", None) if hw else None
    mem_bytes = getattr(hw, "memorySize", None) if hw else None
    ram_gb = int(mem_bytes // (1024**3)) if mem_bytes is not None else None

    # Physical NICs
    pnic_names = []
    try:
        for pnic in host.config.network.pnic:
            if getattr(pnic, "device", None):
                pnic_names.append(pnic.device)  # e.g., "vmnic0"
    except Exception:
        pass

    # VMkernel NICs
    vmk_info = []
    mgmt_ip = None
    vmk_name_to_pg = {}  # vmk -> portgroup name (standard) when available

    try:
        for vnic in host.config.network.vnic:
            dev = getattr(vnic, "device", None)  # e.g., "vmk0"
            ip = None
            try:
                ip = vnic.spec.ip.ipAddress
            except Exception:
                pass

            pg_name = getattr(vnic, "portgroup", None)  # Only for Standard vSwitch PGs
            vmk_info.append({
                "device": dev,
                "ip": ip,
                "portgroup": pg_name
            })
            if dev == "vmk0" and ip:
                mgmt_ip = ip
            if dev and pg_name:
                vmk_name_to_pg[dev] = pg_name
    except Exception:
        pass

    # Standard vSwitch portgroups and VLANs
    std_portgroups = []  # list of dicts: {name, vlan_id, vswitch}
    try:
        for pg in host.config.network.portgroup:
            vlan_id = None
            vsw_name = None
            try:
                vlan_id = pg.spec.vlanId
                vsw_name = pg.spec.vswitchName
            except Exception:
                pass
            std_name = None
            try:
                std_name = pg.spec.name
            except Exception:
                std_name = getattr(pg, "name", None)
            std_portgroups.append({
                "name": std_name,
                "vlan_id": vlan_id,
                "switch": vsw_name,
                "type": "standard"
            })
    except Exception:
        pass

    # Distributed Portgroups (best-effort). VLANs may require extra permissions.
    dvs_portgroups = []
    try:
        for net in getattr(host, "network", []) or []:
            if isinstance(net, vim.dvs.DistributedVirtualPortgroup):
                vlan_id = None
                try:
                    vlan_spec = net.config.defaultPortConfig.vlan
                    # Known cases: TrunkVlanSpec (ranges), VlanIdSpec (single)
                    if hasattr(vlan_spec, "vlanId"):
                        vlan_id = getattr(vlan_spec, "vlanId", None)
                except Exception:
                    pass
                dvs_portgroups.append({
                    "name": getattr(net, "name", None),
                    "vlan_id": vlan_id,
                    "switch": getattr(net.config, "distributedVirtualSwitchName", None),
                    "type": "distributed"
                })
    except Exception:
        pass

    # Datastores
    datastore_names = []
    try:
        for ds in host.datastore:
            if getattr(ds, "name", None):
                datastore_names.append(ds.name)
    except Exception:
        pass

    # Build a helpful map: vmk -> vlan_id (only resolvable for Standard vswitch PGs)
    vmk_vlan_map = {}
    std_pg_vlan_lookup = {pg["name"]: pg["vlan_id"] for pg in std_portgroups if pg.get("name")}
    for vmk_name, pg in vmk_name_to_pg.items():
        vmk_vlan_map[vmk_name] = std_pg_vlan_lookup.get(pg)

    return {
        "hostname": name,
        "norm_name": normalize_name(name),
        "mgmt_ip": mgmt_ip,
        "cpu_cores": cpu_cores,
        "cpu_threads": cpu_threads,
        "ram_gb": ram_gb,
        "pnics": sorted(set(pnic_names)),
        "vmkernels": vmk_info,
        "vmk_vlan_map": vmk_vlan_map,  # e.g. {"vmk0": 10}
        "portgroups": std_portgroups + dvs_portgroups,  # list of dicts
        "datastores": sorted(set(datastore_names)),
    }

def get_vcenter_hosts() -> Dict[str, Dict[str, Any]]:
    """Collect data for all hosts visible in vCenter: returns map normalized_name -> data."""
    si = connect_vcenter()
    content = si.RetrieveContent()
    result = {}

    try:
        for dc in content.rootFolder.childEntity:
            if not hasattr(dc, "hostFolder"):
                continue
            for entity in dc.hostFolder.childEntity:
                # entity can be ClusterComputeResource or ComputeResource
                if hasattr(entity, "host"):
                    for host in entity.host:
                        data = extract_vcenter_host_data(host)
                        key = data.get("norm_name") or normalize_name(data.get("hostname"))
                        if not key:
                            key = data.get("hostname") or f"host-{len(result)+1}"
                        result[key] = data
    finally:
        try:
            Disconnect(si)
        except Exception:
            pass
    return result


# ---------------------------
# NetBox data collection
# ---------------------------

def get_netbox() -> "pynetbox.api":
    """Connect to NetBox API client."""
    nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)
    # Control SSL verification (useful with self-signed certs)
    nb.http_session.verify = NETBOX_VERIFY_SSL
    return nb

def _parse_datastores_field(value) -> List[str]:
    """Accept JSON list, CSV string, or list; return list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value]
    if isinstance(value, str):
        v = value.strip()
        if not v:
            return []
        # Try JSON first
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except Exception:
            pass
        # Fallback to CSV
        return [s.strip() for s in v.split(",") if s.strip()]
    # unknown type
    return [str(value)]

def get_netbox_hosts() -> Dict[str, Dict[str, Any]]:
    """Collect expected data for ESXi hosts from NetBox: returns map normalized_name -> data."""
    nb = get_netbox()

    query = {}
    # Filter by device role (recommended)
    if NB_DEVICE_ROLE_SLUG:
        query["role"] = NB_DEVICE_ROLE_SLUG  # TODO: ensure this role slug exists in your NetBox
    if NB_SITE_SLUG:
        query["site"] = NB_SITE_SLUG  # optional filter by site

    try:
        devices = nb.dcim.devices.filter(**query)
    except Exception as e:
        print(f"[!] Failed to query NetBox devices: {e}", file=sys.stderr)
        raise

    result = {}

    for dev in devices:
        name = dev.name
        # Apply alias mapping first if provided
        alias_name = NB_NAME_ALIASES.get(name) or name
        norm = normalize_name(alias_name)

        # Primary management IP
        mgmt_ip = None
        try:
            # Prefer primary_ip4 if available; fall back to primary_ip
            pip = getattr(dev, "primary_ip4", None) or getattr(dev, "primary_ip", None)
            if pip and getattr(pip, "address", None):
                mgmt_ip = pip.address.split("/")[0]
        except Exception:
            pass

        # Custom fields (ensure they exist in NetBox → Admin → Custom Fields)
        cf = getattr(dev, "custom_fields", {}) or {}
        cpu_cores = cf.get(CF_CPU_CORES)
        ram_gb = cf.get(CF_RAM_GB)
        datastores_cf = _parse_datastores_field(cf.get(CF_DATASTORES))

        # Interfaces
        try:
            ifaces = list(nb.dcim.interfaces.filter(device_id=dev.id))
        except Exception:
            ifaces = []

        # Physical NIC names modeled in NetBox (heuristic: names starting with "vmnic")
        pnic_names = []
        for iface in ifaces:
            n = (iface.name or "").strip()
            if n.lower().startswith("vmnic"):
                pnic_names.append(n)

        # VMkernel interfaces (names like vmk0, vmk1) with untagged VLAN (if any)
        vmk_info = []
        for iface in ifaces:
            n = (iface.name or "").strip()
            if n.lower().startswith("vmk"):
                # Try to fetch IP assigned to this interface (if modeled)
                ip_addr = None
                try:
                    ips = nb.ipam.ip_addresses.filter(device_id=dev.id, interface_id=iface.id)
                    if ips:
                        ip_addr = ips[0].address.split("/")[0]
                except Exception:
                    pass

                vlan_id = None
                try:
                    if getattr(iface, "untagged_vlan", None):
                        vlan_id = iface.untagged_vlan.vid
                except Exception:
                    pass

                vmk_info.append({
                    "device": n,
                    "ip": ip_addr,
                    "vlan_id": vlan_id
                })

        result[norm] = {
            "id": dev.id,
            "hostname": name,
            "norm_name": norm,
            "mgmt_ip": mgmt_ip,
            "cpu_cores": cpu_cores,
            "ram_gb": ram_gb,
            "pnics": sorted(set(pnic_names)),
            "vmkernels": vmk_info,
            "datastores": sorted(set(datastores_cf)),
        }

    return result


# ---------------------------
# Comparison
# ---------------------------

def compare_hosts(vc: Dict[str, Any], nb: Dict[str, Any]) -> Dict[str, Any]:
    """Return a dict with mismatches between one vCenter host and one NetBox device."""
    mismatches = {}

    # Management IP
    if safe(vc.get("mgmt_ip")) != safe(nb.get("mgmt_ip")):
        mismatches["mgmt_ip"] = {
            "vcenter": vc.get("mgmt_ip"),
            "netbox": nb.get("mgmt_ip")
        }

    # CPU cores
    if str(safe(vc.get("cpu_cores"))) != str(safe(nb.get("cpu_cores"))):
        mismatches["cpu_cores"] = {
            "vcenter": vc.get("cpu_cores"),
            "netbox": nb.get("cpu_cores")
        }

    # RAM
    if str(safe(vc.get("ram_gb"))) != str(safe(nb.get("ram_gb"))):
        mismatches["ram_gb"] = {
            "vcenter": vc.get("ram_gb"),
            "netbox": nb.get("ram_gb")
        }

    # Datastores
    if as_set(vc.get("datastores")) != as_set(nb.get("datastores")):
        mismatches["datastores"] = {
            "vcenter": sorted(as_set(vc.get("datastores"))),
            "netbox": sorted(as_set(nb.get("datastores")))
        }

    # Physical NIC names
    if as_set(vc.get("pnics")) != as_set(nb.get("pnics")):
        mismatches["pnics"] = {
            "vcenter": sorted(as_set(vc.get("pnics"))),
            "netbox": sorted(as_set(nb.get("pnics")))
        }

    # VMkernel interface presence (names only)
    vc_vmk_names = {vmk.get("device") for vmk in vc.get("vmkernels", []) if vmk.get("device")}
    nb_vmk_names = {vmk.get("device") for vmk in nb.get("vmkernels", []) if vmk.get("device")}
    if vc_vmk_names != nb_vmk_names:
        mismatches["vmkernel_names"] = {
            "vcenter": sorted(vc_vmk_names),
            "netbox": sorted(nb_vmk_names)
        }

    # VMkernel VLAN check (best-effort): compare VLAN on vmkX when both sides have a value
    nb_vmk_vlan = {vmk.get("device"): vmk.get("vlan_id") for vmk in nb.get("vmkernels", []) if vmk.get("device")}
    vc_vmk_vlan = vc.get("vmk_vlan_map", {})  # only resolvable for Standard switches

    vmk_vlan_diff = {}
    for vmk_name in set(list(nb_vmk_vlan.keys()) + list(vc_vmk_vlan.keys())):
        if safe(vc_vmk_vlan.get(vmk_name)) != safe(nb_vmk_vlan.get(vmk_name)):
            vmk_vlan_diff[vmk_name] = {
                "vcenter_vlan": vc_vmk_vlan.get(vmk_name),
                "netbox_vlan": nb_vmk_vlan.get(vmk_name)
            }
    if vmk_vlan_diff:
        mismatches["vmkernel_vlans"] = vmk_vlan_diff

    return mismatches

def build_comparison(vc_hosts: Dict[str, Dict[str, Any]], nb_hosts: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Compare all hosts and return a comprehensive report structure."""
    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "vcenter_hosts": len(vc_hosts),
            "netbox_hosts": len(nb_hosts),
            "ok": 0,
            "mismatch": 0,
            "missing_in_netbox": 0,
            "missing_in_vcenter": 0,
        },
        "hosts": {}  # key (normalized name) -> {display_name, status, mismatches, vc, nb}
    }

    # Hosts present in vCenter
    for key, vc in vc_hosts.items():
        # Allow an explicit alias mapping: if vCenter name is aliased to a NetBox name, use that key
        nb_key = NB_NAME_ALIASES.get(vc.get("hostname")) or key
        nb = nb_hosts.get(nb_key) or nb_hosts.get(key)
        if not nb:
            report["hosts"][key] = {
                "display_name": vc.get("hostname"),
                "status": "MISSING_IN_NETBOX",
                "mismatches": {"missing": "Host not found in NetBox"},
                "vcenter": vc,
                "netbox": None
            }
            report["summary"]["missing_in_netbox"] += 1
            continue

        mismatches = compare_hosts(vc, nb)
        if mismatches:
            status = "MISMATCH"
            report["summary"]["mismatch"] += 1
        else:
            status = "OK"
            report["summary"]["ok"] += 1

        report["hosts"][key] = {
            "display_name": vc.get("hostname"),
            "status": status,
            "mismatches": mismatches,
            "vcenter": vc,
            "netbox": nb
        }

    # Hosts present in NetBox but missing in vCenter
    for key, nb in nb_hosts.items():
        if key not in vc_hosts:
            report["hosts"][key] = {
                "display_name": nb.get("hostname"),
                "status": "MISSING_IN_VCENTER",
                "mismatches": {"missing": "Host not found in vCenter"},
                "vcenter": None,
                "netbox": nb
            }
            report["summary"]["missing_in_vcenter"] += 1

    return report


# ---------------------------
# HTML report generation
# ---------------------------

def html_escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def render_html(report: Dict[str, Any]) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = report["summary"]["vcenter_hosts"]
    ok = report["summary"]["ok"]
    mm = report["summary"]["mismatch"]
    miss_nb = report["summary"]["missing_in_netbox"]
    miss_vc = report["summary"]["missing_in_vcenter"]

    rows = []
    for key, data in sorted(report["hosts"].items(), key=lambda x: (x[1]["status"], x[0])):
        name = data.get("display_name") or key
        status = data["status"]
        badge_class = {
            "OK": "ok",
            "MISMATCH": "mismatch",
            "MISSING_IN_NETBOX": "missing",
            "MISSING_IN_VCENTER": "missing"
        }.get(status, "unknown")

        # Compact mismatch summary for table view
        mm_keys = ", ".join(sorted(list(data["mismatches"].keys()))) if data["mismatches"] else ""
        rows.append(f"""
            <tr>
              <td class="host">{html_escape(name)}</td>
              <td class="status {badge_class}">{html_escape(status)}</td>
              <td>{html_escape(mm_keys)}</td>
              <td><a href="#host-{html_escape(key)}">Details</a></td>
            </tr>
        """)

    # Per-host details sections
    details_sections = []
    for key, data in sorted(report["hosts"].items()):
        name = data.get("display_name") or key
        status = data["status"]
        details = data["mismatches"] or {}
        vc = data["vcenter"]
        nb = data["netbox"]

        # Render mismatch table
        mismatch_rows = []
        if not details:
            mismatch_rows.append('<tr><td colspan="3">No mismatches 🎉</td></tr>')
        else:
            for k, v in details.items():
                if isinstance(v, dict) and "vcenter" in v and "netbox" in v:
                    left = human(v["vcenter"])
                    right = human(v["netbox"])
                else:
                    left = human(v)
                    right = ""
                mismatch_rows.append(f"""
                  <tr>
                    <td>{html_escape(k)}</td>
                    <td>{html_escape(left)}</td>
                    <td>{html_escape(right)}</td>
                  </tr>
                """)

        # Quick facts table
        def fact_row(label, left, right):
            return f"""
              <tr>
                <th>{html_escape(label)}</th>
                <td>{html_escape(human(left))}</td>
                <td>{html_escape(human(right))}</td>
              </tr>
            """

        facts = []
        facts.append(fact_row("Mgmt IP", (vc or {}).get("mgmt_ip") if vc else None, (nb or {}).get("mgmt_ip") if nb else None))
        facts.append(fact_row("CPU Cores", (vc or {}).get("cpu_cores") if vc else None, (nb or {}).get("cpu_cores") if nb else None))
        facts.append(fact_row("RAM (GB)", (vc or {}).get("ram_gb") if vc else None, (nb or {}).get("ram_gb") if nb else None))
        facts.append(fact_row("Datastores", (vc or {}).get("datastores") if vc else None, (nb or {}).get("datastores") if nb else None))
        facts.append(fact_row("PNICs", (vc or {}).get("pnics") if vc else None, (nb or {}).get("pnics") if nb else None))

        details_sections.append(f"""
          <section id="host-{html_escape(key)}" class="host-section">
            <h3>{html_escape(name)} <span class="pill {badge_class}">{html_escape(status)}</span></h3>

            <h4>Quick Facts</h4>
            <table class="kv">
              <thead><tr><th>Field</th><th>vCenter</th><th>NetBox</th></tr></thead>
              <tbody>
                {''.join(facts)}
              </tbody>
            </table>

            <h4>Mismatches</h4>
            <table class="mismatch">
              <thead><tr><th>Field</th><th>vCenter</th><th>NetBox</th></tr></thead>
              <tbody>
                {''.join(mismatch_rows)}
              </tbody>
            </table>
          </section>
        """)

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>vCenter ↔ NetBox Host Drift Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; margin: 24px; }}
    h1 {{ margin-top: 0; }}
    .summary {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin: 16px 0 24px; }}
    .card {{ border: 1px solid #e3e3e3; border-radius: 12px; padding: 12px; text-align: center; }}
    .card h2 {{ margin: 8px 0 4px; font-size: 14px; font-weight: 600; color: #555; }}
    .card .num {{ font-size: 24px; font-weight: 700; }}
    table {{ width: 100%; border-collapse: collapse; }}
    table thead th {{ text-align: left; background: #fafafa; border-bottom: 1px solid #e6e6e6; padding: 8px; }}
    table td, table th {{ padding: 8px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }}
    tr:hover td {{ background: #fcfcfc; }}
    .status.ok {{ color: #0a7; font-weight: 700; }}
    .status.mismatch {{ color: #d67a00; font-weight: 700; }}
    .status.missing {{ color: #d00; font-weight: 700; }}
    .pill {{ padding: 2px 8px; border-radius: 999px; font-size: 12px; vertical-align: middle; }}
    .pill.ok {{ background: #e6fbf4; color: #06795d; border: 1px solid #b4eedc; }}
    .pill.mismatch {{ background: #fff6e6; color: #8a5a00; border: 1px solid #ffe2b3; }}
    .pill.missing {{ background: #ffecec; color: #a40000; border: 1px solid #ffc7c7; }}
    .host {{ font-weight: 600; }}
    .host-section {{ margin: 36px 0; }}
    .kv, .mismatch {{ margin-top: 8px; }}
    .footer {{ margin-top: 40px; color: #888; font-size: 12px; }}
    code {{ background: #f6f8fa; padding: 1px 6px; border-radius: 6px; }}
  </style>
</head>
<body>
  <h1>vCenter ↔ NetBox Host Drift Report</h1>
  <div>Generated: {html_escape(ts)}</div>

  <div class="summary">
    <div class="card"><h2>vCenter Hosts</h2><div class="num">{total}</div></div>
    <div class="card"><h2>OK</h2><div class="num">{ok}</div></div>
    <div class="card"><h2>Mismatches</h2><div class="num">{mm}</div></div>
    <div class="card"><h2>Missing in NetBox</h2><div class="num">{miss_nb}</div></div>
    <div class="card"><h2>Missing in vCenter</h2><div class="num">{miss_vc}</div></div>
  </div>

  <h2>Hosts Overview</h2>
  <table>
    <thead>
      <tr><th>Host</th><th>Status</th><th>Mismatch Keys</th><th>Details</th></tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>

  <h2>Details</h2>
  {''.join(details_sections)}

  <div class="footer">
    This report is read-only. No changes were made to vCenter or NetBox.<br/>
    Tip: Adjust fields compared in the script (see TODOs in config section).<br/>
    Name matching mode: <code>{html_escape(NAME_MATCH_MODE)}</code>
  </div>
</body>
</html>"""
    return html


# ---------------------------
# CLI / MAIN
# ---------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Compare ESXi hosts between vCenter and NetBox and output an HTML report.")
    p.add_argument("--output-html", default=OUTPUT_HTML, help="Path to write the HTML report")
    p.add_argument("--output-json", default=None, help="Optional path to also write a JSON report")
    p.add_argument("--vcenter-host", default=VCENTER_HOST, help="vCenter host (FQDN/IP)")
    p.add_argument("--vcenter-user", default=VCENTER_USER, help="vCenter username")
    p.add_argument("--vcenter-pass", default=VCENTER_PASS, help="vCenter password")
    p.add_argument("--vcenter-verify-ssl", action="store_true", default=VCENTER_VERIFY_SSL, help="Verify vCenter SSL certs")
    p.add_argument("--netbox-url", default=NETBOX_URL, help="NetBox base URL")
    p.add_argument("--netbox-token", default=NETBOX_TOKEN, help="NetBox API token")
    p.add_argument("--netbox-verify-ssl", action="store_true", default=NETBOX_VERIFY_SSL, help="Verify NetBox SSL certs")
    p.add_argument("--nb-role", default=NB_DEVICE_ROLE_SLUG, help="Filter NetBox devices by role slug")
    p.add_argument("--nb-site", default=NB_SITE_SLUG, help="Optional filter NetBox devices by site slug")
    p.add_argument("--name-match-mode", default=NAME_MATCH_MODE, choices=["short", "fqdn", "lowercase"], help="Hostname normalization strategy")
    return p.parse_args()

def main():
    global VCENTER_HOST, VCENTER_USER, VCENTER_PASS, VCENTER_VERIFY_SSL
    global NETBOX_URL, NETBOX_TOKEN, NETBOX_VERIFY_SSL
    global NB_DEVICE_ROLE_SLUG, NB_SITE_SLUG, NAME_MATCH_MODE

    args = parse_args()

    # Apply CLI overrides back to globals (used by helper functions)
    VCENTER_HOST = args.vcenter_host
    VCENTER_USER = args.vcenter_user
    VCENTER_PASS = args.vcenter_pass
    VCENTER_VERIFY_SSL = args.vcenter_verify_ssl

    NETBOX_URL = args.netbox_url
    NETBOX_TOKEN = args.netbox_token
    NETBOX_VERIFY_SSL = args.netbox_verify_ssl

    NB_DEVICE_ROLE_SLUG = args.nb_role
    NB_SITE_SLUG = args.nb_site
    NAME_MATCH_MODE = args.name_match_mode

    try:
        print("[*] Collecting vCenter hosts ...")
        vc_data = get_vcenter_hosts()
        print(f"    Found {len(vc_data)} hosts in vCenter (normalized)")

        print("[*] Collecting NetBox hosts ...")
        nb_data = get_netbox_hosts()
        print(f"    Found {len(nb_data)} hosts in NetBox (after filters, normalized)")

        print("[*] Comparing ...")
        report = build_comparison(vc_data, nb_data)

        html = render_html(report)
        out_html = args.output_html
        with open(out_html, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[✓] HTML report written to: {out_html}")

        if args.output_json:
            with open(args.output_json, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            print(f"[✓] JSON report written to: {args.output_json}")

        # Exit code semantics:
        # 0 -> all OK and no missing
        # 2 -> mismatches or missing hosts
        # 1 -> error (uncaught)
        if report["summary"]["mismatch"] or report["summary"]["missing_in_netbox"] or report["summary"]["missing_in_vcenter"]:
            sys.exit(2)
        sys.exit(0)

    except Exception as e:
        print(f"[!] Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
