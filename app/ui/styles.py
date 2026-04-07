APP_STYLESHEET = """
* {
    font-family: "Segoe UI", "Inter", "Arial", sans-serif;
}

QWidget#appRoot {
    background: #0B1120;
    color: #E5E7EB;
}

QFrame#sidebar {
    background: #070B14;
    border-right: 1px solid #1F2937;
}

QLabel#sidebarTitle {
    color: #F8FAFC;
    font-size: 30px;
    font-weight: 700;
    letter-spacing: 0.5px;
}

QLabel#sidebarSubtitle,
QLabel#sidebarVersion,
QLabel#mutedLabel {
    color: #64748B;
    font-size: 12px;
}

QPushButton#navButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 12px;
    color: #CBD5E1;
    font-size: 14px;
    font-weight: 600;
    padding: 12px 14px;
    text-align: left;
}

QPushButton#navButton:hover {
    background: #111827;
    color: #F8FAFC;
}

QPushButton#navButton:checked {
    background: #1D4ED8;
    color: #FFFFFF;
}

QFrame#contentFrame {
    background: #0B1120;
}

QFrame#heroPanel,
QFrame#catalogPanel,
QFrame#infoPanel,
QDialog#toolDialog {
    background: #111827;
    border: 1px solid #1F2937;
    border-radius: 22px;
}

QLabel#heroTitle {
    color: #F8FAFC;
    font-size: 28px;
    font-weight: 750;
}

QLabel#heroDescription,
QLabel#panelBody,
QLabel#catalogSubtitle,
QLabel#toolDescription {
    color: #94A3B8;
    font-size: 14px;
    line-height: 1.4;
}

QLabel#heroMeta {
    color: #60A5FA;
    font-size: 13px;
    font-weight: 650;
}

QLabel#catalogTitle,
QLabel#panelTitle,
QLabel#dialogTitle {
    color: #F8FAFC;
    font-size: 20px;
    font-weight: 700;
}

QLineEdit#toolSearch {
    background: #0F172A;
    border: 1px solid #253044;
    border-radius: 14px;
    color: #F8FAFC;
    font-size: 14px;
    padding: 12px 14px;
    selection-background-color: #2563EB;
}

QLineEdit#toolSearch:focus {
    border-color: #3B82F6;
}

QScrollArea#toolScroll {
    background: transparent;
    border: none;
}

QWidget#toolGridViewport {
    background: transparent;
}

QFrame#toolCard {
    background: #0F172A;
    border: 1px solid #253044;
    border-radius: 18px;
}

QFrame#toolCard:hover {
    border-color: #3B82F6;
    background: #111D35;
}

QLabel#toolName {
    color: #F8FAFC;
    font-size: 17px;
    font-weight: 700;
}

QLabel#toolCategory {
    background: #172554;
    border-radius: 10px;
    color: #93C5FD;
    font-size: 11px;
    font-weight: 700;
    padding: 5px 9px;
}

QLabel#toolTags {
    color: #64748B;
    font-size: 12px;
}

QLabel#emptyState {
    color: #94A3B8;
    font-size: 14px;
    padding: 24px;
}

QPushButton#primaryButton {
    background: #2563EB;
    border: 1px solid #3B82F6;
    border-radius: 12px;
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 700;
    padding: 10px 14px;
}

QPushButton#primaryButton:hover {
    background: #1D4ED8;
}

QPushButton#secondaryButton {
    background: #1F2937;
    border: 1px solid #334155;
    border-radius: 12px;
    color: #E5E7EB;
    font-size: 13px;
    font-weight: 650;
    padding: 10px 14px;
}

QPushButton#secondaryButton:hover {
    background: #334155;
}
"""
