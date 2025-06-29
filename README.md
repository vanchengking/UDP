-----

# 计算机网络课程实习

[cite\_start]**姓名：** 高范铖 [cite: 1, 200]
[cite\_start]**学号：** 230203205 [cite: 1, 200]
[cite\_start]**班级：** 计算机23-3 [cite: 1, 200]
[cite\_start]**指导教师：** 齐建东 [cite: 1, 200]

-----

## 项目概述

[cite\_start]本项目包含两个基于Python Socket编程的网络课程实习任务，在 **PyCharm 2024.1.4** 环境下开发完成 [cite: 2, 201]。

  * **Task 1** 实现了一个多线程的TCP服务器，能够接收客户端发送的文本文件，分块进行字符串反转并返回结果。
  * **Task 2** 在UDP之上实现了一个可靠数据传输协议，模拟了TCP的三次握手、四次挥手、Go-Back-N滑动窗口、累积确认以及动态超时重传等机制。

## Git 仓库地址

[cite\_start][https://github.com/vanchengking/TCP.git](https://github.com/vanchengking/TCP.git) [cite: 12, 214]

-----

## 1\. 运行环境与依赖

  * **操作系统**: `[请在此处填写您的操作系统，如: Windows 11]`
  * **Python 版本**: `[请在此处填写您的Python版本, 通过在终端输入 python --version 获取]`
  * **需要安装的库**: `pandas` (仅Task2的客户端需要)
      * 安装命令:
        ```bash
        pip install pandas
        ```

-----
## 2\. Task 2: 可靠UDP传输协议 (GBN)

### 文件列表

  * `udpserver.py`
  * `udpclient.py`

### 运行指南

#### ① 启动服务器

在终端中运行以下命令，服务器将启动并监听在 **12000** 端口，等待客户端发起连接。

```bash
python udpserver.py
```

#### ② 启动客户端

在另一个终端中运行以下命令。客户端需要3个命令行参数。

```bash
python udpclient.py <服务器IP> <服务器端口> <包数量>
```

  * `<服务器IP>`: 服务器所在的IP地址。如果在同一台机器上测试，请使用 `127.0.0.1`。
  * `<服务器端口>`: 服务器监听的端口号，应为 `12000`。
  * `<包数量>`: 希望客户端发送并获得确认的数据包总数。

#### ③ 运行示例

```bash
python udpclient.py 127.0.0.1 12000 30
```