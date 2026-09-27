import sys
from datetime import datetime
import numpy as np
import pyqtgraph as pg
import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    convert_xor
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QPushButton, QLineEdit,
    QLabel, QListWidget, QStackedWidget, QComboBox, 
    QSplitter, QListWidgetItem, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QCursor


# ==========================================
# MODULE 1: MATHEMATICAL ENGINE
# ==========================================
class MathEngine:
    """Handles mathematical parsing, safe evaluation, and function generation."""
    def __init__(self):
        self.x = sp.Symbol('x')
        self.angle_mode = 'RAD'  # 'RAD' or 'DEG'
        self.last_answer = ""

    def preprocess(self, expr: str) -> str:
        replacements = {
            '×': '*', '÷': '/', '²': '**2', '³': '**3',
            '√': 'sqrt', 'π': 'pi', 'mod': '%',
            '[': '(', ']': ')', '{': '(', '}': ')'
        }
        for old, new in replacements.items():
            expr = expr.replace(old, new)
        return expr

    def evaluate(self, expression: str) -> str:
        if not expression.strip():
            return ""
        try:
            expr_clean = self.preprocess(expression)
            
            # Substitute 'Ans' with last_answer
            if 'Ans' in expr_clean:
                if not self.last_answer:
                    return "Error: No Ans"
                expr_clean = expr_clean.replace('Ans', f"({self.last_answer})")

            # Enable implicit multiplication (e.g. 2x -> 2*x, 3(4+5) -> 3*(4+5))
            transformations = standard_transformations + (implicit_multiplication_application, convert_xor)
            parsed = parse_expr(expr_clean, transformations=transformations)
            
            # Degree mode handling for trig functions
            if self.angle_mode == 'DEG':
                d2r = sp.pi / 180
                parsed = parsed.replace(
                    lambda expr: expr.is_Function and expr.func in (sp.sin, sp.cos, sp.tan),
                    lambda expr: expr.func(expr.args[0] * d2r)
                )

            result = parsed.evalf()

            if result == sp.zoo or result == sp.oo or result == -sp.oo:
                return "Error: Division by Zero"
            
            if result.is_real:
                val = float(result)
                if abs(val) < 1e-12:
                    val = 0.0
                if val.is_integer():
                    res_str = str(int(val))
                else:
                    res_str = f"{val:.10g}"
                self.last_answer = res_str
                return res_str
            return str(result)
        except ZeroDivisionError:
            return "Error: Division by Zero"
        except (sp.SympifyError, SyntaxError, TypeError):
            return "Syntax Error"
        except Exception:
            return "Invalid Expression"

    def get_numpy_function(self, expression: str):
        """Compiles a string expression into a fast vectorized NumPy function."""
        try:
            expr_clean = self.preprocess(expression)
            transformations = standard_transformations + (implicit_multiplication_application, convert_xor)
            parsed = parse_expr(expr_clean, transformations=transformations)
            
            if self.angle_mode == 'DEG':
                d2r = sp.pi / 180
                parsed = parsed.replace(
                    lambda expr: expr.is_Function and expr.func in (sp.sin, sp.cos, sp.tan),
                    lambda expr: expr.func(expr.args[0] * d2r)
                )

            return sp.lambdify(self.x, parsed, modules=['numpy', 'math'])
        except Exception:
            return None


# ==========================================
# MODULE 2: HISTORY MANAGEMENT
# ==========================================
class CalculationHistory(QWidget):
    """History panel storing expressions, results, and timestamps."""
    expression_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        header_layout = QHBoxLayout()
        label = QLabel("History")
        label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        clear_btn = QPushButton("Clear")
        clear_btn.setMaximumWidth(60)
        clear_btn.clicked.connect(self.clear_history)
        
        header_layout.addWidget(label)
        header_layout.addStretch()
        header_layout.addWidget(clear_btn)
        
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        layout.addLayout(header_layout)
        layout.addWidget(self.list_widget)

    def add_entry(self, expr: str, result: str):
        time_str = datetime.now().strftime("%H:%M:%S")
        item_text = f"[{time_str}] {expr}\n= {result}"
        item = QListWidgetItem(item_text)
        item.setData(Qt.ItemDataRole.UserRole, result)
        self.list_widget.insertItem(0, item)

    def clear_history(self):
        self.list_widget.clear()

    def on_item_double_clicked(self, item: QListWidgetItem):
        res = item.data(Qt.ItemDataRole.UserRole)
        if res:
            self.expression_selected.emit(res)


# ==========================================
# MODULE 3: GRAPHING ENGINE
# ==========================================
class GraphingWorkspace(QWidget):
    """A highly optimized graphing calculator view supporting multi-functions and controls."""
    def __init__(self, math_engine: MathEngine):
        super().__init__()
        self.engine = math_engine
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Controls Toolbar
        self.controls_layout = QHBoxLayout()
        self.reset_btn = QPushButton("Reset View")
        self.zoom_in_btn = QPushButton("Zoom +")
        self.zoom_out_btn = QPushButton("Zoom -")
        self.grid_btn = QPushButton("Toggle Grid")

        self.reset_btn.clicked.connect(self.reset_view)
        self.zoom_in_btn.clicked.connect(lambda: self.plot_widget.zoomIn())
        self.zoom_out_btn.clicked.connect(lambda: self.plot_widget.zoomOut())
        self.grid_btn.clicked.connect(self.toggle_grid)

        self.controls_layout.addWidget(self.reset_btn)
        self.controls_layout.addWidget(self.zoom_in_btn)
        self.controls_layout.addWidget(self.zoom_out_btn)
        self.controls_layout.addWidget(self.grid_btn)
        self.controls_layout.addStretch()

        # Function Input Area
        self.input_layout = QHBoxLayout()
        self.func_label = QLabel("f(x) = ")
        self.func_label.setFont(QFont("Segoe UI", 12))
        self.func_input = QLineEdit()
        self.func_input.setPlaceholderText("e.g., x^2 + sin(x)")
        self.func_input.setFont(QFont("Segoe UI", 12))
        self.plot_btn = QPushButton("Plot")
        self.plot_btn.setObjectName("AccentButton")
        
        self.input_layout.addWidget(self.func_label)
        self.input_layout.addWidget(self.func_input)
        self.input_layout.addWidget(self.plot_btn)

        # PyQtGraph Setup
        pg.setConfigOptions(antialias=True)
        self.plot_widget = pg.PlotWidget(background='#ffffff')
        self.grid_enabled = True
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('bottom', 'X Axis')
        self.plot_widget.setLabel('left', 'Y Axis')

        # Trace Crosshairs
        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('#8e8e93', style=Qt.PenStyle.DashLine))
        self.h_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('#8e8e93', style=Qt.PenStyle.DashLine))
        self.plot_widget.addItem(self.v_line, ignoreBounds=True)
        self.plot_widget.addItem(self.h_line, ignoreBounds=True)
        
        self.tooltip = pg.TextItem(text="", color="k", fill=pg.mkBrush(255, 255, 255, 220))
        self.plot_widget.addItem(self.tooltip, ignoreBounds=True)

        self.layout.addLayout(self.controls_layout)
        self.layout.addLayout(self.input_layout)
        self.layout.addWidget(self.plot_widget)

        self.current_x = None
        self.current_y = None
        self.plot_btn.clicked.connect(self.update_plot)
        self.func_input.returnPressed.connect(self.update_plot)
        self.proxy = pg.SignalProxy(self.plot_widget.scene().sigMouseMoved, rateLimit=60, slot=self.mouse_moved)

        self.reset_view()

    def reset_view(self):
        self.plot_widget.setXRange(-10, 10)
        self.plot_widget.setYRange(-10, 10)

    def toggle_grid(self):
        self.grid_enabled = not self.grid_enabled
        self.plot_widget.showGrid(x=self.grid_enabled, y=self.grid_enabled, alpha=0.3)

    def update_plot(self):
        func_str = self.func_input.text()
        func = self.engine.get_numpy_function(func_str)
        if not func:
            return

        self.current_x = np.linspace(-50, 50, 4000)
        try:
            with np.errstate(divide='ignore', invalid='ignore'):
                self.current_y = func(self.current_x)
                if np.isscalar(self.current_y):
                    self.current_y = np.full_like(self.current_x, self.current_y)
                self.current_y[np.abs(self.current_y) > 1e4] = np.nan
        except Exception:
            return

        self.plot_widget.clear()
        self.plot_widget.addItem(self.v_line, ignoreBounds=True)
        self.plot_widget.addItem(self.h_line, ignoreBounds=True)
        self.plot_widget.addItem(self.tooltip, ignoreBounds=True)
        
        pen = pg.mkPen(color='#007aff', width=2.5)
        self.plot_widget.plot(self.current_x, self.current_y, pen=pen)

    def mouse_moved(self, evt):
        pos = evt[0]
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            x_val = mouse_point.x()
            y_val = mouse_point.y()

            if self.current_x is not None and self.current_y is not None:
                idx = (np.abs(self.current_x - x_val)).argmin()
                snap_x = self.current_x[idx]
                snap_y = self.current_y[idx]
                
                if not np.isnan(snap_y):
                    self.v_line.setPos(snap_x)
                    self.h_line.setPos(snap_y)
                    self.tooltip.setPos(snap_x, snap_y)
                    self.tooltip.setText(f"Point: ({snap_x:.3f}, {snap_y:.3f})\nf(x) = {snap_y:.3f}")
                    return

            self.v_line.setPos(x_val)
            self.h_line.setPos(y_val)
            self.tooltip.setPos(x_val, y_val)
            self.tooltip.setText(f"x = {x_val:.3f}\ny = {y_val:.3f}")


# ==========================================
# MODULE 4: SCIENTIFIC CALCULATOR UI
# ==========================================
class ScientificCalculator(QWidget):
    """Main scientific calculator view with interactive keypad and history."""
    def __init__(self, math_engine: MathEngine, history: CalculationHistory):
        super().__init__()
        self.engine = math_engine
        self.history = history
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        calc_container = QWidget()
        calc_layout = QVBoxLayout(calc_container)
        calc_layout.setSpacing(12)
        
        # Display Area
        self.display_expr = QLineEdit()
        self.display_expr.setPlaceholderText("0")
        self.display_expr.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.display_expr.setObjectName("ExprDisplay")
        self.display_expr.returnPressed.connect(self.evaluate_expression)
        
        self.display_res = QLabel("")
        self.display_res.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.display_res.setObjectName("ResDisplay")
        
        calc_layout.addWidget(self.display_expr)
        calc_layout.addWidget(self.display_res)

        # Keypad layout
        self.keypad_layout = QGridLayout()
        self.keypad_layout.setSpacing(6)
        calc_layout.addLayout(self.keypad_layout)

        buttons = [
            ['(', ')', '[', ']', 'C', 'DEL'],
            ['sin()', 'cos()', 'tan()', 'π', 'e', 'mod'],
            ['x²', '√()', 'log()', '7', '8', '9', '÷'],
            ['|x|', 'x!', '10^()', '4', '5', '6', '×'],
            ['{', '}', 'x^()', '1', '2', '3', '-'],
            ['a/b', 'Ans', 'RAD', '.', '0', '=', '+']
        ]

        self.mode_btn_ref = None

        for row, cols in enumerate(buttons):
            for col, text in enumerate(cols):
                btn = QPushButton(text)
                btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                if text == 'RAD':
                    self.mode_btn_ref = btn
                
                if text in ['=', 'C', 'DEL']:
                    btn.setObjectName("AccentButton" if text == '=' else "CtrlButton")
                elif text.isdigit() or text == '.':
                    btn.setObjectName("NumButton")
                else:
                    btn.setObjectName("FuncButton")
                    
                btn.clicked.connect(lambda ch, t=text: self.on_button_click(t))
                self.keypad_layout.addWidget(btn, row, col)

        self.layout.addWidget(calc_container, stretch=3)
        self.layout.addWidget(self.history, stretch=1)
        self.history.expression_selected.connect(self.insert_history_value)

    def insert_history_value(self, val: str):
        pos = self.display_expr.cursorPosition()
        curr = self.display_expr.text()
        self.display_expr.setText(curr[:pos] + val + curr[pos:])
        self.display_expr.setFocus()

    def toggle_angle_mode(self):
        if self.engine.angle_mode == 'RAD':
            self.engine.angle_mode = 'DEG'
            self.mode_btn_ref.setText('DEG')
        else:
            self.engine.angle_mode = 'RAD'
            self.mode_btn_ref.setText('RAD')

    def evaluate_expression(self):
        expr_text = self.display_expr.text()
        if not expr_text.strip():
            return
        res = self.engine.evaluate(expr_text)
        self.display_res.setText(res)
        if "Error" not in res and res != "Syntax Error" and res != "Invalid Expression":
            self.history.add_entry(expr_text, res)

    def on_button_click(self, char: str):
        if char == 'C':
            self.display_expr.clear()
            self.display_res.clear()
            return
        elif char == 'DEL':
            self.display_expr.backspace()
            return
        elif char == '=':
            self.evaluate_expression()
            return
        elif char in ['RAD', 'DEG']:
            self.toggle_angle_mode()
            return

        pos = self.display_expr.cursorPosition()
        current = self.display_expr.text()

        insert_text = char
        cursor_offset = len(char)

        if char.endswith('()'):
            insert_text = char
            cursor_offset = len(char) - 1
        elif char == 'x²':
            insert_text = '²'
            cursor_offset = 1
        elif char == 'x^()':
            insert_text = '^()'
            cursor_offset = 2
        elif char == '|x|':
            insert_text = 'abs()'
            cursor_offset = 4
        elif char == 'a/b':
            insert_text = '/'
            cursor_offset = 1

        new_text = current[:pos] + insert_text + current[pos:]
        self.display_expr.setText(new_text)
        self.display_expr.setCursorPosition(pos + cursor_offset)
        self.display_expr.setFocus()


# ==========================================
# MODULE 5: PROGRAMMER & CONVERTER UTILS
# ==========================================
class ProgrammerCalculator(QWidget):
    """Programmer mode for Base conversion (HEX, DEC, OCT, BIN)."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        self.input_num = QLineEdit()
        self.input_num.setPlaceholderText("Enter integer number...")
        self.input_num.setFont(QFont("Segoe UI", 14))
        self.input_num.textChanged.connect(self.convert_bases)

        self.hex_label = QLabel("HEX: ")
        self.dec_label = QLabel("DEC: ")
        self.oct_label = QLabel("OCT: ")
        self.bin_label = QLabel("BIN: ")

        for label in [self.hex_label, self.dec_label, self.oct_label, self.bin_label]:
            label.setFont(QFont("Segoe UI", 12))

        layout.addWidget(self.input_num)
        layout.addWidget(self.hex_label)
        layout.addWidget(self.dec_label)
        layout.addWidget(self.oct_label)
        layout.addWidget(self.bin_label)
        layout.addStretch()

    def convert_bases(self, text: str):
        if not text.strip():
            for label in [self.hex_label, self.dec_label, self.oct_label, self.bin_label]:
                label.setText(label.text().split(':')[0] + ": ")
            return
        try:
            val = int(text)
            self.hex_label.setText(f"HEX: {hex(val).upper()[2:]}")
            self.dec_label.setText(f"DEC: {val}")
            self.oct_label.setText(f"OCT: {oct(val)[2:]}")
            self.bin_label.setText(f"BIN: {bin(val)[2:]}")
        except ValueError:
            self.hex_label.setText("HEX: Invalid input")


# ==========================================
# MODULE 6: MAIN APPLICATION & RESPONSIVE UX
# ==========================================
class MainWindow(QMainWindow):
    """Orchestrates navigation, layout breakpoints, and responsive behavior."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ProCalc - Scientific & Graphing")
        self.setMinimumSize(360, 550)
        self.resize(1280, 800)

        self.engine = MathEngine()
        self.history = CalculationHistory()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        # Mobile Mode Selector Dropdown
        self.mobile_mode_selector = QComboBox()
        self.mobile_mode_selector.addItems([
            "Scientific", "Graphing", "Programmer"
        ])
        self.mobile_mode_selector.hide()
        self.mobile_mode_selector.currentTextChanged.connect(self.change_mode)
        self.main_layout.addWidget(self.mobile_mode_selector)

        # Main Splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(self.splitter)

        # Desktop Sidebar
        self.sidebar = QListWidget()
        self.sidebar.addItems([
            "Scientific", "Graphing", "Programmer"
        ])
        self.sidebar.setCurrentRow(0)
        self.sidebar.setMaximumWidth(200)
        self.sidebar.currentTextChanged.connect(self.change_mode)
        self.splitter.addWidget(self.sidebar)

        # Stacked Views
        self.stack = QStackedWidget()
        self.splitter.addWidget(self.stack)

        # Initialize Mode Instances
        self.scientific_calc = ScientificCalculator(self.engine, self.history)
        self.graphing_calc = GraphingWorkspace(self.engine)
        self.programmer_calc = ProgrammerCalculator()

        self.stack.addWidget(self.scientific_calc)  # Idx 0
        self.stack.addWidget(self.graphing_calc)    # Idx 1
        self.stack.addWidget(self.programmer_calc)  # Idx 2

        self.apply_styles()

    def change_mode(self, mode_name: str):
        if mode_name == "Scientific":
            self.stack.setCurrentWidget(self.scientific_calc)
        elif mode_name == "Graphing":
            self.stack.setCurrentWidget(self.graphing_calc)
        elif mode_name == "Programmer":
            self.stack.setCurrentWidget(self.programmer_calc)

    def resizeEvent(self, event):
        """Responsive breakpoint handler."""
        width = event.size().width()
        if width < 768:
            self.sidebar.hide()
            self.mobile_mode_selector.show()
        else:
            self.sidebar.show()
            self.mobile_mode_selector.hide()
        super().resizeEvent(event)

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f5f7; }
            QListWidget {
                background-color: #e8e8ed;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                padding: 6px;
            }
            QListWidget::item { padding: 10px; border-radius: 8px; margin-bottom: 4px; }
            QListWidget::item:selected { background-color: #ffffff; color: #000000; font-weight: bold; }
            
            QComboBox { padding: 8px; font-size: 15px; border-radius: 8px; border: 1px solid #d1d1d6; }
            
            QLineEdit#ExprDisplay {
                background-color: transparent;
                border: none;
                font-size: 36px;
                color: #1c1c1e;
                padding: 6px;
            }
            QLabel#ResDisplay {
                font-size: 22px;
                color: #8e8e93;
                padding: 6px;
            }
            
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #e5e5ea;
                border-radius: 10px;
                padding: 12px;
                font-size: 15px;
                font-family: "Segoe UI", sans-serif;
            }
            QPushButton:pressed { background-color: #f2f2f7; }
            
            QPushButton#NumButton { font-size: 18px; font-weight: bold; }
            QPushButton#FuncButton { background-color: #f2f2f7; }
            
            QPushButton#AccentButton {
                background-color: #007aff;
                color: white;
                border: none;
                font-weight: bold;
                font-size: 18px;
            }
            QPushButton#AccentButton:pressed { background-color: #005bb5; }
            QPushButton#CtrlButton { color: #ff3b30; }
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())