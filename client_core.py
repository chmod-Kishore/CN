"""
Client Core - Handles all networking for video, audio, screen sharing, chat, and files
"""

import asyncio
import socket
import threading
import struct
import time
import json
from typing import Callable, Optional
from queue import Queue, Empty

class ScalableCommClient:
    """Main client handling all communication with server"""
    
    def __init__(self, server_ip='127.0.0.1', tcp_port=9000, udp_port=9001):
        self.server_ip = server_ip
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        
        # Network connections
        self.tcp_reader: Optional[asyncio.StreamReader] = None
        self.tcp_writer: Optional[asyncio.StreamWriter] = None
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4194304)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4194304)
        
        # State
        self.connected = False
        self.client_id = None
        self.username = None
        
        # Callbacks for GUI updates
        self.on_video_frame: Optional[Callable] = None
        self.on_audio_chunk: Optional[Callable] = None
        self.on_screen_frame: Optional[Callable] = None
        self.on_chat_message: Optional[Callable] = None
        self.on_user_list: Optional[Callable] = None
        self.on_user_status: Optional[Callable] = None
        self.on_file_meta: Optional[Callable] = None
        
        # Streaming flags
        self.video_streaming = False
        self.audio_streaming = False
        self.screen_streaming = False
        
        # Threads
        self.tcp_thread = None
        self.udp_thread = None
        
        print("🔧 Client initialized")
    
    async def connect(self, username):
        """Connect to server"""
        self.username = username
        
        try:
            # TCP connection
            print(f"📡 Connecting to {self.server_ip}:{self.tcp_port}...")
            self.tcp_reader, self.tcp_writer = await asyncio.wait_for(
                asyncio.open_connection(self.server_ip, self.tcp_port),
                timeout=10.0
            )
            
            # Send username (handshake)
            self.tcp_writer.write(username.encode())
            await self.tcp_writer.drain()
            
            # Receive response
            length_data = await asyncio.wait_for(self.tcp_reader.readexactly(4), timeout=5.0)
            msg_length = struct.unpack('I', length_data)[0]
            data = await asyncio.wait_for(self.tcp_reader.readexactly(msg_length), timeout=5.0)
            
            response = data.decode()
            
            if response.startswith("CONNECTED:"):
                parts = response.split(":")
                self.client_id = parts[1]
                self.connected = True
                
                print(f"✅ Connected as {username} (ID: {self.client_id})")
                
                # Start receiving threads
                self.tcp_thread = threading.Thread(target=self.receive_tcp_loop, daemon=True)
                self.tcp_thread.start()
                
                self.udp_thread = threading.Thread(target=self.receive_udp_loop, daemon=True)
                self.udp_thread.start()
                
                return True
            else:
                print("❌ Connection failed: Invalid response")
                return False
        
        except asyncio.TimeoutError:
            print("❌ Connection timeout")
            return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def start_video(self, camera_index=0):
        """Start video streaming"""
        if not self.connected:
            print("❌ Not connected to server")
            return False
        
        if self.video_streaming:
            print("⚠️  Video already streaming")
            return False
        
        self.video_streaming = True
        threading.Thread(target=self._video_stream_loop, args=(camera_index,), daemon=True).start()
        self.send_control("VIDEO_ON")
        print("📹 Video streaming started")
        return True
    
    def stop_video(self):
        """Stop video streaming"""
        self.video_streaming = False
        self.send_control("VIDEO_OFF")
        print("📹 Video streaming stopped")
    
    def start_audio(self):
        """Start audio streaming"""
        if not self.connected:
            print("❌ Not connected to server")
            return False
        
        if self.audio_streaming:
            print("⚠️  Audio already streaming")
            return False
        
        self.audio_streaming = True
        threading.Thread(target=self._audio_stream_loop, daemon=True).start()
        self.send_control("AUDIO_ON")
        print("🎤 Audio streaming started")
        return True
    
    def stop_audio(self):
        """Stop audio streaming"""
        self.audio_streaming = False
        self.send_control("AUDIO_OFF")
        print("🎤 Audio streaming stopped")
    
    def start_screen_share(self):
        """Start screen sharing"""
        if not self.connected:
            print("❌ Not connected to server")
            return False
        
        if self.screen_streaming:
            print("⚠️  Screen already sharing")
            return False
        
        self.screen_streaming = True
        threading.Thread(target=self._screen_share_loop, daemon=True).start()
        self.send_control("SCREEN_ON")
        print("🖥️  Screen sharing started")
        return True
    
    def stop_screen_share(self):
        """Stop screen sharing"""
        self.screen_streaming = False
        self.send_control("SCREEN_OFF")
        print("🖥️  Screen sharing stopped")
    
    def _video_stream_loop(self, camera_index):
        """Video capture and streaming loop"""
        cap = None
        try:
            import cv2
            
            # Try to find working camera
            working_camera = None
            for idx in range(5):  # Try cameras 0-4
                test_cap = cv2.VideoCapture(idx)
                if test_cap.isOpened():
                    ret, _ = test_cap.read()
                    if ret:
                        working_camera = idx
                        test_cap.release()
                        print(f"✅ Found working camera at index {idx}")
                        break
                test_cap.release()
            
            if working_camera is None:
                print("❌ No working camera found!")
                self.video_streaming = False
                return
            
            # Open the working camera
            cap = cv2.VideoCapture(working_camera)
            
            # Set properties
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            
            # Verify it opened
            if not cap.isOpened():
                print("❌ Failed to open camera")
                self.video_streaming = False
                return
            
            print(f"📹 Video capture started (Camera {working_camera})")
            
            frame_count = 0
            while self.video_streaming and self.connected:
                ret, frame = cap.read()
                if not ret:
                    print("⚠️ Failed to read frame")
                    time.sleep(0.1)
                    continue
                
                frame_count += 1
                
                # **ADD THIS: Show local preview**
                if self.on_video_frame:
                    self.on_video_frame(self.username, frame.copy())
                
                # Compress frame
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
                success, encoded = cv2.imencode('.jpg', frame, encode_param)
                
                if success:
                    # Send via UDP
                    packet = self.create_udp_packet(1, encoded.tobytes())
                    if packet:
                        try:
                            self.udp_socket.sendto(packet, (self.server_ip, self.udp_port))
                        except Exception as e:
                            if frame_count % 100 == 0:
                                print(f"⚠️ UDP send error: {e}")
                
                # 30 FPS = ~33ms per frame
                time.sleep(0.033)

            '''while self.video_streaming and self.connected:
                ret, frame = cap.read()
                if not ret:
                    print("⚠️  Failed to read frame")
                    time.sleep(0.1)
                    continue
                
                frame_count += 1
                
                # Compress frame
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
                success, encoded = cv2.imencode('.jpg', frame, encode_param)
                
                if success:
                    # Send via UDP
                    packet = self.create_udp_packet(1, encoded.tobytes())
                    if packet:
                        try:
                            self.udp_socket.sendto(packet, (self.server_ip, self.udp_port))
                        except Exception as e:
                            if frame_count % 100 == 0:  # Print every 100 frames
                                print(f"⚠️  UDP send error: {e}")
                
                # 30 FPS = ~33ms per frame
                time.sleep(0.033)'''
            
            print(f"📹 Video capture stopped (sent {frame_count} frames)")
        
        except Exception as e:
            print(f"❌ Video error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.video_streaming = False
            if cap:
                cap.release()
    
    def _audio_stream_loop(self):
        """Audio capture and streaming loop"""
        try:
            import pyaudio
            
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024
            )
            
            print("🎤 Audio capture started")
            
            while self.audio_streaming and self.connected:
                audio_data = stream.read(1024, exception_on_overflow=False)
                
                # Send via UDP
                packet = self.create_udp_packet(2, audio_data)
                try:
                    self.udp_socket.sendto(packet, (self.server_ip, self.udp_port))
                except:
                    pass
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            print("🎤 Audio capture stopped")
        
        except Exception as e:
            print(f"❌ Audio error: {e}")
            self.audio_streaming = False
    
    def _screen_share_loop(self):
        """Screen capture and sharing loop"""
        try:
            import cv2
            import numpy as np
            from mss import mss
            
            sct = mss()
            monitor = sct.monitors[1]
            
            print("🖥️  Screen capture started")
            
            while self.screen_streaming and self.connected:
                # Capture screen
                screenshot = sct.grab(monitor)
                frame = np.array(screenshot)
                
                # Resize for efficiency
                frame = cv2.resize(frame, (1280, 720))
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                
                # Compress
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]
                success, encoded = cv2.imencode('.jpg', frame, encode_param)
                
                if success:
                    # Send via UDP
                    packet = self.create_udp_packet(3, encoded.tobytes())
                    try:
                        self.udp_socket.sendto(packet, (self.server_ip, self.udp_port))
                    except:
                        pass
                
                # 15 FPS for screen share
                time.sleep(0.066)
            
            print("🖥️  Screen capture stopped")
        
        except Exception as e:
            print(f"❌ Screen share error: {e}")
            self.screen_streaming = False
    
    def send_chat_message(self, message):
        """Send chat message via TCP"""
        if not self.connected:
            return False
        
        try:
            msg = f"CHAT:{message}"
            asyncio.run(self._send_tcp_data(msg.encode()))
            return True
        except Exception as e:
            print(f"❌ Chat send error: {e}")
            return False
    
    def send_control(self, control):
        """Send control message"""
        if not self.connected:
            return
        
        try:
            msg = f"CONTROL:{control}"
            asyncio.run(self._send_tcp_data(msg.encode()))
        except Exception as e:
            print(f"❌ Control send error: {e}")
    
    async def _send_tcp_data(self, data):
        """Send TCP data with length prefix"""
        try:
            length = struct.pack('I', len(data))
            self.tcp_writer.write(length + data)
            await self.tcp_writer.drain()
        except Exception as e:
            print(f"❌ TCP send error: {e}")
    
    def receive_tcp_loop(self):
        """Receive TCP messages"""
        print("📥 TCP receiver started")
        
        while self.connected:
            try:
                # Use the underlying socket for reading
                sock = self.tcp_reader._transport.get_extra_info('socket')
                sock.settimeout(1.0)  # 1 second timeout
                
                # Read length prefix
                length_data = b''
                while len(length_data) < 4 and self.connected:
                    try:
                        chunk = sock.recv(4 - len(length_data))
                        if not chunk:
                            self.connected = False
                            break
                        length_data += chunk
                    except socket.timeout:
                        continue
                    except Exception as e:
                        print(f"❌ Socket receive error: {e}")
                        self.connected = False
                        break
                
                if len(length_data) < 4:
                    break
                
                length = struct.unpack('I', length_data)[0]
                
                # Read message
                data = b''
                while len(data) < length and self.connected:
                    try:
                        chunk = sock.recv(min(length - len(data), 4096))
                        if not chunk:
                            self.connected = False
                            break
                        data += chunk
                    except socket.timeout:
                        continue
                    except Exception as e:
                        print(f"❌ Socket receive error: {e}")
                        self.connected = False
                        break
                
                if len(data) < length:
                    break
                
                message = data.decode('utf-8')
                
                # Process message
                self._process_tcp_message_sync(message)
                
            except Exception as e:
                if self.connected:
                    print(f"❌ TCP receive error: {e}")
                break
        
        print("📥 TCP receiver stopped")
    
    async def _receive_tcp_message(self):
        """Receive single TCP message"""
        try:
            # Read length prefix
            length_data = await asyncio.wait_for(
                self.tcp_reader.readexactly(4), 
                timeout=300.0
            )
            length = struct.unpack('I', length_data)[0]
            
            # Read message
            data = await asyncio.wait_for(
                self.tcp_reader.readexactly(length),
                timeout=30.0
            )
            message = data.decode('utf-8')
            
            # Process message
            await self._process_tcp_message(message)
        
        except asyncio.TimeoutError:
            pass
        except asyncio.IncompleteReadError:
            self.connected = False
        except Exception as e:
            print(f"❌ Message receive error: {e}")
    
    def _process_tcp_message_sync(self, message):
        """Process received TCP message (synchronous version)"""
        try:
            if message.startswith("CHAT:"):
                # Chat message: CHAT:username:message
                parts = message[5:].split(":", 1)
                if len(parts) == 2 and self.on_chat_message:
                    self.on_chat_message(parts[0], parts[1])
            
            elif message.startswith("USERS:"):
                # User list: USERS:[{user1}, {user2}, ...]
                users_json = message[6:]
                users = json.loads(users_json)
                if self.on_user_list:
                    self.on_user_list(users)
            
            elif message.startswith("STATUS:"):
                # User status change
                status_json = message[7:]
                status = json.loads(status_json)
                if self.on_user_status:
                    self.on_user_status(status)
            
            elif message.startswith("FILE_META:"):
                # File metadata
                parts = message[10:].split(":", 1)
                if len(parts) == 2 and self.on_file_meta:
                    self.on_file_meta(parts[0], parts[1])
            
            elif message == "PONG":
                # Heartbeat response
                pass
        
        except Exception as e:
            print(f"❌ Message processing error: {e}")
    
    async def _process_tcp_message(self, message):
        """Process received TCP message"""
        try:
            if message.startswith("CHAT:"):
                # Chat message: CHAT:username:message
                parts = message[5:].split(":", 1)
                if len(parts) == 2 and self.on_chat_message:
                    self.on_chat_message(parts[0], parts[1])
            
            elif message.startswith("USERS:"):
                # User list: USERS:[{user1}, {user2}, ...]
                users_json = message[6:]
                users = json.loads(users_json)
                if self.on_user_list:
                    self.on_user_list(users)
            
            elif message.startswith("STATUS:"):
                # User status change
                status_json = message[7:]
                status = json.loads(status_json)
                if self.on_user_status:
                    self.on_user_status(status)
            
            elif message.startswith("FILE_META:"):
                # File metadata
                parts = message[10:].split(":", 1)
                if len(parts) == 2 and self.on_file_meta:
                    self.on_file_meta(parts[0], parts[1])
            
            elif message == "PONG":
                # Heartbeat response
                pass
        
        except Exception as e:
            print(f"❌ Message processing error: {e}")
    
    def receive_udp_loop(self):
        """Receive UDP streams"""
        print("📥 UDP receiver started")
        
        while self.connected:
            try:
                data, addr = self.udp_socket.recvfrom(65536)
                
                if len(data) < 3:
                    continue
                
                # Parse packet: [type:1][sender_len:2][sender:var][payload:var]
                packet_type = data[0]
                sender_len = struct.unpack('H', data[1:3])[0]
                
                if len(data) < 3 + sender_len:
                    continue
                
                sender = data[3:3+sender_len].decode()
                payload = data[3+sender_len:]
                
                # Process based on type
                if packet_type == 1 and self.on_video_frame:
                    # Video frame
                    import cv2
                    import numpy as np
                    
                    frame_data = np.frombuffer(payload, dtype=np.uint8)
                    frame = cv2.imdecode(frame_data, cv2.IMREAD_COLOR)
                    
                    if frame is not None:
                        self.on_video_frame(sender, frame)
                
                elif packet_type == 2 and self.on_audio_chunk:
                    # Audio chunk
                    self.on_audio_chunk(sender, payload)
                
                elif packet_type == 3 and self.on_screen_frame:
                    # Screen share frame
                    import cv2
                    import numpy as np
                    
                    frame_data = np.frombuffer(payload, dtype=np.uint8)
                    frame = cv2.imdecode(frame_data, cv2.IMREAD_COLOR)
                    
                    if frame is not None:
                        self.on_screen_frame(sender, frame)
            
            except Exception as e:
                if self.connected:
                    print(f"❌ UDP receive error: {e}")
        
        print("📥 UDP receiver stopped")
    
    def create_udp_packet(self, packet_type, payload):
        """Create UDP packet with header"""
        if not self.client_id:
            return None
        
        client_id_bytes = self.client_id.encode()
        client_id_len = len(client_id_bytes)
        
        packet = bytes([packet_type]) + struct.pack('H', client_id_len)
        packet += client_id_bytes + payload
        
        return packet
    
    def disconnect(self):
        """Disconnect from server"""
        print("👋 Disconnecting...")
        
        self.connected = False
        self.video_streaming = False
        self.audio_streaming = False
        self.screen_streaming = False
        
        try:
            if self.tcp_writer:
                self.tcp_writer.close()
            self.udp_socket.close()
        except:
            pass
        
        print("✅ Disconnected")
    
    def __del__(self):
        """Cleanup on deletion"""
        self.disconnect()       