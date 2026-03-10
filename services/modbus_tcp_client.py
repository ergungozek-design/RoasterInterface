import socket
import struct
import threading
import time


class ModbusTCPClient:
    """
    Modbus TCP (port 502)
    - read_holding_n(start_reg, qty) -> (values, err)
    - write_single_register(reg, value) -> (ok, err)
    Arayüz RTU client ile aynı.
    """

    def __init__(self, host="192.168.1.50", port=502, unit_id=1, timeout=1.5):
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.timeout = timeout

        self.sock = None
        self.lock = threading.Lock()
        self._tx_id = 1

    def connect(self):
        try:
            self.close()

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            return True

        except Exception:
            try:
                if self.sock:
                    self.sock.close()
            except Exception:
                pass

            self.sock = None
            return False


#    def connect_eski(self) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.connect((self.host, self.port))
            self.sock = s
            return True
        except Exception:
            self.sock = None
            return False

    def close(self):
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.sock = None

    def _ensure(self) -> bool:
        return self.sock is not None or self.connect()

    def _next_tid(self) -> int:
        self._tx_id = (self._tx_id + 1) & 0xFFFF
        if self._tx_id == 0:
            self._tx_id = 1
        return self._tx_id

    def _recv_exact(self, n: int) -> bytes:
        buf = bytearray()
        t0 = time.time()
        while len(buf) < n and (time.time() - t0) < self.timeout:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                break
            buf += chunk
        return bytes(buf)

    def _send_pdu(self, pdu: bytes):
        """
        MBAP:
        - TID (2)
        - PID (2) = 0
        - LEN (2) = unit_id + pdu length
        - UID (1)
        + PDU
        """
        tid = self._next_tid()
        length = 1 + len(pdu)
        mbap = struct.pack(">HHHB", tid, 0, length, self.unit_id)
        adu = mbap + pdu

        self.sock.sendall(adu)

        # Response MBAP header is 7 bytes
        hdr = self._recv_exact(7)
        if len(hdr) != 7:
            return None, "short mbap"

        r_tid, r_pid, r_len, r_uid = struct.unpack(">HHHB", hdr)
        if r_tid != tid:
            return None, "tid mismatch"
        if r_pid != 0:
            return None, "pid mismatch"
        if r_uid != self.unit_id:
            return None, "unit mismatch"

        # Remaining bytes in ADU = r_len - 1 (unit already consumed)
        rest_len = r_len - 1
        rest = self._recv_exact(rest_len)
        if len(rest) != rest_len:
            return None, f"short pdu {len(rest)}/{rest_len}"

        return rest, None

    def read_holding_n(self, start_reg: int, qty: int):
        if qty <= 0 or qty > 125:
            return None, "qty out of range"

        with self.lock:
            if not self._ensure():
                return None, "connect failed"

            # PDU: [FC=0x03][startHi][startLo][qtyHi][qtyLo]
            pdu = struct.pack(">BHH", 0x03, start_reg, qty)

            try:
                rpdu, err = self._send_pdu(pdu)
            except Exception as e:
                self.close()
                return None, f"tcp: {e}"

            if rpdu is None:
                return None, err

            fc = rpdu[0]
            if fc & 0x80:
                ex = rpdu[1] if len(rpdu) > 1 else 0
                return None, f"exception 0x{ex:02X}"

            if fc != 0x03:
                return None, "bad response"

            if len(rpdu) < 2:
                return None, "short response"

            bytecount = rpdu[1]
            if bytecount != 2 * qty:
                return None, "bytecount mismatch"

            data = rpdu[2:2 + bytecount]
            if len(data) != bytecount:
                return None, "short data"

            values = []
            for i in range(qty):
                hi = data[2 * i]
                lo = data[2 * i + 1]
                values.append((hi << 8) | lo)

            return values, None

    def write_single_register(self, reg: int, value: int):
        value &= 0xFFFF

        with self.lock:
            if not self._ensure():
                return False, "connect failed"

            # PDU: [FC=0x06][regHi][regLo][valHi][valLo]
            pdu = struct.pack(">BHH", 0x06, reg, value)

            try:
                rpdu, err = self._send_pdu(pdu)
            except Exception as e:
                self.close()
                return False, f"tcp: {e}"

            if rpdu is None:
                return False, err

            fc = rpdu[0]
            if fc & 0x80:
                ex = rpdu[1] if len(rpdu) > 1 else 0
                return False, f"exception 0x{ex:02X}"

            if fc != 0x06:
                return False, "bad response"

            # Normal FC06 response echoes address+value (5 bytes total)
            if len(rpdu) < 5:
                return False, "short response"

            return True, None

    def write_single_coil(self, coil_addr: int, value: bool):
        """
        FC05 - Write Single Coil
        coil_addr: 0-based coil address (M50 -> 50 gibi)
        value: True/False
        returns: (ok:bool, err:str|None)
        """
        try:
            # MBAP header: Transaction(2) Protocol(2)=0 Length(2) UnitID(1)
            # PDU: FC(1)=0x05 + Addr(2) + Value(2) (0xFF00 / 0x0000)
            tx_id = getattr(self, "_tx_id", 1)
            self._tx_id = (tx_id + 1) & 0xFFFF

            unit = int(getattr(self, "unit_id", 1))
            fc = 0x05
            addr = int(coil_addr) & 0xFFFF
            val = 0xFF00 if bool(value) else 0x0000

            pdu = struct.pack(">BHH", fc, addr, val)
            mbap = struct.pack(">HHHB", tx_id, 0, len(pdu) + 1, unit)
            req = mbap + pdu

            self.sock.sendall(req)

            # Response: same as request PDU (FC + Addr + Value)
            resp = self.sock.recv(12)  # MBAP(7) + PDU(5)
            if not resp or len(resp) < 12:
                return False, "No/short response"

            # Basic exception check
            r_fc = resp[7]
            if r_fc & 0x80:
                ex = resp[8] if len(resp) > 8 else 0
                return False, f"Modbus exception {ex}"

            return True, None

        except Exception as e:
            return False, str(e)

def read_coils(self, start_coil, qty):
    """
    Modbus TCP - Read Coils (FC01)
    start_coil : coil address (0-based)
    qty        : number of coils
    return     : (list[0/1], err)
    """
    try:
        # ---- MBAP HEADER ----
        self._tid = (self._tid + 1) & 0xFFFF
        tid = self._tid

        # Transaction ID, Protocol ID, Length, Unit ID
        mbap = struct.pack(">HHHB", tid, 0, 6, self.unit_id)

        # ---- PDU ----
        pdu = struct.pack(">BHH", 0x01, start_coil, qty)

        frame = mbap + pdu
        self.sock.send(frame)

        # ---- RESPONSE HEADER ----
        hdr = self._recv_all(7)
        r_tid, _, length, _ = struct.unpack(">HHHB", hdr)

        if r_tid != tid:
            return None, "TID mismatch"

        body = self._recv_all(length - 1)

        func = body[0]
        if func & 0x80:
            return None, f"Exception {body[1]}"

        byte_count = body[1]
        data = body[2:2 + byte_count]

        coils = []
        for i in range(qty):
            byte_i = i // 8
            bit_i = i % 8
            coils.append((data[byte_i] >> bit_i) & 0x01)

        return coils, None

    except Exception as e:
        return None, str(e)


