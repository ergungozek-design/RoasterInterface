# RoasterInterface

**RoasterInterface** is a Python-based graphical interface developed for controlling and monitoring a coffee roasting machine connected to a PLC system.

The application communicates with the PLC via **Modbus protocol** and provides a modern UI built with **Kivy** for real-time roasting control, profile management, and data visualization.

---

## Features

* Live roasting dashboard
* Real-time temperature monitoring
* Roast profile creation and editing
* PLC communication via Modbus
* Bean roasting animation
* Exhaust and flame control interface
* Profile execution and stage tracking
* Modern UI built with Kivy

---

## Screens

The application contains multiple screens designed for different stages of the roasting process:

* **Home Screen** – Main navigation interface
* **Live Roast Screen** – Real-time roasting dashboard
* **Manual Control Screen** – Manual control of roasting parameters
* **Make Profile Screen** – Create new roasting profiles
* **Profile Screen** – View saved profiles
* **Profile Detail Screen** – Edit and send profiles to PLC
* **History Screen** – Review past roasting sessions

---

## Project Structure

```
RoasterInterface
│
├── screens
│   ├── home_screen.py
│   ├── live_roast_screen.py
│   ├── manual_control_screen.py
│   ├── profile_screen.py
│   └── profile_detail_screen.py
│
├── widgets
│   ├── bean_roast_anim.py
│   ├── roast_plot.py
│   └── status_anim.py
│
├── services
│   ├── modbus_tcp_client.py
│   ├── numeric_keypad.py
│   └── text_keypad.py
│
├── ui
│   ├── live_roast.kv
│   └── manual_control.kv
│
├── assets
│
├── profiles
│
├── main.py
└── README.md
```

---

## Requirements

* Python 3.10+
* Kivy
* pymodbus
* numpy

Install dependencies:

```
pip install -r requirements.txt
```

---

## Running the Application

Run the application using:

```
python main.py
```

---

## PLC Communication

The interface communicates with the PLC using **Modbus registers**.

Typical usage includes:

* Reading temperature values
* Writing control parameters
* Sending roast profiles to the PLC
* Monitoring roasting stages

---

## Author

Ergün Gözek
Giritli Elektrik

---

## License

This project is intended for educational and industrial experimentation purposes.
