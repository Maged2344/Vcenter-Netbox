#!/usr/bin/env python3
"""
IPA Client → IPA Server Firewall Connectivity Verifier (HTML Report)
====================================================================

This script SSHes into each **IPA client host** and checks whether it can reach
**all IPA servers** in its environment/AZ on all **required ports** for FreeIPA.
It produces a human-friendly **HTML report** and a machine-readable **JSON**.

WHY this design?
- Verifies connectivity *from the clients themselves*, which is what you need
  to validate firewalls/routing within each AZ.
- Avoids installing extra tools on the clients: uses Bash /dev/tcp and /dev/udp.

DEPENDENCIES (install on the machine that will run this script):
    pip install paramiko

USAGE (quick start):
    1) Edit the "CONFIG — EDIT THESE" section below (clients, users, keys, servers).
    2) Run:  python ipa_fw_connectivity_check.py
    3) Open: ipa_fw_report.html

NOTES & LIMITATIONS:
- UDP checks are "fire-and-forget": success means the datagram was sent without
  a local error; it does not confirm an application-layer response.
- Clients must have Bash (for /dev/tcp and /dev/udp). On most Linux hosts this is true.
- Bastion/jump host is supported (SSH ProxyCommand). See CLIENTS config.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import paramiko


# ---------------------------
# CONFIG — EDIT THESE
# ---------------------------

# TODO: List your IPA client hosts where checks should originate FROM.
# Each entry can specify:
#   host      -> hostname or IP of the client
#   user      -> SSH username to use
#   key       -> path to a private key file (PEM/OpenSSH). Leave None to use agent/password.
#   password  -> password for SSH (avoid if possible; prefer keys). Leave None if using key/agent.
#   bastion   -> OPTIONAL: hostname/IP of a jump host to reach the client; set None if not needed.
CLIENTS = [
    # EXAMPLES — replace with your real hosts
    {"host": "demfra13-z1-app1", "user": "cloudadmin", "key": "~/.ssh/id_rsa", "password": None, "bastion": None},
    {"host": "demfra13-z1-app2", "user": "cloudadmin", "key": "~/.ssh/id_rsa", "password": None, "bastion": "bastion.mycorp.local"},
]

# TODO: IPA servers per environment/AZ. Add/adjust as needed.
IPA_SERVERS = {
    # VE
    # "VE_AZ1": ["demfra13-z1-b7", "demfra13-z1-b8"],
    # "VE_AZ2": ["demfra13-z2-b7", "demfra13-z2-b8"],
    # # APP PROD DE
    # "APP_PROD_DE_AZ1": ["dember1-z1-b7", "dember1-z1-b8"],
    # "APP_PROD_DE_AZ2": ["dember1-z2-b7", "dember1-z2-b8"],
    # DT (example from your note)
    "DT_AZ1": ["sdpappb1002", "sdpappb1020"],
    "DT_AZ2": ["dember1-z2-b10", "dember1-z2-b11"],
}

# TODO: Required ports/protocols per FreeIPA (from Red Hat table).
# Use a list of tuples: (service_name, port, protocol)
REQUIRED_PORTS = [
    ("HTTP", 80, "tcp"),
    ("HTTPS", 443, "tcp"),
    ("LDAP", 389, "tcp"),
    ("LDAPS", 636, "tcp"),
    ("Kerberos", 88, "tcp"),
    ("Kerberos", 88, "udp"),
    ("Kerberos kpasswd", 464, "tcp"),
    ("Kerberos kpasswd", 464, "udp"),
    ("DNS", 53, "tcp"),
    ("DNS", 53, "udp"),
    ("NTP (optional)", 123, "udp"),
]

# TODO: Command timeouts (seconds). Increase if links are slow.
TCP_TIMEOUT = int(os.getenv("TCP_TIMEOUT", "3"))
UDP_TIMEOUT = int(os.getenv("UDP_TIMEOUT", "3"))

# TODO: Output artifact paths
OUTPUT_JSON = os.getenv("OUTPUT_JSON", "ipa_fw_results.json")
OUTPUT_HTML = os.getenv("OUTPUT_HTML", "ipa_fw_report.html")


# ---------------------------
# Internal types
# ---------------------------

@dataclass
class Client:
    host: str
    user: str
    key: Optional[str] = None
    password: Optional[str] = None
    bastion: Optional[str] = None


# ---------------------------
# SSH helpers
# ---------------------------

def _expand(path: Optional[str]) -> Optional[str]:
    return os.path.expanduser(path) if path else None

def ssh_run(client: Client, cmd: str, timeout: int = 10):
    """Run a shell command on the remote client over SSH.
    Returns: (exit_code, stdout, stderr)"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # SSH Proxy (bastion) support
    sock = None
    if client.bastion:
        bastion_cmd = f"ssh -W %h:%p {client.user}@{client.bastion}"
        sock = paramiko.ProxyCommand(bastion_cmd)

    try:
        ssh.connect(
            hostname=client.host,
            username=client.user,
            key_filename=_expand(client.key),
            password=client.password,
            timeout=timeout,
            sock=sock,
        )
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", "ignore")
        err = stderr.read().decode("utf-8", "ignore")
        rc = stdout.channel.recv_exit_status()
        return rc, out, err
    finally:
        try:
            ssh.close()
        except Exception:
            pass


# ---------------------------
# Connectivity checks (remote, via bash /dev/tcp and /dev/udp)
# ---------------------------

def check_tcp_from_client(client: Client, server: str, port: int) -> bool:
    cmd = f"bash -lc 'timeout {TCP_TIMEOUT} bash -c \">/dev/tcp/{server}/{port}\" >/dev/null 2>&1'"
    rc, _, _ = ssh_run(client, cmd, timeout=TCP_TIMEOUT + 5)
    return rc == 0

def check_udp_from_client(client: Client, server: str, port: int) -> bool:
    cmd = f"bash -lc 'timeout {UDP_TIMEOUT} bash -c \"echo ping >/dev/udp/{server}/{port}\" >/dev/null 2>&1'"
    rc, _, _ = ssh_run(client, cmd, timeout=UDP_TIMEOUT + 5)
    return rc == 0



# ---------------------------
# Orchestration
# ---------------------------

def build_clients():
    return [Client(**entry) for entry in CLIENTS]

def run_all_checks():
    results = {}
    clients = build_clients()

    for c in clients:
        results[c.host] = {"meta": {"user": c.user, "bastion": c.bastion}, "checks": []}
        for env, servers in IPA_SERVERS.items():
            for srv in servers:
                for service, port, proto in REQUIRED_PORTS:
                    try:
                        if proto.lower() == "tcp":
                            ok = check_tcp_from_client(c, srv, port)
                        else:
                            ok = check_udp_from_client(c, srv, port)
                    except Exception:
                        ok = False
                    results[c.host]["checks"].append(
                        {"env": env, "server": srv, "service": service, "port": port, "proto": proto, "ok": ok}
                    )
    return results


# ---------------------------
# HTML report
# ---------------------------

def html_escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def render_html(results):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_checks = sum(len(v["checks"]) for v in results.values())
    passed = sum(1 for v in results.values() for chk in v["checks"] if chk["ok"])
    failed = total_checks - passed

    rows = []
    for client, data in sorted(results.items()):
        checks = data["checks"]
        by_env = {}
        for chk in checks:
            by_env.setdefault(chk["env"], {}).setdefault(chk["server"], []).append(chk)

        for env, servers in sorted(by_env.items()):
            for server, chks in sorted(servers.items()):
                for chk in sorted(chks, key=lambda x: (x["service"], x["proto"], x["port"])):
                    status = "PASS" if chk["ok"] else "FAIL"
                    klass = "pass" if chk["ok"] else "fail"
                    rows.append(
                        f"<tr><td>{html_escape(client)}</td>"
                        f"<td>{html_escape(env)}</td>"
                        f"<td>{html_escape(server)}</td>"
                        f"<td>{html_escape(chk['service'])}</td>"
                        f"<td>{chk['port']}/{html_escape(chk['proto'].upper())}</td>"
                        f"<td class='{klass}'>{status}</td></tr>"
                    )

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>IPA Firewall Connectivity Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; margin: 24px; }}
    h1 {{ margin: 0 0 4px 0; }}
    .summary {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 16px 0 24px; }}
    .card {{ border: 1px solid #e3e3e3; border-radius: 12px; padding: 12px; text-align: center; }}
    .card h2 {{ margin: 8px 0 4px; font-size: 14px; font-weight: 600; color: #555; }}
    .card .num {{ font-size: 24px; font-weight: 700; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 8px; border-bottom: 1px solid #f0f0f0; text-align: left; }}
    thead th {{ background: #fafafa; }}
    tr:hover td {{ background: #fcfcfc; }}
    td.pass {{ color: #06795d; font-weight: 700; }}
    td.fail {{ color: #a40000; font-weight: 700; }}
    .footer {{ margin-top: 40px; color: #888; font-size: 12px; }}
    code {{ background: #f6f8fa; padding: 1px 6px; border-radius: 6px; }}
  </style>
</head>
<body>
  <h1>IPA Firewall Connectivity Report</h1>
  <div>Generated: {html_escape(ts)}</div>

  <div class="summary">
    <div class="card"><h2>Total checks</h2><div class="num">{total_checks}</div></div>
    <div class="card"><h2>Passed</h2><div class="num">{passed}</div></div>
    <div class="card"><h2>Failed</h2><div class="num">{failed}</div></div>
  </div>

  <h2>Per-Client Results</h2>
  <table>
    <thead>
      <tr><th>Client</th><th>Environment</th><th>IPA Server</th><th>Service</th><th>Port</th><th>Status</th></tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>

  <div class="footer">
    UDP checks confirm packet send only (no protocol handshake). For Kerberos/DNS deep tests,
    extend the script to perform a <code>kinit</code> or a DNS query.
  </div>
</body>
</html>"""
    return html


def main():
    results = run_all_checks()
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    html = render_html(results)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[✓] Wrote JSON: {OUTPUT_JSON}")
    print(f"[✓] Wrote HTML: {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
