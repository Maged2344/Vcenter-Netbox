import socket
import time

# IPA servers per environment/AZ (add as many as you want)
IPA_SERVERS = {
    "DT_AZ1": [
        "dember1-z1-b99.infra.dev.pndrs.de",
        "sdpvvcb1001.infra.dev.pndrs.de",
        "sdpvvcb1002.infra.dev.pndrs.de",
        "sdpappb1001.infra.dev.pndrs.de",
        "sdpappb1002.infra.dev.pndrs.de",
        "sdpappb1003.infra.dev.pndrs.de",
        "sdpappb1004.infra.dev.pndrs.de",
        "dember1-z1-b4.infra.dev.pndrs.de",
        "sdpappb1005.infra.dev.pndrs.de",
        "dember1-z1-b5.infra.dev.pndrs.de",
        "dember1-z1-b6.infra.dev.pndrs.de",
        "dember1-z1-b9.infra.dev.pndrs.de",
        "dember1-z1-b60.infra.dev.pndrs.de",
        "sdpappb1007.infra.dev.pndrs.de",
        "dember1-z1-b7.infra.dev.pndrs.de",
        "sdpappb1008.infra.dev.pndrs.de",
        "dember1-z1-b8.infra.dev.pndrs.de",
        "sdpappb1009.infra.dev.pndrs.de",
        "sdpappb1010.infra.dev.pndrs.de",
        "dember1-z1-b57.infra.dev.pndrs.de",
        "sdpappb1011.infra.dev.pndrs.de",
        "sdpappb1012.infra.dev.pndrs.de",
        "dember1-z1-b52.infra.dev.pndrs.de",
        "sdpappb1013.infra.dev.pndrs.de",
        "sdpappb1016.infra.dev.pndrs.de",
        "sdpja8jlep8.infra.dev.pndrs.de",
        "sdpappb1017.infra.dev.pndrs.de",
        "sdpappb1018.infra.dev.pndrs.de",
        "sdpappb1020.infra.dev.pndrs.de",
        "sdpappb1021.infra.dev.pndrs.de",
        "sdpappb1023.infra.dev.pndrs.de",
        "sdpappb1026.infra.dev.pndrs.de",
        "sdpappb1027.infra.dev.pndrs.de",
        "sdpappb1029.infra.dev.pndrs.de",
        "sdpappb1030.infra.dev.pndrs.de",
        "sdpappb1031.infra.dev.pndrs.de",
        "sdpappb1033.infra.dev.pndrs.de",
        "sdpappb1034.infra.dev.pndrs.de",
        "sdpappb1035.infra.dev.pndrs.de",
        "sdpappb1036.infra.dev.pndrs.de",
        "sdpappb1037.infra.dev.pndrs.de",
        "sdpappb1038.infra.dev.pndrs.de",
        "sdpappb1039.infra.dev.pndrs.de",
        "sdpappb1040.infra.dev.pndrs.de",
        "sdpappb1041.infra.dev.pndrs.de",
        "sdpappb1042.infra.dev.pndrs.de",
        "sdpappb1043.infra.dev.pndrs.de",
        "sdpappb1044.infra.dev.pndrs.de",
        "dember1-z1-b45.infra.dev.pndrs.de",
        "dember1-z1-b46.infra.dev.pndrs.de",
        "dember1-z1-b47.infra.dev.pndrs.de",
        "dember1-z1-b48.infra.dev.pndrs.de",
        "dember1-z1-b49.infra.dev.pndrs.de",
        "dember1-z1-b50.infra.dev.pndrs.de",
        "dember1-z1-b51.infra.dev.pndrs.de",
        "dember1-z1-b54.infra.dev.pndrs.de",
        "dember1-z1-b55.infra.dev.pndrs.de",
        "dember1-z1-b56.infra.dev.pndrs.de",
        "dember1-z1-b11.ice.test.pndrs.de",
        "dember1-z1-b12.ice.test.pndrs.de",
        "dember1-z1-b13.ice.test.pndrs.de",
        "dember1-z1-b58.infra.dev.pndrs.de",
        "dember1-z1-b59.infra.dev.pndrs.de",
        "dember1-z1-b1.infra.dev.pndrs.de",
        "dember1-z1-b61.infra.dev.pndrs.de",
        "dember1-z1-b62.infra.dev.pndrs.de",
        "dember1-z1-b63.infra.dev.pndrs.de",
        "dember1-z1-b64.infra.dev.pndrs.de",
        "dember1-z1-b65.infra.dev.pndrs.de",
        "dember1-z1-b66.infra.dev.pndrs.de",
        "dember1-z1-b67.infra.dev.pndrs.de",
        "dember1-z1-b68.infra.dev.pndrs.de",
        "dember1-z1-b99.infra.dev.pndrs.de",
        "dember1-z1-b69.infra.dev.pndrs.de",
        "dember1-z1-b70.infra.dev.pndrs.de",
        "dember1-z1-b71.infra.dev.pndrs.de",
        "dember1-z1-b72.infra.dev.pndrs.de",
        "dember1-z1-b73.infra.dev.pndrs.de",
        "sdpappb1019.infra.dev.pndrs.de",
        "sdpappb1022.infra.dev.pndrs.de",
        "sdpappb1028.infra.dev.pndrs.de",
        "sdpappb1032.infra.dev.pndrs.de",
    ],
    "DT_AZ2": [
        "dember1-z2-b99.infra.dev.pndrs.de",
        "dember1-z2-b2.infra.dev.pndrs.de",
        "dember1-z2-b3.infra.dev.pndrs.de",
        "dember1-z2-b5.infra.dev.pndrs.de",
        "dember1-z2-b6.infra.dev.pndrs.de",
        "dember1-z2-b7.infra.dev.pndrs.de",
        "dember1-z2-b8.infra.dev.pndrs.de",
        "dember1-z2-b9.infra.dev.pndrs.de",
        "dember1-z2-b10.infra.dev.pndrs.de",
        "dember1-z2-b11.infra.dev.pndrs.de",
        "dember1-z2-b12.infra.dev.pndrs.de",
        "dember1-z2-b17.infra.dev.pndrs.de",
        "dember1-z2-b99.infra.dev.pndrs.de",
        "dember1-z2-b13.infra.dev.pndrs.de",
    ],
}

REQUIRED_PORTS = [
    ("HTTP", 80, "tcp"),
    ("HTTPS", 443, "tcp"),
    ("LDAP", 389, "tcp"),
    ("LDAPS", 636, "tcp"),
    ("Kerberos", 88, "tcp"),
    ("Kerberos kpasswd", 464, "tcp"),
    ("DNS", 53, "tcp"),
]

TIMEOUT = 3  # seconds
OUTPUT_FILE = "connectivity_report.txt"
FAILED_FILE = "connectivity_failed.txt"
SUCCESS_FILE = "connectivity_success.txt"

def check_tcp(host, port):
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT):
            return True
    except Exception:
        return False

def main():
    results = []
    failed = []
    success_list = []
    total = 0
    success = 0
    fail = 0

    print("\n{:<35} {:<6} {:<20} {:<10}".format("Server", "Port", "Service", "Status"))
    print("-" * 75)
    for env, servers in IPA_SERVERS.items():
        print(f"\nEnvironment: {env}")
        for server in servers:
            for service, port, proto in REQUIRED_PORTS:
                if proto.lower() != "tcp":
                    continue
                total += 1
                status = check_tcp(server, port)
                msg = "CONNECTED" if status else "FAILED"
                row = (env, server, port, service, msg)
                if status:
                    success += 1
                    success_list.append(row)
                else:
                    fail += 1
                    failed.append(row)
                print("{:<35} {:<6} {:<20} {:<10}".format(server, port, service, msg))
                results.append(row)

    print("\nSummary:")
    print(f"  Total checks: {total}")
    print(f"  Successful : {success}")
    print(f"  Failed     : {fail}")

    # Write full report
    with open(OUTPUT_FILE, "w") as f:
        f.write("{:<15} {:<35} {:<6} {:<20} {:<10}\n".format("Env", "Server", "Port", "Service", "Status"))
        f.write("-" * 90 + "\n")
        for row in results:
            f.write("{:<15} {:<35} {:<6} {:<20} {:<10}\n".format(*row))
        f.write("\nSummary:\n")
        f.write(f"  Total checks: {total}\n")
        f.write(f"  Successful : {success}\n")
        f.write(f"  Failed     : {fail}\n")

    # Write failed only
    with open(FAILED_FILE, "w") as f:
        f.write("{:<15} {:<35} {:<6} {:<20} {:<10}\n".format("Env", "Server", "Port", "Service", "Status"))
        f.write("-" * 90 + "\n")
        for row in failed:
            f.write("{:<15} {:<35} {:<6} {:<20} {:<10}\n".format(*row))
        f.write(f"\nTotal failed: {fail}\n")

    # Write success only
    with open(SUCCESS_FILE, "w") as f:
        f.write("{:<15} {:<35} {:<6} {:<20} {:<10}\n".format("Env", "Server", "Port", "Service", "Status"))
        f.write("-" * 90 + "\n")
        for row in success_list:
            f.write("{:<15} {:<35} {:<6} {:<20} {:<10}\n".format(*row))
        f.write(f"\nTotal successful: {success}\n")

    print(f"\nReports written to {OUTPUT_FILE}, {FAILED_FILE}, {SUCCESS_FILE}")

if __name__ == "__main__":
    main()