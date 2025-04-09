#!/usr/bin/env python3
import asyncio
import ipaddress
import logging
import socket
import struct

import someip.header
from someip.config import Eventgroup, _T_SOCKNAME
from someip.sd import SOMEIPDatagramProtocol, ServiceDiscoveryProtocol

loggerdeb = logging.getLogger('SOME/IP')



logging.getLogger("someip.sd").setLevel(logging.WARNING)
logging.getLogger("someip.sd.announce").setLevel(logging.WARNING)


def enhex(buf, sep=" "):
    return sep.join("%02x" % b for b in buf)


class EventGroupReceiver(SOMEIPDatagramProtocol):
    def __init__(self):
        super().__init__(logger="notification")

    def message_received(
        self,
        someip_message: someip.header.SOMEIPHeader,
        addr: _T_SOCKNAME,
        multicast: bool,
    ) -> None:
        """
        called when a well-formed SOME/IP datagram was received
        """
        if someip_message.service_id == 0x010D:        
            pass
        if someip_message.service_id == 0x1126:
            print('DEBUG POINT: Response = '+ someip_message.payload.hex())


class SomeIPMiddleware:
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.subscribers = {}
        self.sock = None
        self.server_address = ('YOUR_SERVER_ADDRESS', YOUR_SERVER_PORT))  # 根据实际SOME/IP服务器地址修改

        self.local_addr = "YOUR_LOCAL_ADDRESS"
        self.multicast_addr = "YOUR_MULTICAST_ADDRESS"
        self.sd_port = YOUR_SD_PORT
        self.endpoint_port = YOUR_ENDPOINT_PORT
        self.subscribed_services = {}
        self.protocol = None
        self.evgrp_receiver = None
        self.periodic_tasks = {}
        self._session_id = 0  # 添加session_id计数器

    def _get_next_session_id(self):
        """获取下一个session ID并自增"""
        self._session_id = (self._session_id + 1) & 0xFFFF  # 保持在16位范围内
        return self._session_id

    async def initialize(self):
        """初始化UDP socket连接"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        #self.sock.bind((self.local_addr, self.endpoint_port))

        # 获取事件循环并保存引用
        self.loop = asyncio.get_event_loop()
        trsp_u, trsp_m, self.protocol = await ServiceDiscoveryProtocol.create_endpoints(
            family=socket.AF_INET,
            local_addr=self.local_addr,
            multicast_addr=self.multicast_addr,
            port=self.sd_port,
        )
        
        self.evgrp_receiver, _ = await EventGroupReceiver.create_unicast_endpoint(
            local_addr=(self.local_addr, self.endpoint_port)
        )
        
        self.protocol.start()
        
        # 启动后台任务
        asyncio.create_task(self._keep_alive())

    async def _keep_alive(self):
        while True:
            await asyncio.sleep(3600)
            # Optionally add heartbeat or maintenance tasks here

    async def subscribe_service(self, service_id):
        if service_id not in self.subscribed_services:
            self.protocol.discovery.find_subscribe_eventgroup(
                Eventgroup(
                    service_id=service_id,
                    instance_id=1,
                    major_version=1,
                    eventgroup_id=1,
                    sockname=self.evgrp_receiver.get_extra_info("sockname"),
                    protocol=someip.header.L4Protocols.UDP,
                )
            )
            self.subscribed_services[service_id] = True
            print(f"Subscribed to service 0x{service_id:04X}")

    async def unsubscribe_service(self, service_id):
        if service_id in self.subscribed_services:
            # Implement proper unsubscribe logic here
            del self.subscribed_services[service_id]
            print(f"Unsubscribed from service 0x{service_id:04X}")

    async def start_periodic_subscribe(self, service_id, interval):
        try:
            print("DEBUG POINT 1")  # 确认是否执行到此处
            if ...:
                print("DEBUG POINT 2")
        except Exception as e:
            print(f"Error in subscription: {e}")

        if service_id not in self.periodic_tasks:
            task = asyncio.create_task(self._periodic_subscribe(service_id, interval))
            self.periodic_tasks[service_id] = task

    async def _periodic_subscribe(self, service_id, interval):
        while True:
            await self.subscribe_service(service_id)
            await asyncio.sleep(interval)

    async def stop_periodic_subscribe(self, service_id):
        if service_id in self.periodic_tasks:
            task = self.periodic_tasks.pop(service_id)
            task.cancel()
            print(f"Stopped periodic subscription for service 0x{service_id:04X}")
    
    #test purpose no use in production
    async def maintest_periodic_subscribe(self, service_id, interval):
        """
        Start a periodic subscription task for the given service ID.
        :param service_id: The service ID to subscribe to.
        :param interval: The interval (in seconds) between subscription attempts.
        """
        while True:
            await self.subscribe_service(service_id)
            await asyncio.sleep(interval)

    def send_request(self, service_id, method_id, payload):
        """发送SOME/IP请求
        
        Args:
            service_id (int): 服务ID
            method_id (int): 方法ID
            payload (str): 16进制字符串格式的负载
            
        Returns:
            dict: 包含响应状态的字典
        """
        try:
            # 构建SOME/IP消息头
            message_id = (service_id << 16) | method_id
            protocol_version = 0x01
            client_id = 0x0000  # 客户端ID（可以根据需要修改）
            session_id = self._get_next_session_id()  # 获取下一个session ID
            interface_version = 0x01
            message_type = 0x00  # REQUEST
            return_code = 0x00
            
            # 将payload字符串转换为字节
            try:
                payload_bytes = bytes.fromhex(payload.replace('0x', '').replace(' ', ''))
            except ValueError:
                return {'status': 'error', 'message': 'Invalid payload format'}

            # 更新长度计算：header (12 bytes) + payload
            length = 8 + len(payload_bytes)  # length字段不包括service_id, method_id和length本身
            
            # 新的header打包结构：包含client_id和session_id
            header = struct.pack('!II2H4B',
                message_id,          # Service ID + Method ID (4 bytes)
                length,              # Length (2 bytes)
                client_id,           # Client ID (2 bytes)
                session_id,           # Session ID (2 bytes)
                protocol_version,    # Protocol version (1 byte)
                interface_version,   # Interface version (1 byte)
                message_type,        # Message type (1 byte)
                return_code       # Return code (1 byte)
            )
            print(f"DEBUG POINT 3: header={header.hex()}")  # 调试输出header的十六进制表示
            message = header + payload_bytes
            
            # 发送消息
            #self.sock.sendto(message, self.server_address)  #socket 方法无法使用49500端口
            
            # 使用事件组接收器发送消息
            # 这里假设self.evgrp_receiver是一个有效的socket对象
            self.evgrp_receiver.sendto(message, self.server_address)

            # 接收响应（这里简化处理，实际应该使用异步方式）
            try:
                self.evgrp_receiver.settimeout(2.0)  # 设置2秒超时
                response, _ = self.evgrp_receiver.recvfrom(4096)
                return {
                    'status': 'success',
                    'response': response.hex()
                }
            except socket.timeout:
                return {
                    'status': 'error',
                    'message': 'Response timeout'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }


def auto_int(s):
    return int(s, 0)


def setup_log(fmt="", **kwargs):
    try:
        import coloredlogs  # type: ignore[import]
        coloredlogs.install(fmt="%(asctime)s,%(msecs)03d " + fmt, **kwargs)
    except ModuleNotFoundError:
        logging.basicConfig(format="%(asctime)s " + fmt, **kwargs)
        logging.info("install coloredlogs for colored logs :-)")


def main():
    #setup_log(level=logging.DEBUG, fmt="%(levelname)-8s %(name)s: %(message)s")
    middleware = SomeIPMiddleware()

    try:
        asyncio.get_event_loop().run_until_complete(middleware.initialize())
        asyncio.get_event_loop().create_task(middleware.maintest_periodic_subscribe(0x010D, 5))  # Periodic subscription every 5 seconds
        asyncio.get_event_loop().run_forever()


    except KeyboardInterrupt:
        print("Program terminated by user")


if __name__ == "__main__":
    main()
