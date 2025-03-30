import psutil
import time
import csv
import os

# 日志文件名，可根据需要自行修改
LOG_FILE = "system_monitor_log.csv"


def init_csv_log():
    # 初始化 CSV 文件（如果不存在），并写入表头
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            # CSV 表头，可根据实际需求增删字段
            writer.writerow(["Timestamp", "CPU%", "Memory%", "Disk%", "NetSent(B/s)", "NetRecv(B/s)"])


def get_network_speed(prev_bytes_sent, prev_bytes_recv):
    # 获取当前网络发送和接收的字节数
    current_bytes_sent = psutil.net_io_counters().bytes_sent
    current_bytes_recv = psutil.net_io_counters().bytes_recv

    # 计算 5 秒内的网络发送和接收速度
    interval = 5  # 与监控循环的 time.sleep(5) 一致
    sent_speed = (current_bytes_sent - prev_bytes_sent) / interval
    recv_speed = (current_bytes_recv - prev_bytes_recv) / interval

    return sent_speed, recv_speed, current_bytes_sent, current_bytes_recv


def write_to_csv(timestamp, cpu_percent, memory_percent, disk_percent, sent_speed, recv_speed):
    # 将监控数据写入 CSV 文件
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, cpu_percent, memory_percent, disk_percent, sent_speed, recv_speed])


def monitor_system():
    # 初始化网络字节数
    prev_bytes_sent = psutil.net_io_counters().bytes_sent
    prev_bytes_recv = psutil.net_io_counters().bytes_recv

    # 初始化日志文件
    init_csv_log()

    while True:
        # 获取当前时间戳
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        # 获取 CPU 使用率（interval=1 使 cpu_percent 等待1秒采样）
        cpu_percent = psutil.cpu_percent(interval=1)

        # 获取内存使用率
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        # 获取磁盘使用率
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent

        # 获取网络速度
        sent_speed, recv_speed, prev_bytes_sent, prev_bytes_recv = get_network_speed(prev_bytes_sent, prev_bytes_recv)

        # 输出到控制台
        print(f"[{current_time}] CPU: {cpu_percent:.2f}% | Mem: {memory_percent:.2f}% | "
              f"Disk: {disk_percent:.2f}% | NetSent: {sent_speed:.2f} B/s | NetRecv: {recv_speed:.2f} B/s")

        # 如果 CPU 超过阈值，简单打印提示，可进一步扩展为邮件/短信等通知
        if cpu_percent > 80:
            print("[警告] CPU 使用率超过 80%！")

        # 记录到 CSV 文件
        write_to_csv(current_time, cpu_percent, memory_percent, disk_percent, sent_speed, recv_speed)

        # 每隔 5 秒输出一次监控信息
        time.sleep(5)


if __name__ == "__main__":
    monitor_system()