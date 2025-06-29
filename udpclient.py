
import socket
import struct
import time
import sys
import pandas as pd
import random  # 用于生成随机的初始序列号 (Initial Sequence Number, ISN)

# 定义报文类型常量，提高代码可读性
TYPE_SYN = 0  # 连接请求
TYPE_SYN_ACK = 1  # 对连接请求的确认
TYPE_ACK = 2  # 通用确认(可用于握手或挥手)
TYPE_DATA = 3  # 数据包
TYPE_DATA_ACK = 4  # 对数据的确认
TYPE_FIN = 5  # 连接关闭请求
TYPE_FIN_ACK = 6  # 对关闭请求的确认


if len(sys.argv) != 4: 
    print("用法:  python udpclient.py <服务器IP> <服务器端口> <包数量>")
    sys.exit(1)
SERVER_IP, SERVER_PORT, TOTAL_PACKETS = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])

client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

client_socket.settimeout(1.0)
print("--- 开始三次握手 ---")

# Step1. 客户端发送 SYN
# 随机生成一个初始序列号 ISN
client_isn = random.randint(0, 10000)
# 使用 struct.pack 将报文头部打包成二进制。格式为 '!III' (网络字节序, 3个无符号整数)
# 我自定义的报文内容:  (序列号 = client_isn 确认号 = 0 类型 = SYN)
syn_header = struct.pack('!III', client_isn, 0, TYPE_SYN)
# 服务器的主监听地址
server_addr = (SERVER_IP, SERVER_PORT)
# 将 SYN 包发送到服务器
client_socket.sendto(syn_header, server_addr)
print(f"发送 [SYN, SEQ = {client_isn}]...")

try: 
    # Step2. 客户端等待接收服务器的 SYN-ACK
    # recvfrom() 接收数据并返回(数据, 发送方地址)
    syn_ack_packet, server_session_addr = client_socket.recvfrom(1024)
    # 解包 SYN-ACK，获取服务器的 序列号 server_isn 确认号 ack_num 类型
    server_isn, ack_num, packet_type = struct.unpack('!III', syn_ack_packet)
    if packet_type == TYPE_SYN_ACK and ack_num == client_isn + 1:   # 验证收到的包是否正确
        print(f"收到 [ SYN-ACK SEQ = {server_isn} ACK = {ack_num} ] from {server_session_addr}")
        # Step3. 客户端发送最终的 ACK
        # 构造 ACK 包: (序列号 = 自己的下一个序列号 确认号 = 服务器序列号 + 1 类型 = ACK)
        ack_header = struct.pack('!III', client_isn + 1, server_isn + 1, TYPE_ACK)
        # 将 ACK 发送到服务器为此次会话创建的新地址
        client_socket.sendto(ack_header, server_session_addr)
        print(f"发送 [ACK, ACK = {server_isn + 1}]，连接建立完成。\n")
        # 更新服务器地址为新的会话地址，后续所有通信都将发往此地址
        server_addr = server_session_addr
    else: 
        print("握手失败: 收到的 SYN-ACK 不正确")
        client_socket.close()
        sys.exit(1)
except socket.timeout: 
    # 如果等待 SYN-ACK 超时，打印错误并退出
    print("握手超时，服务器无响应")
    client_socket.close()
    sys.exit(1)

# --- 数据传输与 GBN 逻辑 --- 
print("--- 开始数据传输 ---")
WINDOW_SIZE = 5  # 滑动窗口大小
base = 0  # 窗口的起始，即最早未被确认的包的序列号
next_seq_num = 0  # 下一个要发送的新包的序列号
packets_sent_total = 0  # 总发送计数器(含重传)
retransmissions = 0  # 重传计数器
RTT_list = []  # 存储所有 RTT 样本
send_times = {}  # 字典:  记录每个包的发送时间戳

# 动态超时计算 EWMA 的相关参数
alpha = 0.125
beta = 0.25
estimated_RTT = -1.0  # 估算 RTT
dev_RTT = 0.0  # RTT偏差
timeout_interval = 0.5  # 初始超时时间

# 预生成所有要发送的数据
datas = {i:  ('D' * 80).encode('utf-8') for i in range(TOTAL_PACKETS)}

# 当 base 小于总包数时，说明还有数据未被确认
while base < TOTAL_PACKETS: 
    # 只要窗口未满，就持续发送数据包
    while next_seq_num < base + WINDOW_SIZE and next_seq_num < TOTAL_PACKETS: 
        # 数据包的序列号 SEQ 就是其编号，确认号 ACK 字段在此处无用，设为0
        header = struct.pack('!III', next_seq_num, 0, TYPE_DATA)
        packet = header + datas[next_seq_num]
        client_socket.sendto(packet, server_addr)
        print(f"已发送 [DATA, SEQ = {next_seq_num}]")
        send_times[next_seq_num] = time.time()  # 记录发送时间
        packets_sent_total += 1
        next_seq_num += 1

    try: 
        # 设置动态的超时时间来等待 ACK
        client_socket.settimeout(timeout_interval)
        # 接收服务器的 DATA-ACK
        ack_packet, _ = client_socket.recvfrom(2048)
        # 解包，主要关注确认号 ack_num
        _, ack_num, packet_type = struct.unpack('!III', ack_packet)

        # 检查 ACK 是否有效
        if packet_type == TYPE_DATA_ACK and ack_num >= base: 
            print(f"收到 [DATA-ACK, ACK = {ack_num}]")
            # --- 更新RTT和超时时间 ---
            RTT_sample = time.time() - send_times[ack_num]
            if estimated_RTT < 0:   # 第一个样本
                estimated_RTT = RTT_sample
                dev_RTT = RTT_sample / 2
            else:   # EWMA 公式更新
                estimated_RTT = (1 - alpha) * estimated_RTT + alpha * RTT_sample
                dev_RTT = (1 - beta) * dev_RTT + beta * abs(RTT_sample - estimated_RTT)
            timeout_interval = estimated_RTT + 4 * dev_RTT
            timeout_interval = max(0.1, min(timeout_interval, 2.0))  # 限制上下限

            RTT_list.append(RTT_sample * 1000)
            # 移动窗口的 base ，因为是累积确认，收到 ack_num 表示之前的都收到了
            base = ack_num + 1

    except socket.timeout: 
        # 如果超时，说明从 base 开始的包可能丢失
        print(f"!!! 超时！重传窗口起始于 SEQ = {base}")
        retransmissions += (next_seq_num - base)
        # 这样子的话就执行 Go-Back-N: 将 next_seq_num 拉回到 base，准备重传整个窗口
        next_seq_num = base

print(f"\n所有 {TOTAL_PACKETS} 个数据包已确认。")

# --- 模拟四次挥手 ---
print("\n--- 开始四次挥手 ---")
# Step1. 客户端发送 FIN
# FIN 的序列号 SEQ 可以沿用数据传输的最后一个序列号
client_fsn = base
fin_header = struct.pack('!III', client_fsn, 0, TYPE_FIN)
client_socket.sendto(fin_header, server_addr)
print(f"发送 [ FIN, SEQ = {client_fsn} ]...")

try: 
    # Step2. 客户端等待服务器的 FIN-ACK
    client_socket.settimeout(2.0)
    fin_ack_packet, _ = client_socket.recvfrom(1024)
    # 解包服务器的 FIN-ACK ，获取其序列号和确认号
    server_fsn, ack_num, packet_type = struct.unpack('!III', fin_ack_packet)
    # 验证 FIN-ACK 的确认号是否正确
    if packet_type == TYPE_FIN_ACK and ack_num == client_fsn + 1: 
        print(f"收到 [ FIN-ACK SEQ = {server_fsn} ACK = {ack_num} ]。客户端关闭。")
    else: 
        print("未收到预期的 [ FIN-ACK ]，但仍关闭连接。")
except socket.timeout: 
    print("等待 [ FIN-ACK ] 超时，客户端强制关闭。")

client_socket.close()

if RTT_list: 
    RTT_series = pd.Series(RTT_list)
    loss_rate = (retransmissions / packets_sent_total) * 100 if packets_sent_total > 0 else 0
    print("\n--- 传输统计报告 ---")
    print(f"总发送包数(含重传):  {packets_sent_total}")
    print(f"重传包数:  {retransmissions}")
    print(f"丢包率:  {loss_rate: .2f}%")
    print(f"最小 RTT:  {RTT_series.min(): .2f} ms")
    print(f"最大 RTT:  {RTT_series.max(): .2f} ms")
    print(f"平均 RTT:  {RTT_series.mean(): .2f} ms")
    print(f"RTT 标准差:  {RTT_series.std(): .2f} ms")