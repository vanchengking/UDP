
import socket
import threading
import random
import struct

TYPE_SYN = 0
TYPE_SYN_ACK = 1
TYPE_ACK = 2
TYPE_DATA = 3
TYPE_DATA_ACK = 4
TYPE_FIN = 5
TYPE_FIN_ACK = 6

PACKET_LOSS_RATE = 0.3


def handle_client_session(client_ip, client_port, initial_packet):
    # 为当前会话创建一个专用的新套接字
    session_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # 绑定到 0 号端口，让操作系统自动选择一个可用的临时端口
    session_socket.bind(('0.0.0.0', 0))
    print(f"[{client_ip}:{client_port}] 新会话线程启动，使用端口 {session_socket.getsockname()[1]}。")

    # --- 模拟三次握手 ---
    print(f"[{client_ip}:{client_port}] 开始三次握手...")
    # Step1. 服务器处理已收到的初始 SYN
    # 直接从传入的 initial_packet 中解包，获取客户端的ISN
    client_isn, _, _ = struct.unpack('!III', initial_packet)
    print(f"[{client_ip}:{client_port}] 已收到初始 [SYN, SEQ={client_isn}]。")

    # Step2. 服务器发送 SYN-ACK
    # 服务器也随机生成自己的初始序列号 ISN
    server_isn = random.randint(20000, 30000)
    # 确认号 ACK 必须是收到的 客户端序列号 + 1
    ack_num_for_client = client_isn + 1
    # 构造 SYN-ACK 包：(序列号 = 自己的ISN 确认号 = 客户端 ISN + 1, 类型 = SYN-ACK)
    syn_ack_header = struct.pack('!III', server_isn, ack_num_for_client, TYPE_SYN_ACK)
    # 将 SYN-ACK 发送给客户端
    session_socket.sendto(syn_ack_header, (client_ip, client_port))
    print(f"[{client_ip}:{client_port}] 已发送 [ SYN-ACK SEQ={server_isn} ACK={ack_num_for_client}]。")

    # Step3. 服务器等待客户端的最终 ACK
    session_socket.settimeout(2.0)
    try:
        ack_packet, _ = session_socket.recvfrom(1024)
        # 解包 ACK，获取其确认号
        seq_num, ack_num, packet_type = struct.unpack('!III', ack_packet)
        # 验证 ACK 是否正确：类型必须是 ACK ，确认号必须是服务器 ISN + 1
        if packet_type == TYPE_ACK and ack_num == server_isn + 1:
            print(f"[ {client_ip}:{client_port}] 收到 [ACK, ACK = {ack_num} ]，连接建立成功。")
        else:
            print(f"[{client_ip}:{client_port}] 握手失败：未收到最终或不正确的 ACK。")
            session_socket.close()
            return
    except socket.timeout:
        print(f"[{client_ip}:{client_port}] 等待 ACK 握手超时。")
        session_socket.close()
        return

    # --- 数据接收与挥手处理 ---
    expected_seq_num = 0  # 初始化期望收到的数据序列号为0
    session_socket.settimeout(10.0)  # 设置一个较长的超时，防止客户端掉线导致线程永久阻塞

    while True:
        try:
            message, addr = session_socket.recvfrom(2048)
            if random.random() < PACKET_LOSS_RATE:
                print(f"[{addr}] !!! 模拟丢包，丢弃收到的数据包。")
                continue

            seq_num, _, packet_type = struct.unpack('!III', message[:12])

            if packet_type == TYPE_DATA:
                print(f"[{addr}] 收到 [ DATA, SEQ = {seq_num}]，期望 SEQ = {expected_seq_num}。")
                if seq_num == expected_seq_num:
                    ack_num_for_data = expected_seq_num
                    # 构造DATA-ACK：(序列号 = 无用, 确认号 = 已收到的数据 SEQ , 类型 = DATA-ACK)
                    ack_header = struct.pack('!III', 0, ack_num_for_data, TYPE_DATA_ACK)
                    session_socket.sendto(ack_header, addr)
                    print(f"[{addr}] 已按序接收，发送 [DATA-ACK, ACK={ack_num_for_data}]。")
                    expected_seq_num += 1
                else:  # 如果是乱序包 ( GBN 核心)
                    # 重新发送上一个成功确认的 ACK
                    last_ack_num = expected_seq_num - 1
                    if last_ack_num >= 0:
                        ack_header = struct.pack('!III', 0, last_ack_num, TYPE_DATA_ACK)
                        session_socket.sendto(ack_header, addr)
                        print(f"[{addr}] 收到乱序包，丢弃。重发 [DATA-ACK, ACK={last_ack_num}]。")

            elif packet_type == TYPE_FIN:  # 如果收到 FIN 请求
                print(f"[{addr}] 收到客户端的 [FIN, SEQ={seq_num}] 请求。")
                server_fsn = random.randint(40000, 50000)  # 服务器可以有自己的 FIN 序列号
                ack_num_for_fin = seq_num + 1  # 确认号是收到的 FIN 序列号 + 1
                # 构造 FIN-ACK 并发送
                fin_ack_header = struct.pack('!III', server_fsn, ack_num_for_fin, TYPE_FIN_ACK)
                session_socket.sendto(fin_ack_header, addr)
                print(f"[{addr}] 发送 [FIN-ACK, SEQ={server_fsn}, ACK={ack_num_for_fin}]，准备关闭会话。")
                break  # 跳出循环，结束此会话线程

        except socket.timeout:
            print(f"[{client_ip}:{client_port}] 会话超时，异常终止。")
            break
        except Exception as e:
            print(f"[{client_ip}:{client_port}] 发生错误: {e}")
            break

    session_socket.close()
    print(f"[{client_ip}:{client_port}] 会话线程已结束并关闭套接字。")


def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_port = 12000
    server_socket.bind(('0.0.0.0', server_port))
    print(f"UDP 服务器主线程已启动，正在端口 {server_port} 上监听初始请求...")
    active_clients = set()

    while True:
        packet, client_addr = server_socket.recvfrom(1024)
        try:
            _, _, packet_type = struct.unpack('!III', packet)
            # 检查是否是SYN包，并且来自一个新的客户端
            if packet_type == TYPE_SYN and client_addr not in active_clients:
                active_clients.add(client_addr)
                # 为该客户端创建一个新的线程来处理完整的会话
                # 将收到的第一个SYN包(packet)也一并传给线程函数
                client_thread = threading.Thread(target=handle_client_session,
                                                 args=(client_addr[0], client_addr[1], packet))
                client_thread.daemon = True
                client_thread.start()
        except struct.error:
            print(f"从 {client_addr} 收到格式错误的包，已忽略。")


if __name__ == '__main__':
    main()
