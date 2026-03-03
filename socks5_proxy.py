import socket, threading, struct, sys

def handle_socks5(conn):
    try:
        # Handshake
        conn.recv(262)
        conn.sendall(b"\x05\x00")
        
        # Request
        data = conn.recv(4)
        if not data: return
        mode, addr_type = data[1], data[3]
        
        if addr_type == 1: # IPv4
            addr = socket.inet_ntoa(conn.recv(4))
        elif addr_type == 3: # Domain
            length = conn.recv(1)[0]
            addr = conn.recv(length).decode()
        elif addr_type == 4: # IPv6
            addr = socket.inet_ntop(socket.AF_INET6, conn.recv(16))
        else:
            return
            
        port = struct.unpack(">H", conn.recv(2))[0]
        
        # Connect (CONNECT mode only)
        if mode == 1:
            try:
                # Python creates dual-stack connection automatically
                remote = socket.create_connection((addr, port), timeout=10)
                conn.sendall(b"\x05\x00\x00\x01" + socket.inet_aton("0.0.0.0") + struct.pack(">H", 0))
            except:
                conn.sendall(b"\x05\x01\x00\x01" + socket.inet_aton("0.0.0.0") + struct.pack(">H", 0))
                return
            
            # Bidirectional pipe
            def pipe(src, dst):
                try:
                    while True:
                        d = src.recv(4096)
                        if not d: break
                        dst.sendall(d)
                except: pass
                finally:
                    src.close(); dst.close()
            
            threading.Thread(target=pipe, args=(conn, remote), daemon=True).start()
            threading.Thread(target=pipe, args=(remote, conn), daemon=True).start()
    except: pass

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", 18797))
    s.listen(100)
    print("SOCKS5 Proxy (Telegram Bridge) listening on 127.0.0.1:18797")
    while True:
        conn, _ = s.accept()
        threading.Thread(target=handle_socks5, args=(conn,), daemon=True).start()

if __name__ == "__main__":
    main()
