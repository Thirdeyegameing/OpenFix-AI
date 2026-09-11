from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QFrame, QProgressBar, QScrollArea, QStackedWidget,
)

from openfix.config import (
    APP_VERSION, CPU_HIGH, CPU_CRITICAL, RAM_HIGH, RAM_CRITICAL,
    GPU_WARM_C, GPU_HOT_C, PACKET_LOSS_WARN, PING_HIGH_MS,
)
from openfix.core.helpers import format_bytes
from openfix.core.scoring import disk_space_state
from openfix.diagnostics.system import group_process_memory
from openfix.core.scanner import ScanWorker
from openfix.ui.theme import STYLESHEET
from openfix.ui.widgets import (
    ModernDialog, CollapsibleSection, NavButton, StatCard, InfoValueCard,
    SectionCard, SummaryBanner, ResultPanel, PageHeader,
)

class OpenFixWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.scan_buttons = []
        self.active_result = None
        self.active_progress = None
        self.doctor_routes = {}

        self.setWindowTitle(f"OpenFix AI {APP_VERSION}")
        self.resize(1360, 880)
        self.setMinimumSize(1100, 720)

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)

        main = QHBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self.sidebar = self.build_sidebar()
        main.addWidget(self.sidebar)

        content = QWidget()
        content.setObjectName("Content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(34, 25, 34, 28)
        content_layout.addWidget(self.build_topbar())

        self.pages = QStackedWidget()
        content_layout.addWidget(self.pages, 1)
        main.addWidget(content, 1)

        self.dashboard_page = self.build_dashboard()
        self.smart_page = self.build_doctor_page(
            "Local Smart Doctor",
            "Combines several local checks and helps decide what to investigate first.",
            "smart",
        )
        self.internet_page = self.build_doctor_page(
            "Internet Doctor",
            "Checks connection availability, response delay, DNS and stability.",
            "internet",
        )
        self.gaming_page = self.build_doctor_page(
            "Gaming Doctor",
            "Checks common CPU, RAM, GPU and network conditions that may affect games.",
            "gaming",
        )
        self.slow_page = self.build_doctor_page(
            "Slow PC Doctor",
            "Checks common reasons Windows or applications may feel slow.",
            "slow",
        )
        self.storage_page = self.build_doctor_page(
            "Storage Doctor",
            "Checks free space across your drives.",
            "storage",
        )
        self.event_page = self.build_doctor_page(
            "Windows Event Doctor",
            "Checks recent Windows errors while filtering common background noise.",
            "events",
        )

        for page in (
            self.dashboard_page,
            self.smart_page,
            self.internet_page,
            self.gaming_page,
            self.slow_page,
            self.storage_page,
            self.event_page,
        ):
            self.pages.addWidget(page)

        self.doctor_routes = {
            "smart": (1, self.smart_nav),
            "internet": (2, self.internet_nav),
            "gaming": (3, self.gaming_nav),
            "slow": (4, self.slow_nav),
            "storage": (5, self.storage_nav),
            "events": (6, self.event_nav),
        }

        self.apply_style()
        self.show_page(0, self.dashboard_nav)

    def build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(252)
        root = QVBoxLayout(sidebar)
        root.setContentsMargins(18, 22, 18, 20)
        root.setSpacing(8)

        brand = QHBoxLayout()
        brand.setSpacing(11)
        mark = QLabel("OF")
        mark.setObjectName("BrandMark")
        mark.setAlignment(Qt.AlignCenter)
        mark.setFixedSize(42, 42)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        logo = QLabel("OpenFix AI")
        logo.setObjectName("Logo")
        version = QLabel(f"LOCAL DIAGNOSTICS  •  {APP_VERSION}")
        version.setObjectName("SidebarVersion")
        brand_text.addWidget(logo)
        brand_text.addWidget(version)
        brand.addWidget(mark)
        brand.addLayout(brand_text, 1)
        root.addLayout(brand)
        root.addSpacing(20)

        section = QLabel("DIAGNOSTIC CENTER")
        section.setObjectName("SidebarSection")
        root.addWidget(section)

        self.dashboard_nav = NavButton("▦   Dashboard")
        self.smart_nav = NavButton("✦   Smart Doctor")
        self.internet_nav = NavButton("◎   Internet")
        self.gaming_nav = NavButton("◇   Gaming")
        self.slow_nav = NavButton("◷   Slow PC")
        self.storage_nav = NavButton("▣   Storage")
        self.event_nav = NavButton("△   Windows Events")

        self.nav_buttons = [
            self.dashboard_nav,
            self.smart_nav,
            self.internet_nav,
            self.gaming_nav,
            self.slow_nav,
            self.storage_nav,
            self.event_nav,
        ]
        for button in self.nav_buttons:
            root.addWidget(button)

        root.addStretch()

        privacy_card = QFrame()
        privacy_card.setObjectName("PrivacyCard")
        privacy_layout = QVBoxLayout(privacy_card)
        privacy_layout.setContentsMargins(12, 11, 12, 11)
        privacy_layout.setSpacing(5)
        badge = QLabel("●  LOCAL + READ ONLY")
        badge.setObjectName("LocalBadge")
        privacy = QLabel("No Cloud AI\nNo external AI API\nNo automatic system changes")
        privacy.setObjectName("PrivacyText")
        privacy.setWordWrap(True)
        privacy_layout.addWidget(badge)
        privacy_layout.addWidget(privacy)
        root.addWidget(privacy_card)

        routes = [
            (self.dashboard_nav, 0),
            (self.smart_nav, 1),
            (self.internet_nav, 2),
            (self.gaming_nav, 3),
            (self.slow_nav, 4),
            (self.storage_nav, 5),
            (self.event_nav, 6),
        ]
        for button, index in routes:
            button.clicked.connect(
                lambda checked=False, idx=index, btn=button: self.show_page(idx, btn)
            )
        return sidebar

    def build_topbar(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 18)
        layout.setSpacing(8)

        title = QLabel("PC Health Command Center")
        title.setObjectName("TopTitle")
        layout.addWidget(title)
        layout.addStretch()

        badge = QLabel("●  LOCAL ENGINE")
        badge.setObjectName("FactsBadge")
        guide = QPushButton("Guide")
        guide.setObjectName("SecondaryButton")
        terms = QPushButton("Terms")
        terms.setObjectName("SecondaryButton")
        safety = QPushButton("Safety & Privacy")
        safety.setObjectName("SafetyButton")

        guide.clicked.connect(self.show_guide)
        terms.clicked.connect(self.show_terms)
        safety.clicked.connect(self.show_safety)

        layout.addWidget(badge)
        layout.addWidget(guide)
        layout.addWidget(terms)
        layout.addWidget(safety)
        return widget

    def build_dashboard(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        page = QWidget()
        scroll.setWidget(page)
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 28)
        root.setSpacing(16)

        root.addWidget(
            PageHeader(
                "System Dashboard",
                "Latest local snapshot of performance, connectivity, graphics and Windows reliability.",
            )
        )

        self.summary = SummaryBanner()
        root.addWidget(self.summary)

        hero = QFrame()
        hero.setObjectName("HeroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(22, 18, 22, 18)
        hero_layout.setSpacing(18)

        scan_icon = QLabel("SCAN")
        scan_icon.setObjectName("ScanIcon")
        scan_icon.setAlignment(Qt.AlignCenter)
        scan_icon.setFixedSize(58, 58)
        hero_layout.addWidget(scan_icon)

        text_box = QVBoxLayout()
        text_box.setSpacing(4)
        hero_kicker = QLabel("ONE-CLICK HEALTH CHECK")
        hero_kicker.setObjectName("HeroKicker")
        hero_title = QLabel("Full System Scan")
        hero_title.setObjectName("HeroTitle")
        hero_text = QLabel(
            "Checks the main diagnostic areas, correlates results locally and prioritizes what matters first."
        )
        hero_text.setObjectName("HeroText")
        hero_text.setWordWrap(True)
        text_box.addWidget(hero_kicker)
        text_box.addWidget(hero_title)
        text_box.addWidget(hero_text)
        hero_layout.addLayout(text_box, 1)

        scan_meta = QVBoxLayout()
        scan_meta.setSpacing(6)
        chip1 = QLabel("LOCAL")
        chip1.setObjectName("HeroChip")
        chip2 = QLabel("READ ONLY")
        chip2.setObjectName("HeroChip")
        scan_meta.addWidget(chip1, alignment=Qt.AlignRight)
        scan_meta.addWidget(chip2, alignment=Qt.AlignRight)
        hero_layout.addLayout(scan_meta)

        self.full_scan_btn = QPushButton("Run Full Scan")
        self.full_scan_btn.setObjectName("PrimaryButton")
        self.full_scan_btn.setCursor(Qt.PointingHandCursor)
        self.full_scan_btn.setMinimumHeight(44)
        hero_layout.addWidget(self.full_scan_btn)
        root.addWidget(hero)
        self.scan_buttons.append(self.full_scan_btn)

        self.dashboard_progress = QProgressBar()
        self.dashboard_progress.setObjectName("ScanProgress")
        self.dashboard_progress.setRange(0, 0)
        self.dashboard_progress.hide()
        root.addWidget(self.dashboard_progress)

        section_title = QLabel("SYSTEM SNAPSHOT")
        section_title.setObjectName("DashboardSectionTitle")
        root.addWidget(section_title)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(14)
        metrics.setVerticalSpacing(14)

        self.cpu_card = StatCard("CPU", "C")
        self.ram_card = StatCard("Memory", "M")
        self.storage_card = StatCard("Windows Drive", "D")
        self.network_card = StatCard("Internet", "N")
        self.gpu_card = StatCard("Graphics", "G")
        self.events_card = StatCard("Windows Events", "E")

        metrics.addWidget(self.cpu_card, 0, 0)
        metrics.addWidget(self.ram_card, 0, 1)
        metrics.addWidget(self.storage_card, 0, 2)
        metrics.addWidget(self.network_card, 1, 0)
        metrics.addWidget(self.gpu_card, 1, 1)
        metrics.addWidget(self.events_card, 1, 2)
        for column in range(3):
            metrics.setColumnStretch(column, 1)
        root.addLayout(metrics)

        self.system_section = CollapsibleSection(
            "System Information",
            "Processor, installed memory, Windows build, graphics, uptime and active network adapter",
            expanded=False,
        )
        info_grid = QGridLayout()
        info_grid.setSpacing(12)
        self.cpu_model_card = InfoValueCard("Processor")
        self.total_ram_card = InfoValueCard("Memory")
        self.windows_card = InfoValueCard("Windows")
        self.gpu_info_card = InfoValueCard("Graphics Device")
        self.gpu_driver_card = InfoValueCard("Graphics Driver")
        self.uptime_card = InfoValueCard("PC Uptime")
        self.adapter_card = InfoValueCard("Network Adapter")
        info_grid.addWidget(self.cpu_model_card, 0, 0)
        info_grid.addWidget(self.total_ram_card, 0, 1)
        info_grid.addWidget(self.windows_card, 0, 2)
        info_grid.addWidget(self.gpu_info_card, 1, 0)
        info_grid.addWidget(self.gpu_driver_card, 1, 1)
        info_grid.addWidget(self.uptime_card, 1, 2)
        info_grid.addWidget(self.adapter_card, 2, 0, 1, 3)
        self.system_section.add_layout(info_grid)
        root.addWidget(self.system_section)

        self.process_section = CollapsibleSection(
            "Top RAM Usage",
            "Applications currently using the largest share of usable memory",
            expanded=False,
        )
        self.process_card = SectionCard("Applications using the most RAM")
        self.process_card.set_lines([], "Run a Full System Scan to see process information.")
        self.process_section.add_widget(self.process_card)
        root.addWidget(self.process_section)

        result_label = QLabel("SCAN RESULT")
        result_label.setObjectName("DashboardSectionTitle")
        root.addWidget(result_label)
        self.dashboard_result = ResultPanel()
        root.addWidget(self.dashboard_result)
        root.addStretch()

        self.full_scan_btn.clicked.connect(
            lambda: self.start_scan("full", self.dashboard_result, self.dashboard_progress)
        )
        self.dashboard_result.rerun_requested.connect(
            lambda: self.start_scan("full", self.dashboard_result, self.dashboard_progress)
        )
        self.dashboard_result.doctor_requested.connect(self.go_to_doctor)
        return scroll

    def build_doctor_page(self, title, subtitle, mode):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        page = QWidget()
        scroll.setWidget(page)
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 28)
        root.setSpacing(18)
        root.addWidget(PageHeader(title, subtitle))

        action = QFrame()
        action.setObjectName("DoctorHero")
        action_layout = QHBoxLayout(action)
        action_layout.setContentsMargins(22, 18, 22, 18)
        action_layout.setSpacing(16)

        icon = QLabel("DX")
        icon.setObjectName("DoctorIcon")
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(52, 52)
        action_layout.addWidget(icon)

        text = QVBoxLayout()
        text.setSpacing(4)
        ready_kicker = QLabel("FOCUSED DIAGNOSTIC")
        ready_kicker.setObjectName("HeroKicker")
        ready = QLabel("Ready to scan")
        ready.setObjectName("ActionTitle")
        description = QLabel(
            "Read-only local scan. OpenFix will measure this area without automatically changing Windows."
        )
        description.setObjectName("ActionText")
        description.setWordWrap(True)
        text.addWidget(ready_kicker)
        text.addWidget(ready)
        text.addWidget(description)
        action_layout.addLayout(text, 1)

        button = QPushButton("Run Scan")
        button.setObjectName("PrimaryButton")
        button.setMinimumHeight(42)
        action_layout.addWidget(button)
        self.scan_buttons.append(button)
        root.addWidget(action)

        progress = QProgressBar()
        progress.setObjectName("ScanProgress")
        progress.setRange(0, 0)
        progress.hide()
        root.addWidget(progress)

        result = ResultPanel()
        root.addWidget(result)
        root.addStretch()

        button.clicked.connect(lambda: self.start_scan(mode, result, progress))
        result.rerun_requested.connect(lambda: self.start_scan(mode, result, progress))
        result.doctor_requested.connect(self.go_to_doctor)
        return scroll

    def show_page(self, index, active):
        self.pages.setCurrentIndex(index)
        for button in self.nav_buttons:
            button.setChecked(button == active)

    def go_to_doctor(self, doctor):
        route = self.doctor_routes.get(doctor)
        if not route:
            return
        index, button = route
        self.show_page(index, button)

    def enable_scan_buttons(self, enabled):
        for button in self.scan_buttons:
            button.setEnabled(enabled)

    def start_scan(self, mode, result, progress):
        if self.worker is not None and self.worker.isRunning():
            self.show_small_message(
                "Scan already running",
                "OpenFix is already checking this PC. Please wait for the current scan to finish.",
            )
            return

        self.active_result = result
        self.active_progress = progress
        result.set_scanning()
        progress.show()
        self.enable_scan_buttons(False)

        if mode == "full":
            self.summary.set_scanning()
            self.full_scan_btn.setText("Scanning...")

        self.worker = ScanWorker(mode)
        self.worker.result_ready.connect(self.scan_complete)
        self.worker.finished.connect(self.scan_thread_finished)
        self.worker.start()

    def scan_thread_finished(self):
        worker = self.sender()
        if worker is self.worker:
            self.worker = None
            if self.active_progress:
                self.active_progress.hide()
            self.enable_scan_buttons(True)
            self.full_scan_btn.setText("Run Full Scan")
        if worker is not None:
            worker.deleteLater()

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            event.ignore()
            self.show_small_message(
                "Scan still running",
                "Please wait for the current diagnostic scan to finish before closing OpenFix. This prevents the scan thread from being destroyed while Windows checks are still running.",
            )
            return
        event.accept()

    def scan_complete(self, result):
        if self.active_result:
            self.active_result.set_result(result)

        if result.get("is_error") and self.active_result is self.dashboard_result:
            self.summary.set_error(result)
        elif "dashboard_data" in result:
            self.update_dashboard(result["dashboard_data"], result["event_analysis"])
            self.summary.update_summary(result)

    def update_dashboard(self, data, events):
        cpu = data["cpu"]
        if cpu is None:
            self.cpu_card.set_status("N/A", "CPU usage could not be read", "UNAVAILABLE", "unavailable", None)
        elif cpu < CPU_HIGH:
            self.cpu_card.set_status(f"{cpu:.0f}%", "Normal usage", "GOOD", "good", cpu)
        elif cpu < CPU_CRITICAL:
            self.cpu_card.set_status(f"{cpu:.0f}%", "Higher than normal", "CHECK", "minor", cpu)
        else:
            self.cpu_card.set_status(f"{cpu:.0f}%", "Very high usage", "HIGH", "danger", cpu)

        memory = data["memory"]
        ram = memory["percent"]
        if ram is None:
            self.ram_card.set_status("N/A", "RAM usage unavailable", "UNAVAILABLE", "unavailable", None)
        elif ram < RAM_HIGH:
            self.ram_card.set_status(f"{ram:.0f}%", "Normal usage", "GOOD", "good", ram)
        elif ram < RAM_CRITICAL:
            self.ram_card.set_status(f"{ram:.0f}%", "High usage", "CHECK", "minor", ram)
        else:
            self.ram_card.set_status(f"{ram:.0f}%", "Very high usage", "HIGH", "danger", ram)

        drive = data["system_drive"]
        if not drive:
            self.storage_card.set_status("N/A", "Drive information unavailable", "UNAVAILABLE", "unavailable", None)
        else:
            disk_state, free_gb, free_percent = disk_space_state(drive)
            subtitle = f"{drive['device']} free space • {free_percent:.0f}% free"
            if disk_state == "critical":
                badge, state = "LOW", "danger"
            elif disk_state == "low":
                badge, state = "CHECK", "minor"
            else:
                badge, state = "GOOD", "good"
            self.storage_card.set_status(f"{free_gb:.0f} GB", subtitle, badge, state, free_percent)

        network = data["network"]
        online = network.get("online")
        if network.get("connectivity_tested") and online is False:
            self.network_card.set_status("Offline", "External connectivity not confirmed", "CHECK", "danger", 0)
        elif not network.get("connectivity_tested"):
            self.network_card.set_status("N/A", "Connectivity test unavailable", "UNAVAILABLE", "unavailable", None)
        else:
            ping = network.get("ping")
            loss = network.get("packet_loss")
            icmp = network.get("icmp_reachable")
            value = f"{ping} ms" if ping is not None else ("Online" if online is True else "Unknown")
            if icmp is True and loss is not None and loss >= PACKET_LOSS_WARN:
                self.network_card.set_status(value, f"{loss}% packet loss", "UNSTABLE", "warning", max(0, 100 - (loss * 10)))
            elif ping is not None and ping >= PING_HIGH_MS:
                self.network_card.set_status(value, "High response delay", "HIGH", "warning", max(0, 100 - min(100, ping / 2)))
            elif online is True and network.get("ping_tested") and icmp is False:
                self.network_card.set_status("Online", "Ping blocked or unavailable", "PING N/A", "neutral", 100)
            elif online is True:
                subtitle = f"{loss}% packet loss" if icmp is True and loss is not None else "External connectivity confirmed"
                self.network_card.set_status(value, subtitle, "GOOD", "good", 100 if loss in (None, 0) else max(0, 100 - (loss * 10)))
            else:
                self.network_card.set_status(value, "Connectivity result inconclusive", "CHECK", "minor", None)

        gpu = data["gpu"]
        if not gpu["available"]:
            self.gpu_card.set_status("N/A", "Graphics information unavailable", "UNAVAILABLE", "unavailable", None)
        else:
            name = gpu["name"]
            if len(name) > 30:
                name = name[:27] + "..."
            temperature = gpu["temperature"]
            if temperature is None:
                self.gpu_card.set_status(name, "GPU detected • temperature sensor unavailable", "TEMP N/A", "neutral", None)
            elif temperature >= GPU_HOT_C:
                self.gpu_card.set_status(name, f"{temperature:.0f}°C", "HOT", "danger", min(100, temperature))
            elif temperature >= GPU_WARM_C:
                self.gpu_card.set_status(name, f"{temperature:.0f}°C", "CHECK", "warning", min(100, temperature))
            else:
                self.gpu_card.set_status(name, f"{temperature:.0f}°C", "GOOD", "good", min(100, temperature))

        serious = (
            events["hardware_errors"]
            + events["storage_errors"]
            + events["shutdown_errors"]
            + events["gpu_errors"]
        )
        if not events["available"]:
            self.events_card.set_status("N/A", "Event data unavailable", "UNAVAILABLE", "unavailable", None)
        elif serious == 0:
            self.events_card.set_status("Good", "No major system event detected", "GOOD", "good", 100)
        else:
            self.events_card.set_status(str(serious), "Important event(s) detected", "CHECK", "warning", max(0, 100 - min(100, serious * 20)))

        self.cpu_model_card.set_value(data["cpu_model"])
        self.total_ram_card.set_value(
            f"Installed {format_bytes(data.get('installed_ram'))} • Usable {format_bytes(memory['total'])}"
            if data.get("installed_ram") else f"Usable {format_bytes(memory['total'])}"
        )
        windows = data["windows"]
        self.windows_card.set_value(f"{windows['caption']} • Build {windows['build']}")
        self.gpu_info_card.set_value(gpu["name"] if gpu["available"] else "Not available")
        self.gpu_driver_card.set_value(gpu["driver"] if gpu["driver"] else "Not available")
        self.uptime_card.set_value(data["uptime"]["text"])

        adapter = network["adapter"]
        if adapter["available"]:
            self.adapter_card.set_value(
                f"{adapter['name']} • {adapter['description']} • {adapter['link_speed']}"
            )
        else:
            self.adapter_card.set_value("Not available")

        lines = []
        total_ram = memory["total"] or 0
        for index, process in enumerate(group_process_memory(data["processes"], limit=3), start=1):
            percent = process["memory"] / total_ram * 100 if total_ram > 0 else 0
            suffix = f" • {process['count']} processes" if process["count"] > 1 else ""
            lines.append(
                f"{index}. {process['name']} — {format_bytes(process['memory'])} ({percent:.1f}% of usable RAM){suffix}"
            )
        self.process_card.set_lines(lines, "Process information is not available.")

    def show_guide(self):
        dialog = ModernDialog(
            self,
            "How to Use OpenFix AI",
            "A simple guide to understanding the diagnostic results.",
            [
                ("1. Start with Full System Scan", "Use the Dashboard scan first for a general PC health overview."),
                ("Primary Issue", "The issue OpenFix currently considers the most important item to investigate first."),
                ("Why this matters", "A short explanation of how the primary issue may affect your PC."),
                ("Top Recommendations", "The most useful next actions are shown before the full detailed result."),
                ("Scan Coverage", "Shows how much of the planned diagnostic information OpenFix successfully read. A failed test can still count as successfully tested."),
            ],
        )
        dialog.exec()

    def show_terms(self):
        dialog = ModernDialog(
            self,
            "Simple Terms",
            "Short explanations for common computer terms used by OpenFix.",
            [
                ("Ping / Response Time", "How long data takes to travel to another computer and back. Lower is usually better."),
                ("Packet Loss", "Network data that did not reach its destination. It can cause lag and unstable calls or games."),
                ("DNS", "The system that converts website names into network addresses."),
                ("Event ID", "A reference number Windows gives to a recorded system event."),
                ("Scan Coverage", "How much of the planned diagnostic information OpenFix successfully tested or read."),
                ("CPU", "The main processor that performs calculations."),
                ("RAM", "Fast temporary memory used by Windows and running applications."),
                ("Uptime", "How long the PC has been running since its last full boot."),
            ],
        )
        dialog.exec()

    def show_safety(self):
        dialog = ModernDialog(
            self,
            "Safety & Privacy",
            "Important information about how OpenFix currently works.",
            [
                ("Local analysis", "No Cloud AI and no external AI API are used. Smart Doctor analysis uses built-in local rules."),
                ("Read-only diagnostics", "OpenFix does not automatically edit the Registry, remove drivers or disable Windows services."),
                ("Normal connectivity checks", "Internet Doctor uses standard tests such as ping and DNS lookup. These are not AI services."),
                ("Scores are estimates", "A low score does not prove hardware is broken. A score of 100 also cannot guarantee that every component is healthy."),
                ("Before major changes", "Important hardware problems should be confirmed with dedicated diagnostic tools."),
            ],
            warning=True,
        )
        dialog.exec()

    def show_small_message(self, title, message):
        dialog = ModernDialog(
            self,
            title,
            message,
            [("Current status", "Wait for the current diagnostic scan to finish before starting another one.")],
        )
        dialog.resize(560, 360)
        dialog.exec()

    def apply_style(self):
        self.setStyleSheet(STYLESHEET)
