
from scapy.all import (
    Ether, IP, UDP,
    BOOTP, DHCP,
    sendp, sniff,
send
)
import random
import threading

INTERFACE = "lo0"

# The server is bound to port 1067 instead of 67 (non-privileged port).
DHCP_SERVER_IP = "127.0.0.1"
DHCP_SERVER_PORT = 1067

# We'll send from a random ephemeral source port, or we can fix it to 68 for "real" behavior
CLIENT_PORT = 68

# Fake MAC for simulation
CLIENT_MAC = "00:11:22:33:44:55"


def build_dhcp_discover():

    # We'll generate a random transaction ID
    xid = random.randint(1, 0xFFFFFFFF)

    # Ethernet layer: src MAC -> CLIENT_MAC, dst MAC -> broadcast
    ether = Ether(src=CLIENT_MAC, dst="ff:ff:ff:ff:ff:ff")

    # IP layer: source 0.0.0.0, destination is your local DHCP server IP
    # but note, typical DHCP would be broadcast to 255.255.255.255
    ip = IP(src="0.0.0.0", dst=DHCP_SERVER_IP)

    # UDP layer: source = 68, destination = 1067
    udp = UDP(sport=CLIENT_PORT, dport=DHCP_SERVER_PORT)

    # BOOTP layer
    bootp = BOOTP(chaddr=[bytes.fromhex(CLIENT_MAC.replace(":", ""))],
                  xid=xid,
                  flags=0x0000,  # no broadcast flag
                  ciaddr="0.0.0.0",
                  yiaddr="0.0.0.0",
                  siaddr="0.0.0.0",
                  giaddr="0.0.0.0")

    # DHCP layer with "discover"
    dhcp = DHCP(options=[("message-type", "discover"),
                         ("end")])

    # Combine layers
    #dhcp_discover_packet = ether / ip / udp / bootp / dhcp
    dhcp_discover_packet = ip / udp / bootp / dhcp
    send(dhcp_discover_packet, verbose=True)
    return dhcp_discover_packet


def sniff_dhcp_responses(timeout=3):

    print(f"Sniffing for DHCP responses on interface={INTERFACE} for {timeout}s...")

    def filter_dhcp(pkt):
        # We can filter on BOOTP or DHCP layer or check source port
        return pkt.haslayer(BOOTP) or pkt.haslayer(DHCP)

    packets = sniff(iface=INTERFACE, filter="udp and port 68",
                    timeout=timeout, lfilter=filter_dhcp)

    if packets:
        print(f"Received {len(packets)} packet(s).")
        for i, p in enumerate(packets, 1):
            p.show()  # Print the packet details
            print(f"--- Packet {i} end ---\n")
    else:
        # print("No DHCP responses sniffed.")
        print('\n')


def main():
    packet = build_dhcp_discover()
    # packet.show()  # 打印包的各层结构

    # Start a thread to sniff responses in parallel
    sniffer_thread = threading.Thread(target=sniff_dhcp_responses, args=(5,))
    sniffer_thread.start()

    # Send the packet
    print(f"Sending DHCP DISCOVER to {DHCP_SERVER_IP}:{DHCP_SERVER_PORT} via {INTERFACE}...")
    sendp(packet, iface=INTERFACE, verbose=False)
    print("Packet sent. ")

    # Wait for sniffing to complete
    sniffer_thread.join()
    print("Done.")


if __name__ == "__main__":
    main()

