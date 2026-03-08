import time
import threading
import serial
from serial.serialutil import SerialException


# ---------------- MODBUS CRC ----------------
def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def append_crc(frame: bytes) -> bytes:
    c = crc16_modbus(frame)
    return frame + bytes([c & 0xFF, (c >> 8) & 0xFF])


# ---------------- MODBUS CLIENT ----------------
class ModbusClient:
    def __init__(self, port="COM5", baud=9600, slave=2, timeout=1.5):
        self.port = port
        self.baud = baud
        self.slave = slave
        self.timeout = timeout
        self.ser = None
        self.lock = threading.Lock()

    def connect(self) -> bool:
        try:
            self.ser = serial.Serial(
                self.port, self.baud,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=self.timeout
            )
            time.sleep(0.08)
            return True
        except SerialException:
            self.ser = None
            return False

    def close(self):
        try:
            if self.ser:
                self.ser.close()
        except Exception:
            pass
        self.ser = None

    def _ensure(self) -> bool:
        return (self.ser is not None and self.ser.is_open) or self.connect()

    def _read_exact(self, n: int) -> bytes:
        """Read until n bytes or until timeout budget is consumed."""
        if not self.ser:
            return b""
        buf = bytearray()
        t0 = time.time()
        while len(buf) < n and (time.time() - t0) < self.timeout:
            chunk = self.ser.read(n - len(buf))
            if chunk:
                buf += chunk
            else:
                time.sleep(0.01)
        return bytes(buf)

    def read_holding_n(self, start_reg: int, qty: int):
        if qty <= 0 or qty > 125:
            return None, "qty out of range"

        with self.lock:
            if not self._ensure():
                return None, "connect failed"

            req = bytes([
                self.slave, 0x03,
                (start_reg >> 8) & 0xFF, start_reg & 0xFF,
                (qty >> 8) & 0xFF, qty & 0xFF
            ])
            req = append_crc(req)

            expected_len = 5 + 2 * qty  # addr,fc,bytecount,data...,crc

            try:
                self.ser.reset_input_buffer()
                self.ser.write(req)
                time.sleep(0.01)
                resp = self._read_exact(expected_len)
            except SerialException as e:
                self.close()
                return None, f"serial: {e}"

            if len(resp) != expected_len:
                return None, f"short read {len(resp)}/{expected_len}"

            recv_crc = resp[-2] | (resp[-1] << 8)
            calc_crc = crc16_modbus(resp[:-2])
            if recv_crc != calc_crc:
                return None, "crc error"

            if resp[0] != self.slave:
                return None, "slave mismatch"

            if resp[1] & 0x80:
                return None, f"exception 0x{resp[2]:02X}"

            if resp[1] != 0x03:
                return None, "bad response"

            bytecount = resp[2]
            if bytecount != 2 * qty:
                return None, "bytecount mismatch"

            data = resp[3:3 + bytecount]
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

            req = bytes([
                self.slave, 0x06,
                (reg >> 8) & 0xFF, reg & 0xFF,
                (value >> 8) & 0xFF, value & 0xFF
            ])
            req = append_crc(req)

            try:
                self.ser.reset_input_buffer()
                self.ser.write(req)
                time.sleep(0.01)
                resp = self._read_exact(8)
            except SerialException as e:
                self.close()
                return False, f"serial: {e}"

            if len(resp) != 8:
                return False, f"short read {len(resp)}/8"

            recv_crc = resp[-2] | (resp[-1] << 8)
            calc_crc = crc16_modbus(resp[:-2])
            if recv_crc != calc_crc:
                return False, "crc error"

            if resp[0] != self.slave:
                return False, "slave mismatch"

            if resp[1] & 0x80:
                return False, f"exception 0x{resp[2]:02X}"

            if resp[1] != 0x06:
                return False, "bad response"

            return True, None
