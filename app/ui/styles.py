"""Touch-friendly stylesheet for 10.1\" landscape kiosk (system fonts)."""

APP_STYLESHEET = """
QWidget {
    background-color: #111827;
    color: #F9FAFB;
    font-family: "DejaVu Sans", "Noto Sans", "Liberation Sans", sans-serif;
    font-size: 18px;
}
QPushButton {
    background-color: #2563EB;
    color: white;
    border: none;
    border-radius: 12px;
    padding: 16px 24px;
    font-size: 20px;
    font-weight: 600;
    min-height: 56px;
}
QPushButton:disabled {
    background-color: #374151;
    color: #9CA3AF;
}
QPushButton#secondary {
    background-color: #374151;
}
QPushButton#danger {
    background-color: #DC2626;
}
QPushButton#success {
    background-color: #059669;
}
QLabel#title {
    font-size: 36px;
    font-weight: 700;
}
QLabel#subtitle {
    font-size: 22px;
    color: #D1D5DB;
}
QLabel#price {
    font-size: 24px;
    font-weight: 700;
    color: #34D399;
}
QFrame#card {
    background-color: #1F2937;
    border-radius: 16px;
    border: 1px solid #374151;
}
QScrollArea {
    border: none;
}
"""
