import logging
import socket
import struct
import time
class DHCPServer:
    def __init__(self, subnet, subnet_mask, gateway, dns_servers):
        self.subnet = subnet
        self.subnet_mask = subnet_mask
        self.gateway = gateway
        self.dns_servers = dns_servers
        self.leased_ips = {}
        self.available_ips = self._generate_available_ips()

    def _generate_available_ips(self):
        subnet_parts = list(map(int, self.subnet.split('.')))
        mask_parts = list(map(int, self.subnet_mask.split('.')))
        network_parts = [subnet_parts[i] & mask_parts[i] for i in range(4)]
        network_address = '.'.join(map(str, network_parts))
        broadcast_parts = [subnet_parts[i] | (~mask_parts[i] & 255) for i in range(4)]
        broadcast_address = '.'.join(map(str, broadcast_parts))

        available_ips = []
        for i in range(1, 255):
            ip_parts = network_parts[:]
            ip_parts[3] = i
            ip = '.'.join(map(str, ip_parts))
            if ip != network_address and ip != broadcast_address:
                available_ips.append(ip)
        return available_ips

    def _allocate_ip(self, client_mac):
        if client_mac in self.leased_ips:
            return self.leased_ips[client_mac]['ip']
        if self.available_ips:
            ip = self.available_ips.pop(0)
            lease_time = 3600
            self.leased_ips[client_mac] = {
                'ip': ip,
                'start_time': time.time(),
                'lease_time': lease_time
            }
            return ip
        return None

    def _renew_lease(self, client_mac):
        if client_mac in self.leased_ips:
            self.leased_ips[client_mac]['start_time'] = time.time()
            return self.leased_ips[client_mac]['ip']
        return None

    def _release_ip(self, client_mac):
        if client_mac in self.leased_ips:
            ip = self.leased_ips[client_mac]['ip']
            self.available_ips.append(ip)
            del self.leased_ips[client_mac]

    def _is_lease_expired(self, client_mac):
        if client_mac in self.leased_ips:
            lease_info = self.leased_ips[client_mac]
            elapsed_time = time.time() - lease_info['start_time']
            return elapsed_time > lease_info['lease_time']
        return True

    def _build_dhcp_offer(self, client_mac, offered_ip):
        dhcp_magic_cookie = struct.pack('!I', 0x63825363)
        dhcp_message_type = struct.pack('!BB', 53, 2)
        subnet_mask = struct.pack('!BB', 1, 4) + socket.inet_aton(self.subnet_mask)
        router = struct.pack('!BB', 3, 4) + socket.inet_aton(self.gateway)
        dns = struct.pack('!BB', 6, 4) + socket.inet_aton(self.dns_servers[0])
        lease_time = struct.pack('!BB', 51, 4) + struct.pack('!I', 3600)

        dhcp_options = dhcp_magic_cookie + dhcp_message_type + subnet_mask + router + dns + lease_time
        dhcp_options += struct.pack('!BB', 255, 0)

        dhcp_header = struct.pack('!BBBBLHHLL6s16s64s128s',
                                  2, 1, 6, 0, 0, 0, 0, 0, 0,
                                  bytes.fromhex(client_mac.replace(':', '')),
                                  b'\x00' * 16,
                                  b'\x00' * 64,
                                  b'\x00' * 128)
        dhcp_yiaddr = socket.inet_aton(offered_ip)
        dhcp_packet = dhcp_header + dhcp_yiaddr + b'\x00' * 12 + dhcp_options
        return dhcp_packet

    def _build_dhcp_ack(self, client_mac, assigned_ip):
        dhcp_magic_cookie = struct.pack('!I', 0x63825363)
        dhcp_message_type = struct.pack('!BB', 53, 5)
        subnet_mask = struct.pack('!BB', 1, 4) + socket.inet_aton(self.subnet_mask)
        router = struct.pack('!BB', 3, 4) + socket.inet_aton(self.gateway)
        dns = struct.pack('!BB', 6, 4) + socket.inet_aton(self.dns_servers[0])
        lease_time = struct.pack('!BB', 51, 4) + struct.pack('!I', 3600)

        dhcp_options = dhcp_magic_cookie + dhcp_message_type + subnet_mask + router + dns + lease_time
        dhcp_options += struct.pack('!BB', 255, 0)

        dhcp_header = struct.pack('!BBBBLHHLL6s16s64s128s',
                                  2, 1, 6, 0, 0, 0, 0, 0, 0,
                                  bytes.fromhex(client_mac.replace(':', '')),
                                  b'\x00' * 16,
                                  b'\x00' * 64,
                                  b'\x00' * 128)
        dhcp_yiaddr = socket.inet_aton(assigned_ip)
        dhcp_packet = dhcp_header + dhcp_yiaddr + b'\x00' * 12 + dhcp_options
        return dhcp_packet

    def _handle_dhcp_discovery(self, client_mac):
        offered_ip = self._allocate_ip(client_mac)
        if offered_ip:
            dhcp_offer = self._build_dhcp_offer(client_mac, offered_ip)
            return dhcp_offer
        return None

    def _handle_dhcp_request(self, client_mac):
        if self._is_lease_expired(client_mac):
            assigned_ip = self._allocate_ip(client_mac)
        else:
            assigned_ip = self._renew_lease(client_mac)
        if assigned_ip:
            dhcp_ack = self._build_dhcp_ack(client_mac, assigned_ip)
            return dhcp_ack
        return None

    def _handle_dhcp_release(self, client_mac):
        self._release_ip(client_mac)

    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        server_socket.bind(('', 1067))
        print("Server is running and bound to port 1067")

        while True:
            data, addr = server_socket.recvfrom(1024)
            dhcp_message_type = data[242]
            client_mac = ':'.join([f'{b:02x}' for b in data[28:34]])

            if dhcp_message_type == 1:
                dhcp_offer = self._handle_dhcp_discovery(client_mac)
                if dhcp_offer:
                    server_socket.sendto(dhcp_offer, ('255.255.255.255', 68))
            elif dhcp_message_type == 3:
                dhcp_ack = self._handle_dhcp_request(client_mac)
                if dhcp_ack:
                    server_socket.sendto(dhcp_ack, ('255.255.255.255', 68))
            elif dhcp_message_type == 7:
                self._handle_dhcp_release(client_mac)


if __name__ == "__main__":
    subnet = '192.168.1.0'
    subnet_mask = '255.255.255.0'
    gateway = '192.168.1.1'
    dns_servers = ['8.8.8.8']

    dhcp_server = DHCPServer(subnet, subnet_mask, gateway, dns_servers)
    dhcp_server.start()

