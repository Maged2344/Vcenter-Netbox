import socket
import time

# IPA servers per environment/AZ
IPA_SERVERS = {
    "DT_AZ1": ["sdpappb1002", "sdpappb1020"],
    "DT_AZ2": ["dember1-z2-b10", "dember1-z2-b11"],
}

# Required ports/protocols per FreeIPA (TCP only for telnet)
REQUIRED_PORTS = [
    ("HTTP", 80, "tcp"),
    ("HTTPS", 443, "tcp"),
    ("LDAP", 389, "tcp"),
    ("LDAPS", 636, "tcp"),
    ("Kerberos", 88, "tcp"),
    ("Kerberos kpasswd", 464, "tcp"),
    ("DNS", 53, "tcp"),
    # UDP ports are ignored for telnet
]

TIMEOUT = 3  # seconds

def check_tcp(host, port):
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT):
            return True
    except Exception:
        return False

def main():
    for env, servers in IPA_SERVERS.items():
        print(f"\nEnvironment: {env}")
        for server in servers:
            for service, port, proto in REQUIRED_PORTS:
                if proto.lower() != "tcp":
                    continue  # skip UDP for telnet
                status = check_tcp(server, port)
                msg = "CONNECTED" if status else "FAILED"
                print(f"{server}:{port} ({service}) ... {msg}")

if __name__ == "__main__":
    main()