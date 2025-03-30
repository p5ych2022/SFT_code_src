import psutil
import time

def get_network_speed(prev_bytes_sent, prev_bytes_recv):
    # 获取当前网络发送和接收的字节数
    current_bytes_sent = psutil.net_io_counters().bytes_sent
    current_bytes_recv = psutil.net_io_counters().bytes_recv
    # 计算 5 秒内的网络发送和接收速度
    sent_speed = (current_bytes_sent - prev_bytes_sent) / 5
    recv_speed = (current_bytes_recv - prev_bytes_recv) / 5
    return sent_speed, recv_speed, current_bytes_sent, current_bytes_recv

def monitor_system():
    # 初始化网络字节数
    prev_bytes_sent = psutil.net_io_counters().bytes_sent
    prev_bytes_recv = psutil.net_io_counters().bytes_recv

    while True:
        # 获取 CPU 使用率
        cpu_percent = psutil.cpu_percent(interval=1)

        # 获取内存使用率
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        # 获取磁盘使用率
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent

        # 获取网络速度
        sent_speed, recv_speed, prev_bytes_sent, prev_bytes_recv = get_network_speed(prev_bytes_sent, prev_bytes_recv)

        # 输出监控信息
        print(f"CPU 使用率: {cpu_percent}%")
        print(f"内存使用率: {memory_percent}%")
        print(f"磁盘使用率: {disk_percent}%")
        print(f"网络发送速度: {sent_speed:.2f} 字节/秒")
        print(f"网络接收速度: {recv_speed:.2f} 字节/秒")
        print("-" * 50)

        # 每隔 5 秒输出一次监控信息
        time.sleep(5)

if __name__ == "__main__":
    monitor_system()
