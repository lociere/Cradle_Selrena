"""AI核心主服务

启动Python AI核心服务，与TS内核通信
"""

import asyncio
import logging
import argparse
from typing import Optional

from .ai_service import AIService, SimpleAIService
from .event_bus_client import EventBusTransport

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AICoreService:
    """
    AI核心服务
    
    管理AI服务的启动、停止和运行
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 3000,
        transport: str = "http",
        simple_mode: bool = False
    ):
        """
        初始化AI核心服务
        
        Args:
            host: 事件总线主机地址
            port: 事件总线端口
            transport: 传输协议 (http/websocket/zeromq)
            simple_mode: 是否使用简化模式
        """
        self.host = host
        self.port = port
        self.transport = self._parse_transport(transport)
        self.simple_mode = simple_mode
        
        self.service: Optional[AIService] = None
        self.simple_service: Optional[SimpleAIService] = None
        
        # 信号处理
        self.shutdown_event = asyncio.Event()
    
    def _parse_transport(self, transport_str: str) -> EventBusTransport:
        """解析传输协议字符串"""
        transport_map = {
            "http": EventBusTransport.HTTP,
            "websocket": EventBusTransport.WEBSOCKET,
            "ws": EventBusTransport.WEBSOCKET,
            "zeromq": EventBusTransport.ZEROMQ,
            "zmq": EventBusTransport.ZEROMQ
        }
        
        transport = transport_map.get(transport_str.lower(), EventBusTransport.HTTP)
        logger.info(f"使用传输协议: {transport.value}")
        return transport
    
    async def start(self):
        """启动AI核心服务"""
        logger.info("正在启动AI核心服务...")
        logger.info(f"配置: host={self.host}, port={self.port}, transport={self.transport.value}")
        
        try:
            if self.simple_mode:
                # 使用简化模式
                logger.info("使用简化模式启动")
                self.simple_service = SimpleAIService(self.host, self.port)
                await self.simple_service.start()
                
                # 启动HTTP服务器用于接收消息
                await self._start_simple_http_server()
                
            else:
                # 使用完整模式
                logger.info("使用完整模式启动")
                self.service = AIService(
                    event_bus_host=self.host,
                    event_bus_port=self.port,
                    transport=self.transport
                )
                await self.service.start()
            
            logger.info("AI核心服务启动成功")
            logger.info("等待事件...")
            
            # 等待关闭信号
            await self.shutdown_event.wait()
            
        except KeyboardInterrupt:
            logger.info("收到中断信号")
        except Exception as e:
            logger.error(f"启动服务失败: {e}")
            raise
        finally:
            await self.stop()
    
    async def _start_simple_http_server(self):
        """启动简化的HTTP服务器"""
        try:
            from aiohttp import web
            
            app = web.Application()
            
            # 添加路由
            app.router.add_post('/message', self._handle_simple_message)
            app.router.add_get('/health', self._handle_health_check)
            
            # 启动服务器
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, 'localhost', 8000)
            await site.start()
            
            logger.info(f"简化HTTP服务器已启动: http://localhost:8000")
            
        except ImportError:
            logger.warning("aiohttp未安装，无法启动HTTP服务器")
            logger.info("简化模式将只处理通过事件总线发送的消息")
    
    async def _handle_simple_message(self, request):
        """处理简化模式的消息请求"""
        from aiohttp import web
        
        try:
            data = await request.json()
            user_id = data.get('user_id', 'default_user')
            message = data.get('message', '')
            
            if not message:
                return web.json_response({'error': '消息不能为空'}, status=400)
            
            # 处理消息
            response = await self.simple_service.process_message(user_id, message)
            
            return web.json_response({
                'response': response,
                'user_id': user_id
            })
            
        except Exception as e:
            logger.error(f"处理消息请求失败: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def _handle_health_check(self, request):
        """健康检查"""
        from aiohttp import web
        
        return web.json_response({
            'status': 'healthy',
            'service': 'python_ai_core',
            'mode': 'simple' if self.simple_mode else 'full'
        })
    
    async def stop(self):
        """停止AI核心服务"""
        logger.info("正在停止AI核心服务...")
        
        try:
            if self.service:
                await self.service.stop()
            elif self.simple_service:
                # 简化模式没有stop方法，直接记录日志
                logger.info("简化服务已停止")
            
            logger.info("AI核心服务已停止")
            
        except Exception as e:
            logger.error(f"停止服务失败: {e}")
    
    def signal_shutdown(self):
        """发送关闭信号"""
        self.shutdown_event.set()


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Cradle Selrena AI核心服务')
    parser.add_argument('--host', default='localhost', help='事件总线主机地址')
    parser.add_argument('--port', type=int, default=3000, help='事件总线端口')
    parser.add_argument('--transport', default='http', 
                       choices=['http', 'websocket', 'zeromq'],
                       help='传输协议')
    parser.add_argument('--simple', action='store_true',
                       help='使用简化模式（适合测试）')
    
    args = parser.parse_args()
    
    service = AICoreService(host=args.host, port=args.port, transport=args.transport, simple_mode=args.simple)
    await service.start()


if __name__ == "__main__":
    asyncio.run(main())
