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
QDialog#toolDialog,
QFrame#workspacePanel {
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
QLabel#dialogTitle,
QLabel#workspaceTitle {
    color: #F8FAFC;
    font-size: 20px;
    font-weight: 700;
}

QLabel#workspaceTitle {
    font-size: 22px;
    font-weight: 750;
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

QLineEdit#workspaceInput {
    background: #0F172A;
    border: 1px solid #253044;
    border-radius: 12px;
    color: #F8FAFC;
    font-size: 13px;
    padding: 10px 12px;
    selection-background-color: #2563EB;
}

QLineEdit#workspaceInput:hover,
QLineEdit#workspaceInput:focus {
    border-color: #3B82F6;
}

QComboBox#formatCombo,
QDoubleSpinBox#timeSpin {
    background: #0F172A;
    border: 1px solid #253044;
    border-radius: 12px;
    color: #F8FAFC;
    font-size: 13px;
    padding: 9px 12px;
}

QComboBox#formatCombo {
    min-width: 120px;
}

QDoubleSpinBox#timeSpin {
    min-width: 96px;
}

QComboBox#formatCombo:hover,
QComboBox#formatCombo:focus,
QDoubleSpinBox#timeSpin:hover,
QDoubleSpinBox#timeSpin:focus {
    border-color: #3B82F6;
}

QComboBox#formatCombo QAbstractItemView {
    background: #0F172A;
    border: 1px solid #253044;
    color: #F8FAFC;
    selection-background-color: #1D4ED8;
    selection-color: #FFFFFF;
}

QComboBox#formatCombo::drop-down {
    border: none;
    width: 26px;
}

QScrollArea#toolScroll {
    background: transparent;
    border: none;
}

QScrollArea#dialogScroll {
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

QPushButton#modeTab {
    background: #0F172A;
    border: 1px solid #253044;
    border-radius: 14px;
    color: #CBD5E1;
    font-size: 13px;
    font-weight: 700;
    padding: 10px 18px;
}

QPushButton#modeTab:hover {
    border-color: #3B82F6;
    color: #F8FAFC;
}

QPushButton#modeTab:checked {
    background: #172554;
    border-color: #3B82F6;
    color: #DBEAFE;
}

QSlider#editSlider::groove:horizontal {
    background: #0F172A;
    border: 1px solid #253044;
    border-radius: 7px;
    height: 10px;
}

QSlider#editSlider::sub-page:horizontal {
    background: #2563EB;
    border-radius: 7px;
}

QSlider#editSlider::handle:horizontal {
    background: #F8FAFC;
    border: 2px solid #2563EB;
    border-radius: 9px;
    height: 18px;
    margin: -6px 0;
    width: 18px;
}

QLabel#valueBadge {
    background: #0F172A;
    border: 1px solid #253044;
    border-radius: 12px;
    color: #F8FAFC;
    font-size: 13px;
    font-weight: 700;
    min-width: 74px;
    padding: 9px 12px;
}

QFrame#dialogSeparator {
    background: #1F2937;
    border: none;
    max-height: 1px;
}

QLabel#statusLabel {
    color: #93C5FD;
    font-size: 13px;
}

QLabel#successLabel {
    color: #86EFAC;
    font-size: 13px;
}

QLabel#errorLabel {
    color: #FCA5A5;
    font-size: 13px;
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

QPushButton:disabled {
    color: #64748B;
}

QListWidget#pdfList,
QTableWidget#pageTable {
    background: #0F172A;
    border: 1px solid #253044;
    border-radius: 16px;
    color: #E5E7EB;
    gridline-color: #1F2937;
    outline: none;
}

QListWidget#pdfList::item {
    border: none;
    padding: 4px;
}

QListWidget#pdfList::item:selected {
    background: #172554;
    border-radius: 14px;
}

QFrame#pdfQueueCard,
QFrame#pdfOutputPanel {
    background: #0B1220;
    border: 1px solid #253044;
    border-radius: 18px;
}

QLabel#pdfQueueTitle {
    color: #F8FAFC;
    font-size: 14px;
    font-weight: 700;
}

QLabel#pdfQueuePath {
    color: #94A3B8;
    font-size: 12px;
}

QHeaderView::section {
    background: #111827;
    border: 0;
    border-bottom: 1px solid #253044;
    color: #CBD5E1;
    font-size: 12px;
    font-weight: 700;
    padding: 10px 8px;
}

QTableWidget#pageTable::item {
    padding: 8px;
}
"""
