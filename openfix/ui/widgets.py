from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QDialog, QProgressBar,
)

from openfix.config import SCORE_ATTENTION, SCORE_CHECK, SCORE_HEALTHY

class ModernDialog(QDialog):
    def __init__(self, parent, title, subtitle, sections, warning=False):
        super().__init__(parent)
        self.setModal(True)
        self.resize(720, 600)
        self.setMinimumSize(620, 480)
        self.setWindowTitle(title)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        top = QHBoxLayout()
        title_box = QVBoxLayout()

        heading = QLabel(title)
        heading.setObjectName("DialogTitle")
        description = QLabel(subtitle)
        description.setObjectName("DialogSubtitle")
        description.setWordWrap(True)

        title_box.addWidget(heading)
        title_box.addWidget(description)
        top.addLayout(title_box, 1)

        close_x = QPushButton("×")
        close_x.setObjectName("DialogCloseX")
        close_x.setFixedSize(36, 36)
        close_x.clicked.connect(self.accept)
        top.addWidget(close_x)
        root.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        content = QVBoxLayout(container)
        content.setContentsMargins(0, 0, 6, 0)
        content.setSpacing(10)

        for section_title, text in sections:
            card = QFrame()
            card.setObjectName("DialogWarningCard" if warning else "DialogCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 14)

            card_title = QLabel(section_title)
            card_title.setObjectName("DialogCardTitle")
            card_text = QLabel(text)
            card_text.setObjectName("DialogCardText")
            card_text.setWordWrap(True)

            card_layout.addWidget(card_title)
            card_layout.addWidget(card_text)
            content.addWidget(card)

        content.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        footer = QHBoxLayout()
        footer.addStretch()
        close_button = QPushButton("Close")
        close_button.setObjectName("DialogCloseButton")
        close_button.setMinimumWidth(110)
        close_button.clicked.connect(self.accept)
        footer.addWidget(close_button)
        root.addLayout(footer)

class CollapsibleSection(QFrame):
    def __init__(self, title, subtitle, expanded=False):
        super().__init__()
        self.setObjectName("CollapsibleSection")
        self.expanded = expanded

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("CollapsibleHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 13, 12, 13)

        labels = QVBoxLayout()
        labels.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("CollapsibleTitle")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("CollapsibleSubtitle")
        labels.addWidget(self.title_label)
        labels.addWidget(self.subtitle_label)
        header_layout.addLayout(labels, 1)

        self.toggle_button = QPushButton()
        self.toggle_button.setObjectName("CollapseToggle")
        self.toggle_button.setFixedSize(40, 40)
        self.toggle_button.setCursor(Qt.PointingHandCursor)
        self.toggle_button.clicked.connect(self.toggle)
        header_layout.addWidget(self.toggle_button)
        root.addWidget(header)

        self.content_frame = QFrame()
        self.content_frame.setObjectName("CollapsibleContent")
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(14, 14, 14, 14)
        root.addWidget(self.content_frame)

        self.set_expanded(expanded)

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)

    def toggle(self):
        self.set_expanded(not self.expanded)

    def set_expanded(self, expanded):
        self.expanded = expanded
        self.content_frame.setVisible(expanded)
        if expanded:
            self.toggle_button.setText("−")
            self.toggle_button.setToolTip("Collapse section")
        else:
            self.toggle_button.setText("+")
            self.toggle_button.setToolTip("Expand section")

class NavButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(48)

class HealthGauge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._score = None
        self._coverage = None
        self._state = "neutral"
        self.setMinimumSize(156, 156)
        self.setMaximumSize(176, 176)

    def set_score(self, score, coverage=None):
        self._score = score
        self._coverage = coverage
        if score is None:
            self._state = "neutral"
        elif score >= SCORE_HEALTHY:
            self._state = "good"
        elif score >= SCORE_CHECK:
            self._state = "minor"
        elif score >= SCORE_ATTENTION:
            self._state = "warning"
        else:
            self._state = "danger"
        self.update()

    def _accent(self):
        return {
            "good": QColor("#56d49b"),
            "minor": QColor("#f0c66b"),
            "warning": QColor("#f39a58"),
            "danger": QColor("#ff6b75"),
            "neutral": QColor("#6b8db8"),
        }.get(self._state, QColor("#6b8db8"))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        side = min(self.width(), self.height())
        rect = QRectF(12, 12, side - 24, side - 24)
        pen_width = 10

        bg_pen = QPen(QColor("#26303d"), pen_width)
        bg_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 90 * 16, -360 * 16)

        if self._score is not None:
            value = max(0, min(100, float(self._score)))
            fg_pen = QPen(self._accent(), pen_width)
            fg_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(fg_pen)
            painter.drawArc(rect, 90 * 16, -int(360 * 16 * value / 100.0))

        painter.setPen(QColor("#f5f7fb"))
        font = QFont("Segoe UI", 28)
        font.setBold(True)
        painter.setFont(font)
        score_text = "--" if self._score is None else str(int(round(self._score)))
        score_rect = QRectF(0, side * 0.31, side, 48)
        painter.drawText(score_rect, Qt.AlignCenter, score_text)

        painter.setPen(QColor("#78879a"))
        small = QFont("Segoe UI", 9)
        small.setBold(True)
        painter.setFont(small)
        painter.drawText(QRectF(0, side * 0.58, side, 24), Qt.AlignCenter, "HEALTH SCORE")

        if self._coverage is not None:
            painter.setPen(QColor("#5f7187"))
            tiny = QFont("Segoe UI", 8)
            painter.setFont(tiny)
            painter.drawText(
                QRectF(0, side * 0.72, side, 20),
                Qt.AlignCenter,
                f"{int(self._coverage)}% coverage",
            )

class StatCard(QFrame):
    def __init__(self, title, symbol="•"):
        super().__init__()
        self.setObjectName("StatCard")
        self.setProperty("state", "neutral")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 15)
        root.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(10)

        self.symbol = QLabel(symbol)
        self.symbol.setObjectName("MetricSymbol")
        self.symbol.setAlignment(Qt.AlignCenter)
        self.symbol.setFixedSize(34, 34)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        self.title = QLabel(title)
        self.title.setObjectName("StatTitle")
        self.kicker = QLabel("SNAPSHOT")
        self.kicker.setObjectName("StatKicker")
        title_box.addWidget(self.title)
        title_box.addWidget(self.kicker)

        self.badge = QLabel("WAITING")
        self.badge.setObjectName("StatBadge")

        top.addWidget(self.symbol)
        top.addLayout(title_box, 1)
        top.addWidget(self.badge, alignment=Qt.AlignTop)

        value_row = QHBoxLayout()
        self.value = QLabel("--")
        self.value.setObjectName("StatValue")
        self.value.setWordWrap(True)
        value_row.addWidget(self.value, 1)

        self.subtitle = QLabel("Waiting for scan")
        self.subtitle.setObjectName("StatSubtitle")
        self.subtitle.setWordWrap(True)

        self.meter = QProgressBar()
        self.meter.setObjectName("MetricMeter")
        self.meter.setRange(0, 100)
        self.meter.setValue(0)
        self.meter.setTextVisible(False)

        root.addLayout(top)
        root.addLayout(value_row)
        root.addWidget(self.subtitle)
        root.addWidget(self.meter)

    def set_status(self, value, subtitle, badge, state, meter=None):
        self.value.setText(value)
        self.subtitle.setText(subtitle)
        self.badge.setText(badge)
        self.setProperty("state", state)
        self.badge.setProperty("state", state)
        self.symbol.setProperty("state", state)
        self.meter.setProperty("state", state)

        if meter is None:
            self.meter.setValue(0)
            self.meter.setProperty("empty", "true")
        else:
            self.meter.setValue(max(0, min(100, int(round(meter)))))
            self.meter.setProperty("empty", "false")

        for widget in (self, self.badge, self.symbol, self.meter):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

class InfoValueCard(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setObjectName("InfoValueCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 13, 15, 13)
        layout.setSpacing(5)

        heading = QLabel(title.upper())
        heading.setObjectName("InfoValueTitle")
        self.value = QLabel("Not scanned yet")
        self.value.setObjectName("InfoValueText")
        self.value.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(self.value)

    def set_value(self, value):
        self.value.setText(value)

class SectionCard(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setObjectName("SectionCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(17, 15, 17, 15)
        layout.setSpacing(8)

        heading = QLabel(title)
        heading.setObjectName("SectionTitle")
        self.text = QLabel("")
        self.text.setObjectName("SectionText")
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(heading)
        layout.addWidget(self.text)

    def set_lines(self, lines, empty_text):
        if not lines:
            self.text.setText(empty_text)
            return
        self.text.setText("\n".join(f"• {line}" for line in lines))

class RecommendationPanel(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("RecommendationPanel")
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(18, 16, 18, 16)
        self.root.setSpacing(9)

        title_row = QHBoxLayout()
        title = QLabel("Top recommendations")
        title.setObjectName("RecommendationTitle")
        subtitle = QLabel("PRIORITY ORDER")
        subtitle.setObjectName("RecommendationKicker")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(subtitle)
        self.root.addLayout(title_row)

        self.container = QVBoxLayout()
        self.container.setSpacing(8)
        self.root.addLayout(self.container)
        self.set_actions([])

    def _clear(self):
        while self.container.count():
            item = self.container.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def set_actions(self, actions):
        self._clear()
        if not actions:
            empty = QLabel("No immediate action appears necessary.")
            empty.setObjectName("RecommendationEmpty")
            self.container.addWidget(empty)
            return

        for index, action in enumerate(actions[:3], start=1):
            row = QFrame()
            row.setObjectName("RecommendationStep")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 10, 12, 10)
            row_layout.setSpacing(12)

            number = QLabel(str(index))
            number.setObjectName("RecommendationNumber")
            number.setAlignment(Qt.AlignCenter)
            number.setFixedSize(28, 28)

            text = QLabel(action)
            text.setObjectName("RecommendationText")
            text.setWordWrap(True)

            row_layout.addWidget(number)
            row_layout.addWidget(text, 1)
            self.container.addWidget(row)

class PrimaryIssueCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("PrimaryIssueCard")
        self.setProperty("active", "false")

        root = QVBoxLayout(self)
        root.setContentsMargins(19, 17, 19, 17)
        root.setSpacing(8)

        top = QHBoxLayout()
        self.eyebrow = QLabel("SYSTEM STATUS")
        self.eyebrow.setObjectName("PrimaryEyebrow")
        self.signal = QLabel("●")
        self.signal.setObjectName("PrimarySignal")
        top.addWidget(self.eyebrow)
        top.addStretch()
        top.addWidget(self.signal)

        self.issue = QLabel("No major issue detected")
        self.issue.setObjectName("PrimaryIssueText")
        self.issue.setWordWrap(True)
        self.why_title = QLabel("Summary")
        self.why_title.setObjectName("PrimaryWhyTitle")
        self.why = QLabel("Run a scan to see the current diagnostic status.")
        self.why.setObjectName("PrimaryWhyText")
        self.why.setWordWrap(True)

        root.addLayout(top)
        root.addWidget(self.issue)
        root.addWidget(self.why_title)
        root.addWidget(self.why)

    def set_data(self, issue, why):
        if issue:
            self.eyebrow.setText("PRIMARY ISSUE")
            self.why_title.setText("Why this matters")
            self.issue.setText(issue)
            self.why.setText(why or "This item has the highest current diagnostic priority.")
            self.setProperty("active", "true")
        else:
            self.eyebrow.setText("SYSTEM STATUS")
            self.why_title.setText("Summary")
            self.issue.setText("No major issue detected")
            self.why.setText("OpenFix did not identify a major issue that needs immediate attention.")
            self.setProperty("active", "false")

        self.style().unpolish(self)
        self.style().polish(self)

class SummaryBanner(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("SummaryBanner")

        root = QHBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(22)

        self.gauge = HealthGauge()
        root.addWidget(self.gauge, 0, Qt.AlignVCenter)

        center = QVBoxLayout()
        center.setSpacing(7)

        kicker = QLabel("SYSTEM HEALTH OVERVIEW")
        kicker.setObjectName("SummaryKicker")
        title = QLabel("Your PC has not been scanned yet")
        title.setObjectName("SummaryTitle")
        self.text = QLabel("Run a Full System Scan to build a local health overview.")
        self.text.setObjectName("SummaryText")
        self.text.setWordWrap(True)
        self.meta = QLabel("SCAN COVERAGE --  •  LAST SCAN NEVER")
        self.meta.setObjectName("SummaryMeta")

        center.addWidget(kicker)
        center.addWidget(title)
        center.addWidget(self.text)
        center.addStretch()
        center.addWidget(self.meta)
        self.title = title
        root.addLayout(center, 1)

        stats = QFrame()
        stats.setObjectName("SummaryStats")
        stats_layout = QVBoxLayout(stats)
        stats_layout.setContentsMargins(14, 12, 14, 12)
        stats_layout.setSpacing(9)

        self.healthy = self._make_stat("Healthy", "--", "good")
        self.attention = self._make_stat("To check", "--", "warning")
        self.unavailable = self._make_stat("Unavailable", "--", "neutral")
        stats_layout.addWidget(self.healthy)
        stats_layout.addWidget(self.attention)
        stats_layout.addWidget(self.unavailable)
        root.addWidget(stats)

    def _make_stat(self, label, value, state):
        widget = QFrame()
        widget.setObjectName("SummaryMiniStat")
        widget.setProperty("state", state)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(10)
        dot = QLabel("●")
        dot.setObjectName("SummaryMiniDot")
        dot.setProperty("state", state)
        text = QLabel(label)
        text.setObjectName("SummaryMiniLabel")
        number = QLabel(value)
        number.setObjectName("SummaryMiniValue")
        layout.addWidget(dot)
        layout.addWidget(text, 1)
        layout.addWidget(number)
        widget.number_label = number
        return widget

    def set_scanning(self):
        self.title.setText("Scanning local system...")
        self.text.setText("Collecting read-only diagnostic signals and building the health overview.")
        self.meta.setText("LOCAL SCAN IN PROGRESS  •  NO SYSTEM CHANGES")
        self.gauge.set_score(None, None)

    def set_error(self, result):
        self.gauge.set_score(None, 0)
        self.title.setText("Full scan could not complete")
        self.text.setText("OpenFix encountered an internal diagnostic error. This does not mean the PC is unhealthy.")
        self.meta.setText(f"SCAN FAILED  •  LAST ATTEMPT {result.get('scan_time', '--')}")
        self.healthy.number_label.setText("--")
        self.attention.number_label.setText("--")
        self.unavailable.number_label.setText("--")

    def update_summary(self, result):
        if result.get("is_error"):
            self.set_error(result)
            return
        score = result["score"]
        coverage = result.get("coverage")
        healthy = result.get("healthy_areas") or 0
        attention = result.get("attention_areas") or 0
        unavailable = result.get("unavailable_areas") or 0

        self.gauge.set_score(score, coverage)
        if score is None:
            headline = "Health score unavailable"
            summary_text = "OpenFix could not collect enough diagnostic data to calculate a reliable health score."
        elif score >= SCORE_HEALTHY:
            headline = "System looks healthy"
            summary_text = "OpenFix completed the local checks and prioritized the areas that matter most."
        elif score >= SCORE_CHECK:
            headline = "Minor items are worth checking"
            summary_text = "OpenFix completed the local checks and prioritized the areas that matter most."
        elif score >= SCORE_ATTENTION:
            headline = "Some areas need attention"
            summary_text = "OpenFix completed the local checks and prioritized the areas that matter most."
        else:
            headline = "Important issues were detected"
            summary_text = "OpenFix completed the local checks and prioritized the areas that matter most."

        self.title.setText(headline)
        self.text.setText(summary_text)
        coverage_text = f"{coverage}%" if coverage is not None else "N/A"
        self.meta.setText(f"SCAN COVERAGE {coverage_text}  •  LAST SCAN {result['scan_time']}")
        self.healthy.number_label.setText(str(healthy))
        self.attention.number_label.setText(str(attention))
        self.unavailable.number_label.setText(str(unavailable))

class ResultPanel(QFrame):
    rerun_requested = Signal()
    doctor_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("ResultPanel")
        self.current_target = None

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(18)
        left = QVBoxLayout()
        left.setSpacing(4)

        kicker = QLabel("DIAGNOSTIC RESULT")
        kicker.setObjectName("ResultKicker")
        self.title = QLabel("No scan yet")
        self.title.setObjectName("ResultTitle")
        self.description = QLabel("Start a scan to see diagnostic results.")
        self.description.setObjectName("ResultExplanation")
        self.description.setWordWrap(True)

        left.addWidget(kicker)
        left.addWidget(self.title)
        left.addWidget(self.description)
        header.addLayout(left, 1)

        score_box = QFrame()
        score_box.setObjectName("ResultScoreBox")
        score_layout = QVBoxLayout(score_box)
        score_layout.setContentsMargins(14, 10, 14, 10)
        score_layout.setSpacing(2)
        caption = QLabel("ESTIMATED SCORE")
        caption.setObjectName("ScoreCaption")
        self.score = QLabel("--")
        self.score.setObjectName("ResultScore")
        self.badge = QLabel("WAITING")
        self.badge.setObjectName("StatusBadge")
        self.badge.setAlignment(Qt.AlignCenter)
        score_layout.addWidget(caption, alignment=Qt.AlignCenter)
        score_layout.addWidget(self.score, alignment=Qt.AlignCenter)
        score_layout.addWidget(self.badge, alignment=Qt.AlignCenter)
        header.addWidget(score_box)
        root.addLayout(header)

        self.primary = PrimaryIssueCard()
        root.addWidget(self.primary)

        self.top_actions = RecommendationPanel()
        root.addWidget(self.top_actions)

        self.details = CollapsibleSection(
            "Detailed Scan Information",
            "Measured facts, possible problems and additional recommendations",
            expanded=False,
        )
        self.facts = SectionCard("What we found")
        self.issues = SectionCard("Possible problems")
        self.actions = SectionCard("All recommendations")
        self.details.add_widget(self.facts)
        self.details.add_widget(self.issues)
        self.details.add_widget(self.actions)
        root.addWidget(self.details)

        footer = QHBoxLayout()
        self.note = QLabel("")
        self.note.setObjectName("ResultNote")
        self.note.setWordWrap(True)
        footer.addWidget(self.note, 1)

        self.run_again = QPushButton("Run Again")
        self.run_again.setObjectName("SecondaryActionButton")
        self.run_again.hide()
        self.go_doctor = QPushButton("Open Recommended Doctor")
        self.go_doctor.setObjectName("PrimaryButton")
        self.go_doctor.hide()
        self.run_again.clicked.connect(self.rerun_requested.emit)
        self.go_doctor.clicked.connect(self.emit_doctor)
        footer.addWidget(self.run_again, alignment=Qt.AlignBottom)
        footer.addWidget(self.go_doctor, alignment=Qt.AlignBottom)
        root.addLayout(footer)

    def emit_doctor(self):
        if self.current_target:
            self.doctor_requested.emit(self.current_target)

    def set_badge(self, text, state):
        self.badge.setText(text)
        self.badge.setProperty("state", state)
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)

    def set_scanning(self):
        self.title.setText("Scanning your PC")
        self.description.setText("Collecting local diagnostic information. No system changes are being made.")
        self.score.setText("--")
        self.set_badge("SCANNING", "neutral")
        self.primary.set_data(None, None)
        self.top_actions.set_actions([])
        self.facts.set_lines([], "Collecting information...")
        self.issues.set_lines([], "Waiting for results...")
        self.actions.set_lines([], "Waiting for recommendations...")
        self.note.setText("Local diagnostic scan in progress.")
        self.run_again.hide()
        self.go_doctor.hide()

    def set_result(self, result):
        if result.get("is_error"):
            self.title.setText("Scan Error")
            self.score.setText("--")
            self.set_badge("SCAN FAILED", "danger")
            self.description.setText(
                "OpenFix could not complete this diagnostic scan. This is a program/scan error and is not a health score for your PC."
            )
            self.primary.eyebrow.setText("SCAN STATUS")
            self.primary.why_title.setText("What happened")
            self.primary.issue.setText("Diagnostic scan did not complete")
            self.primary.why.setText(result.get("note", "An internal diagnostic error occurred."))
            self.primary.setProperty("active", "true")
            self.primary.style().unpolish(self.primary)
            self.primary.style().polish(self.primary)
            actions = result.get("actions", [])
            self.top_actions.set_actions(actions[:3])
            self.facts.set_lines(result.get("facts", []), "No diagnostic facts were produced because the scan stopped early.")
            self.issues.set_lines(result.get("issues", []), "The scan stopped before health analysis could finish.")
            self.actions.set_lines(actions, "Run the scan again. If it repeats, inspect the OpenFix log in %LOCALAPPDATA%/OpenFix/logs on Windows.")
            self.note.setText(
                f"Scan failed  •  {result.get('scan_time', '--')}  •  Session {result.get('session_id', 'N/A')}"
            )
            self.current_target = None
            self.run_again.show()
            self.go_doctor.hide()
            return

        score = result.get("score")
        coverage = result.get("coverage")
        partial = coverage is not None and coverage < 100

        self.title.setText(result["title"])

        if score is None:
            self.score.setText("N/A")
            self.set_badge("UNAVAILABLE", "neutral")
            self.description.setText(
                "OpenFix could not collect enough diagnostic data to calculate a reliable health score."
            )
            self.primary.set_data(result.get("primary_issue"), result.get("why_it_matters"))
            actions = result.get("actions", [])
            self.top_actions.set_actions(actions[:3])
            self.facts.set_lines(result.get("facts", []), "No diagnostic facts are available.")
            self.issues.set_lines(result.get("issues", []), "No health conclusion was made from unavailable data.")
            self.actions.set_lines(actions, "Run the scan again if you want to retry unavailable checks.")
            coverage_text = f"{coverage}%" if coverage is not None else "Not available"
            self.note.setText(
                f"Coverage {coverage_text}  •  {result.get('scan_time', '--')}\n{result.get('note', '')}"
            )
            self.current_target = result.get("target_doctor")
            self.run_again.show()
            self.go_doctor.setVisible(bool(self.current_target))
            return

        self.score.setText(f"{score}/100")

        if score >= SCORE_HEALTHY:
            label = "HEALTHY"
            state = "good"
            message = "No major problem was detected."
        elif score >= SCORE_CHECK:
            label = "CHECK"
            state = "minor"
            message = "A few items may be worth checking."
        elif score >= SCORE_ATTENTION:
            label = "ATTENTION"
            state = "warning"
            message = "Some diagnostic results need attention."
        else:
            label = "IMPORTANT"
            state = "danger"
            message = "Important items should be checked carefully."

        if partial:
            label += " • PARTIAL"
            message += f" Scan coverage: {coverage}%."

        self.set_badge(label, state)
        self.description.setText(message)
        self.primary.set_data(result.get("primary_issue"), result.get("why_it_matters"))

        actions = result.get("actions", [])
        self.top_actions.set_actions(actions[:3])
        self.facts.set_lines(result.get("facts", []), "No diagnostic facts are available.")
        self.issues.set_lines(result.get("issues", []), "No major problems were found.")
        self.actions.set_lines(actions, "No immediate action appears necessary.")

        coverage_text = f"{coverage}%" if coverage is not None else "Not available"
        self.note.setText(
            f"Coverage {coverage_text}  •  {result['scan_time']}\n{result.get('note', '')}"
        )
        self.current_target = result.get("target_doctor")
        self.run_again.show()
        self.go_doctor.setVisible(bool(self.current_target))

class PageHeader(QWidget):
    def __init__(self, title, subtitle):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        kicker = QLabel("OPENFIX / LOCAL DIAGNOSTICS")
        kicker.setObjectName("PageKicker")
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("PageSubtitle")
        subtitle_label.setWordWrap(True)
        root.addWidget(kicker)
        root.addWidget(title_label)
        root.addWidget(subtitle_label)

