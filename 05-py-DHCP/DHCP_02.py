import socket
import struct
import time
import logging
import threading
from threading import Lock


class DHCPLease:
    """
    Represents an individual DHCP lease.

    Attributes:
        ip (str): The allocated IP address.
        start_time (float): The UNIX timestamp when the lease was obtained.
        lease_time (int): The lease duration in seconds.
    """
    def __init__(self, ip, start_time, lease_time):
        self.ip = ip
        self.start_time = start_time
        self.lease_time = lease_time

    def is_expired(self):
        return (time.time() - self.start_time) > self.lease_time


class DHCPServer:
    """
    A more advanced DHCP server implementation that handles IP address leasing,
    renewal, release, supports multiple DHCP options, and uses a dedicated
    DHCPLease class for better lease management. Thread-safe operations ensure
    concurrency safety for lease allocations and releases.
    """

    def __init__(
        self,
        subnet,
        subnet_mask,
        gateway,
        dns_servers,
        domain_name="",
        ntp_servers=None,
        lease_time=3600,
        cleanup_interval=60
    ):
        self.subnet = subnet
        self.subnet_mask = subnet_mask
        self.gateway = gateway
        self.dns_servers = dns_servers
        self.domain_name = domain_name
        self.ntp_servers = ntp_servers if ntp_servers else []
        self.leased_ips = {}  # { MAC: DHCPLease }
        self.lease_time = lease_time
        self.cleanup_interval = cleanup_interval
        self.available_ips = self._generate_available_ips()

        # A lock for thread-safe operations
        self.lock = Lock()

        # Configure logging correctly
        logging.info(
            f"DHCP Server initialized with subnet={self.subnet}, mask={self.subnet_mask}, "
            f"gateway={self.gateway}, DNS={self.dns_servers}"
        )

        # Start a background thread to periodically clean expired leases
        cleanup_thread = threading.Thread(target=self._clean_expired_leases, daemon=True)
        cleanup_thread.start()

    def _generate_available_ips(self):
        subnet_parts = list(map(int, self.subnet.split('.')))
        mask_parts = list(map(int, self.subnet_mask.split('.')))

        # Derive the network address
        network_parts = [subnet_parts[i] & mask_parts[i] for i in range(4)]
        network_address = '.'.join(map(str, network_parts))

        # Derive the broadcast address
        broadcast_parts = [subnet_parts[i] | (~mask_parts[i] & 255) for i in range(4)]
        broadcast_address = '.'.join(map(str, broadcast_parts))

        available_ips = []
        for i in range(1, 255):
            ip_parts = network_parts[:]
            ip_parts[3] = i
            ip = '.'.join(map(str, ip_parts))
            if ip != network_address and ip != broadcast_address:
                available_ips.append(ip)

        logging.info(f"Generated {len(available_ips)} available IPs in the subnet range.")
        return available_ips

    def _allocate_ip(self, client_mac):
        with self.lock:
            if client_mac in self.leased_ips:
                # Check if the existing lease is still valid
                if not self.leased_ips[client_mac].is_expired():
                    return self.leased_ips[client_mac].ip
                else:
                    self._release_ip(client_mac)

            if self.available_ips:
                ip = self.available_ips.pop(0)
                self.leased_ips[client_mac] = DHCPLease(ip, time.time(), self.lease_time)
                logging.info(f"Allocated IP {ip} to MAC {client_mac}")
                return ip

            logging.warning(f"No available IP to allocate for MAC {client_mac}")
            return None

    def _renew_lease(self, client_mac):
        with self.lock:
            if (client_mac in self.leased_ips) and (not self.leased_ips[client_mac].is_expired()):
                lease = self.leased_ips[client_mac]
                lease.start_time = time.time()  # Reset the lease start time
                logging.info(f"Renewed lease for MAC {client_mac}, IP remains {lease.ip}")
                return lease.ip
        return None

    def _release_ip(self, client_mac):
        if client_mac in self.leased_ips:
            released_ip = self.leased_ips[client_mac].ip
            self.available_ips.append(released_ip)
            del self.leased_ips[client_mac]
            logging.info(f"Released IP {released_ip} from MAC {client_mac}")

    def _clean_expired_leases(self):
        while True:
            time.sleep(self.cleanup_interval)
            with self.lock:
                expired_list = [
                    mac for mac, lease in self.leased_ips.items() if lease.is_expired()
                ]
                for mac in expired_list:
                    expired_ip = self.leased_ips[mac].ip
                    self.available_ips.append(expired_ip)
                    del self.leased_ips[mac]
                    logging.info(f"Cleaned up expired lease: IP {expired_ip} for MAC {mac}")

    def _build_dhcp_offer(self, client_mac, offered_ip):
        # DHCP magic cookie
        dhcp_magic_cookie = struct.pack('!I', 0x63825363)
        # DHCP message type -> Offer
        dhcp_message_type = struct.pack('!BB', 53, 2)

        # Options: subnet mask, gateway, DNS, lease time
        subnet_mask_opt = struct.pack('!BB', 1, 4) + socket.inet_aton(self.subnet_mask)
        router_opt = struct.pack('!BB', 3, 4) + socket.inet_aton(self.gateway)

        dns_opt = b''
        for dns in self.dns_servers:
            dns_opt += socket.inet_aton(dns)
        dns_opt = struct.pack('!BB', 6, len(dns_opt)) + dns_opt

        lease_time_opt = struct.pack('!BB', 51, 4) + struct.pack('!I', self.lease_time)

        # Option: domain name (if specified)
        domain_name_opt = b''
        if self.domain_name:
            domain_name_bytes = self.domain_name.encode('ascii')
            domain_name_opt = struct.pack('!BB', 15, len(domain_name_bytes)) + domain_name_bytes

        # Option: NTP servers (option code 42)
        ntp_opt = b''
        if self.ntp_servers:
            ntp_payload = b''
            for ntp_server in self.ntp_servers:
                ntp_payload += socket.inet_aton(ntp_server)
            ntp_opt = struct.pack('!BB', 42, len(ntp_payload)) + ntp_payload

        end_opt = struct.pack('!BB', 255, 0)

        dhcp_options = (
            dhcp_magic_cookie +
            dhcp_message_type +
            subnet_mask_opt +
            router_opt +
            dns_opt +
            lease_time_opt +
            domain_name_opt +
            ntp_opt +
            end_opt
        )

        # Base DHCP header
        dhcp_header = struct.pack(
            '!BBBBLHHLL6s16s64s128s',
            2,      # Message op code: BOOTREPLY
            1,      # Hardware type: Ethernet
            6,      # Hardware address length
            0,      # Hops
            0,      # Transaction ID
            0,      # Seconds elapsed
            0,      # Flags
            0,      # Client IP
            0,      # Your IP => next
            bytes.fromhex(client_mac.replace(':', '')),
            b'\x00' * 16,  # Server host name
            b'\x00' * 64,  # Boot file name
            b'\x00' * 128  # Vendor-specific area
        )

        dhcp_yiaddr = socket.inet_aton(offered_ip)

        dhcp_packet = dhcp_header + dhcp_yiaddr + b'\x00' * 12 + dhcp_options
        return dhcp_packet

    def _build_dhcp_ack(self, client_mac, assigned_ip):
        dhcp_magic_cookie = struct.pack('!I', 0x63825363)
        dhcp_message_type = struct.pack('!BB', 53, 5)

        subnet_mask_opt = struct.pack('!BB', 1, 4) + socket.inet_aton(self.subnet_mask)
        router_opt = struct.pack('!BB', 3, 4) + socket.inet_aton(self.gateway)
        dns_opt = b''
        for dns in self.dns_servers:
            dns_opt += socket.inet_aton(dns)
        dns_opt = struct.pack('!BB', 6, len(dns_opt)) + dns_opt
        lease_time_opt = struct.pack('!BB', 51, 4) + struct.pack('!I', self.lease_time)

        domain_name_opt = b''
        if self.domain_name:
            domain_name_bytes = self.domain_name.encode('ascii')
            domain_name_opt = struct.pack('!BB', 15, len(domain_name_bytes)) + domain_name_bytes

        ntp_opt = b''
        if self.ntp_servers:
            ntp_payload = b''
            for ntp_server in self.ntp_servers:
                ntp_payload += socket.inet_aton(ntp_server)
            ntp_opt = struct.pack('!BB', 42, len(ntp_payload)) + ntp_payload

        end_opt = struct.pack('!BB', 255, 0)

        dhcp_options = (
            dhcp_magic_cookie +
            dhcp_message_type +
            subnet_mask_opt +
            router_opt +
            dns_opt +
            lease_time_opt +
            domain_name_opt +
            ntp_opt +
            end_opt
        )

        dhcp_header = struct.pack(
            '!BBBBLHHLL6s16s64s128s',
            2,    # BOOTREPLY
            1,    # Ethernet
            6,    # Hardware address length
            0,    # Hops
            0,    # Transaction ID
            0,    # Seconds elapsed
            0,    # Flags
            0,    # Client IP
            0,    # Your IP => next
            bytes.fromhex(client_mac.replace(':', '')),
            b'\x00' * 16,
            b'\x00' * 64,
            b'\x00' * 128
        )

        dhcp_yiaddr = socket.inet_aton(assigned_ip)
        dhcp_packet = dhcp_header + dhcp_yiaddr + b'\x00' * 12 + dhcp_options
        return dhcp_packet

    def _handle_dhcp_discovery(self, client_mac):
        offered_ip = self._allocate_ip(client_mac)
        if offered_ip:
            return self._build_dhcp_offer(client_mac, offered_ip)
        return None

    def _handle_dhcp_request(self, client_mac):
        renewed_ip = self._renew_lease(client_mac)
        if renewed_ip:
            return self._build_dhcp_ack(client_mac, renewed_ip)

        assigned_ip = self._allocate_ip(client_mac)
        if assigned_ip:
            return self._build_dhcp_ack(client_mac, assigned_ip)
        return None

    def _handle_dhcp_release(self, client_mac):
        with self.lock:
            self._release_ip(client_mac)

    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        server_socket.bind(('', 1067))
        logging.info("DHCP Server is now listening on port 1067")
        logging.info("server_socket:", server_socket)

        while True:
            data, addr = server_socket.recvfrom(1024)
            logging.info(f"Received UDP packet from {addr}, length={len(data)}")
            client_ip, client_port = addr

            if len(data) > 242:
                dhcp_message_type = data[242]
                logging.info(f"DHCP message type = {dhcp_message_type}")
            else:
                logging.info("Data is too short to contain a DHCP message type at [242]")
                continue

            # DHCP message type often found at byte 242 (in minimal DHCP packets)
            dhcp_message_type = data[242]
            client_mac = ':'.join(f'{b:02x}' for b in data[28:34])

            if dhcp_message_type == 1:  # DHCPDISCOVER
                offer_packet = self._handle_dhcp_discovery(client_mac)
                if offer_packet:
                    server_socket.sendto(offer_packet, (client_ip, client_port))
                    logging.info(f"Sent DHCP OFFER to MAC {client_mac}")
            elif dhcp_message_type == 3:  # DHCPREQUEST
                ack_packet = self._handle_dhcp_request(client_mac)
                if ack_packet:
                    server_socket.sendto(ack_packet, ('255.255.255.255', 68))
                    logging.info(f"Sent DHCP ACK to MAC {client_mac}")
            elif dhcp_message_type == 7:  # DHCPRELEASE
                self._handle_dhcp_release(client_mac)
                logging.info(f"Received DHCP RELEASE from MAC {client_mac}")
            else:
                logging.warning(f"Received unsupported DHCP message type {dhcp_message_type} from {client_mac}")


if __name__ == "__main__":
    subnet = '192.168.1.0'
    subnet_mask = '255.255.255.0'
    gateway = '192.168.1.1'
    dns_servers = ['8.8.8.8', '8.8.4.4']
    domain_name = "example.local"
    ntp_servers = ['192.168.1.10']

    dhcp_server = DHCPServer(
        subnet=subnet,
        subnet_mask=subnet_mask,
        gateway=gateway,
        dns_servers=dns_servers,
        domain_name=domain_name,
        ntp_servers=ntp_servers,
        lease_time=3600,        # 1-hour lease
        cleanup_interval=60     # Check for expired leases every 60 seconds
    )
    dhcp_server.start()