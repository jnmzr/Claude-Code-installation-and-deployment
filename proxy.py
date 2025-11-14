#!/usr/bin/env python3
"""
Professional HTTP/HTTPS Proxy Server
For network proxy applications like Claude Code
Supports long-term running as Windows service
"""

import http.server
import socketserver
import urllib.request
import urllib.error
from http.server import SimpleHTTPRequestHandler
import sys
import logging
import threading
import time
import signal
from logging.handlers import RotatingFileHandler
from datetime import datetime
import os

# ==================== Configuration Section ====================

# Proxy configuration
PROXY_HOST = '0.0.0.0'
PROXY_PORT = 8118

# Log configuration
LOG_DIR = os.path.expanduser('~')
LOG_FILE = os.path.join(LOG_DIR, 'proxy_server.log')
LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# Timeout configuration
CONNECT_TIMEOUT = 10  # Connection timeout (seconds)
DATA_TIMEOUT = 30     # Data transfer timeout (seconds)
IDLE_TIMEOUT = 60     # Idle timeout (seconds)

# Performance configuration
MAX_REQUEST_SIZE = 100 * 1024 * 1024  # 100MB
BUFFER_SIZE = 8192

# ==================== Logging System ====================

def setup_logger():
    """Configure logging system"""
    logger = logging.getLogger('ProxyServer')
    logger.setLevel(logging.INFO)

    # Clear existing handlers
    logger.handlers.clear()

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler (rotating logs)
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=LOG_MAX_SIZE,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Cannot create log file {LOG_FILE}: {e}")

    # Console handler (for debugging only)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

logger = setup_logger()

# ==================== Statistics System ====================

class ProxyStats:
    """Proxy statistics"""

    def __init__(self):
        self.lock = threading.Lock()
        self.start_time = time.time()
        self.total_requests = 0
        self.total_bytes_sent = 0
        self.total_bytes_received = 0
        self.active_connections = 0
        self.errors = 0

    def request_started(self):
        """Request started"""
        with self.lock:
            self.total_requests += 1
            self.active_connections += 1

    def request_finished(self):
        """Request finished"""
        with self.lock:
            self.active_connections -= 1

    def add_bytes(self, sent=0, received=0):
        """Add traffic statistics"""
        with self.lock:
            self.total_bytes_sent += sent
            self.total_bytes_received += received

    def add_error(self):
        """Add error count"""
        with self.lock:
            self.errors += 1

    def get_stats(self):
        """Get statistics"""
        with self.lock:
            uptime = time.time() - self.start_time
            return {
                'uptime': uptime,
                'uptime_str': self._format_time(uptime),
                'total_requests': self.total_requests,
                'active_connections': self.active_connections,
                'total_bytes_sent': self.total_bytes_sent,
                'total_bytes_received': self.total_bytes_received,
                'errors': self.errors,
                'requests_per_minute': self.total_requests / (uptime / 60) if uptime > 0 else 0
            }

    @staticmethod
    def _format_time(seconds):
        """Format time duration"""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if days > 0:
            return f"{days}d {hours}h {minutes}m {secs}s"
        elif hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

stats = ProxyStats()

# ==================== Proxy Handler ====================

class ProxyHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Professional HTTP/HTTPS Proxy Handler"""

    protocol_version = 'HTTP/1.1'

    def do_GET(self):
        """Handle GET requests"""
        self.proxy_request()

    def do_POST(self):
        """Handle POST requests"""
        self.proxy_request()

    def do_PUT(self):
        """Handle PUT requests"""
        self.proxy_request()

    def do_DELETE(self):
        """Handle DELETE requests"""
        self.proxy_request()

    def do_HEAD(self):
        """Handle HEAD requests"""
        self.proxy_request()

    def do_OPTIONS(self):
        """Handle OPTIONS requests"""
        self.proxy_request()

    def do_CONNECT(self):
        """Handle HTTPS CONNECT requests"""
        stats.request_started()

        try:
            self._handle_connect()
        except Exception as e:
            logger.error(f"CONNECT error: {e}", exc_info=True)
            stats.add_error()
            try:
                self.send_error(500, f"Proxy error: {str(e)}")
            except:
                pass
        finally:
            stats.request_finished()

    def _handle_connect(self):
        """Handle CONNECT tunneling"""
        import socket

        # Parse target address
        try:
            host, port = self.path.split(':')
            port = int(port)
        except ValueError:
            self.send_error(400, "Invalid CONNECT request")
            return

        # Connect to target server
        try:
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_socket.settimeout(CONNECT_TIMEOUT)
            target_socket.connect((host, port))
            target_socket.settimeout(DATA_TIMEOUT)
        except socket.timeout:
            self.send_error(504, f"Connection to {host}:{port} timed out")
            return
        except socket.error as e:
            self.send_error(502, f"Cannot connect to {host}:{port}: {e}")
            return

        # Send connection success response
        try:
            self.send_response(200, 'Connection established')
            self.end_headers()
        except:
            target_socket.close()
            return

        # Bidirectional data forwarding
        self._tunnel_data(self.connection, target_socket)

    def _tunnel_data(self, client_sock, target_sock):
        """Use threads for bidirectional data forwarding"""

        def forward(source, destination, direction):
            """Unidirectional data forwarding"""
            total_bytes = 0
            try:
                while True:
                    try:
                        source.settimeout(IDLE_TIMEOUT)
                        data = source.recv(BUFFER_SIZE)
                        if not data:
                            break

                        destination.sendall(data)
                        total_bytes += len(data)

                        # Update statistics
                        if direction == 'client_to_server':
                            stats.add_bytes(sent=len(data))
                        else:
                            stats.add_bytes(received=len(data))

                    except socket.timeout:
                        break
                    except socket.error:
                        break
            except Exception as e:
                logger.debug(f"Forwarding error ({direction}): {e}")
            finally:
                try:
                    source.shutdown(socket.SHUT_RD)
                except:
                    pass
                try:
                    destination.shutdown(socket.SHUT_WR)
                except:
                    pass

        # Create two threads for bidirectional forwarding
        client_to_server = threading.Thread(
            target=forward,
            args=(client_sock, target_sock, 'client_to_server'),
            daemon=True
        )
        server_to_client = threading.Thread(
            target=forward,
            args=(target_sock, client_sock, 'server_to_client'),
            daemon=True
        )

        client_to_server.start()
        server_to_client.start()

        # Wait for both directions to complete
        client_to_server.join(timeout=DATA_TIMEOUT)
        server_to_client.join(timeout=DATA_TIMEOUT)

        # Close connections
        try:
            target_sock.close()
        except:
            pass
        try:
            client_sock.close()
        except:
            pass

    def proxy_request(self):
        """Forward HTTP requests"""
        stats.request_started()

        try:
            self._handle_proxy_request()
        except Exception as e:
            logger.error(f"Proxy request error: {e}", exc_info=True)
            stats.add_error()
            try:
                self.send_error(500, f"Proxy error: {str(e)}")
            except:
                pass
        finally:
            stats.request_finished()

    def _handle_proxy_request(self):
        """Actual logic for handling proxy requests"""
        # Read request body (if any)
        content_length = self.headers.get('Content-Length')
        body = None

        if content_length:
            try:
                length = int(content_length)
                if length > MAX_REQUEST_SIZE:
                    self.send_error(413, "Request body too large")
                    return
                body = self.rfile.read(length)
                stats.add_bytes(sent=length)
            except ValueError:
                self.send_error(400, "Invalid Content-Length")
                return

        # Create request
        try:
            req = urllib.request.Request(
                self.path,
                data=body,
                headers=dict(self.headers),
                method=self.command
            )
        except Exception as e:
            self.send_error(400, f"Invalid request: {e}")
            return

        # Send request
        try:
            with urllib.request.urlopen(req, timeout=DATA_TIMEOUT) as response:
                # Send response status
                self.send_response(response.status)

                # Send response headers
                for header, value in response.headers.items():
                    if header.lower() not in ['connection', 'keep-alive', 'proxy-connection', 'transfer-encoding']:
                        self.send_header(header, value)
                self.end_headers()

                # Send response body
                response_data = response.read()
                self.wfile.write(response_data)
                stats.add_bytes(received=len(response_data))

        except urllib.error.HTTPError as e:
            self.send_error(e.code, str(e))
            stats.add_error()
        except urllib.error.URLError as e:
            self.send_error(502, f"Cannot access target: {e}")
            stats.add_error()
        except socket.timeout:
            self.send_error(504, "Request timeout")
            stats.add_error()

    def log_message(self, format, *args):
        """Log messages"""
        logger.info(f"{self.address_string()} - {format % args}")

    def log_error(self, format, *args):
        """Error logging"""
        logger.error(f"{self.address_string()} - {format % args}")

# ==================== Server ====================

class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Multi-threaded HTTP server"""

    # Allow address reuse
    allow_reuse_address = True

    # Set reasonable thread limit
    daemon_threads = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = True

# ==================== Statistics Reporting Thread ====================

class StatsReporter(threading.Thread):
    """Thread for periodic statistics reporting"""

    def __init__(self, interval=300):  # Default 5 minutes
        super().__init__(daemon=True)
        self.interval = interval
        self.running = True

    def run(self):
        """Run statistics reporting"""
        while self.running:
            time.sleep(self.interval)
            if self.running:
                self._report_stats()

    def _report_stats(self):
        """Report statistics"""
        info = stats.get_stats()
        logger.info("=" * 60)
        logger.info("Proxy Server Statistics:")
        logger.info(f"  Uptime: {info['uptime_str']}")
        logger.info(f"  Total Requests: {info['total_requests']}")
        logger.info(f"  Active Connections: {info['active_connections']}")
        logger.info(f"  Sent Traffic: {self._format_bytes(info['total_bytes_sent'])}")
        logger.info(f"  Received Traffic: {self._format_bytes(info['total_bytes_received'])}")
        logger.info(f"  Error Count: {info['errors']}")
        logger.info(f"  Request Rate: {info['requests_per_minute']:.2f} requests/minute")
        logger.info("=" * 60)

    @staticmethod
    def _format_bytes(bytes_count):
        """Format byte count"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.2f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.2f} PB"

    def stop(self):
        """Stop reporting"""
        self.running = False

# ==================== Main Program ====================

def signal_handler(signum, frame):
    """Signal handler"""
    logger.info(f"Received signal {signum}, preparing to shutdown server...")
    sys.exit(0)

def run_proxy(host=PROXY_HOST, port=PROXY_PORT):
    """Run proxy server"""

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create server
    try:
        httpd = ThreadedHTTPServer((host, port), ProxyHTTPRequestHandler)
    except OSError as e:
        logger.error(f"Cannot start server: {e}")
        sys.exit(1)

    # Start statistics reporting thread
    stats_reporter = StatsReporter(interval=300)  # Report every 5 minutes
    stats_reporter.start()

    logger.info("=" * 60)
    logger.info("Proxy Server Started")
    logger.info(f"Listening Address: {host}:{port}")
    logger.info(f"Log File: {LOG_FILE}")
    logger.info(f"Process PID: {os.getpid()}")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Usage:")
    logger.info("  Set environment variables on other machines:")
    logger.info(f'  export http_proxy="http://your_computer_ip:{port}"')
    logger.info(f'  export https_proxy="http://your_computer_ip:{port}"')
    logger.info("")
    logger.info("Press Ctrl+C to stop server")
    logger.info("=" * 60)

    # Run server
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("\n\nReceived interrupt signal")
    finally:
        # Cleanup resources
        logger.info("Shutting down server...")
        stats_reporter.stop()
        httpd.shutdown()
        httpd.server_close()

        # Print final statistics
        stats_reporter._report_stats()

        logger.info("Server stopped")

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Professional HTTP/HTTPS Proxy Server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Start with default configuration
  %(prog)s --port 8080              # Specify port
  %(prog)s --host 192.168.1.100     # Specify listening address
  %(prog)s --log-file proxy.log     # Specify log file
        """
    )

    parser.add_argument('--port', type=int, default=PROXY_PORT,
                        help=f'Listening port (default: {PROXY_PORT})')
    parser.add_argument('--host', default=PROXY_HOST,
                        help=f'Listening address (default: {PROXY_HOST})')
    parser.add_argument('--log-file', default=LOG_FILE,
                        help=f'Log file path (default: {LOG_FILE})')
    parser.add_argument('--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Log level (default: INFO)')

    args = parser.parse_args()

    # Update configuration
    PROXY_PORT = args.port
    PROXY_HOST = args.host
    LOG_FILE = args.log_file

    # Re-setup logger
    logger = setup_logger()
    logger.setLevel(getattr(logging, args.log_level))

    # Start server
    run_proxy(host=args.host, port=args.port)