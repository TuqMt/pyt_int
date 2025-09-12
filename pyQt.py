import sys
import re
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPlainTextEdit, QTextEdit, QFileDialog, QVBoxLayout, QWidget, QSplitter,
    QToolButton, QHBoxLayout, QFrame, QMenu, QCompleter, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QRect, QSize
from PyQt5.QtGui import QKeySequence, QIcon, QColor, QTextCharFormat, QFont, QSyntaxHighlighter, QPainter, QTextFormat
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtCore import QProcess
from PyQt5.QtWidgets import QLineEdit

class Worker(QObject):
    output_ready = pyqtSignal(str)
    input_request = pyqtSignal(str)
    process_finished = pyqtSignal()

    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath
        self.proc = None

    def run(self):
        try:
            self.proc = subprocess.Popen(
                [sys.executable, self.filepath],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # Читаем построчно, чтобы ловить запросы input()
            while True:
                line = self.proc.stdout.readline()
                if not line and self.proc.poll() is not None:
                    break
                if line.strip().endswith(":") and "input" in line.lower():
                    # Когда встречаем что-то вроде 'Введите число:'
                    self.input_request.emit(line)
                else:
                    self.output_ready.emit(line)

            # Читаем ошибки
            err = self.proc.stderr.read()
            if err:
                self.output_ready.emit(err)

            self.process_finished.emit()

        except Exception as e:
            self.output_ready.emit(f"Ошибка запуска: {e}")

    def send_input(self, text):
        if self.proc and self.proc.stdin:
            self.proc.stdin.write(text + "\n")
            self.proc.stdin.flush()


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        def make_format(color, bold=False, italic=False):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if bold:
                fmt.setFontWeight(QFont.Bold)
            if italic:
                fmt.setFontItalic(True)
            return fmt

        kw_format = make_format("#569CD6", bold=True)
        type_format = make_format("#4EC9B0")
        builtin_format = make_format("#C586C0")
        comment_format = make_format("#6A9955", italic=True)
        string_format = make_format("#D69D85")

        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def",
            "del", "elif", "else", "except", "False", "finally", "for",
            "from", "global", "if", "import", "in", "is", "lambda", "None",
            "nonlocal", "not", "or", "pass", "raise", "return", "True",
            "try", "while", "with", "yield"
        ]
        self.rules.append((re.compile(r'\b(' + '|'.join(keywords) + r')\b'), kw_format))

        types = ["int", "str", "float", "list", "dict", "set", "tuple", "object", "bool"]
        self.rules.append((re.compile(r'\b(' + '|'.join(types) + r')\b'), type_format))

        builtins = ["print", "len", "range", "open", "input", "type", "isinstance", "enumerate", "sum", "min", "max"]
        self.rules.append((re.compile(r'\b(' + '|'.join(builtins) + r')\b'), builtin_format))

        self.rules.append((re.compile(r'(\"[^"\\]*(\\.[^"\\]*)*\"|\'.*?\')'), string_format))
        self.rules.append((re.compile(r'#.*'), comment_format))

    def highlightBlock(self, text: str):
        for pattern, fmt in self.rules:
            for m in pattern.finditer(text):
                start, end = m.span()
                if start >= 0:
                    self.setFormat(start, end - start, fmt)


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self._editor.lineNumberAreaPaintEvent(event)


class CodeEditorWidget(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = LineNumberArea(self)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self.setFont(QFont("Consolas", 10))
        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()

        words = [
            "and", "as", "assert", "break", "class", "continue", "def",
            "del", "elif", "else", "except", "False", "finally", "for",
            "from", "global", "if", "import", "in", "is", "lambda", "None",
            "nonlocal", "not", "or", "pass", "raise", "return", "True",
            "try", "while", "with", "yield",
            "int", "str", "float", "list", "dict", "set", "tuple", "object", "bool",
            "print", "len", "range", "open", "input", "type", "isinstance", "enumerate", "sum", "min", "max"
        ]
        self.completer = QCompleter(words, self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setWidget(self)
        self.completer.activated.connect(self.insertCompletion)

    def insertCompletion(self, completion):
        cursor = self.textCursor()
        cursor.movePosition(cursor.Left, cursor.KeepAnchor, len(self.completer.completionPrefix()))
        cursor.insertText(completion)
        self.setTextCursor(cursor)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab:
            prefix = self.textUnderCursor()
            if prefix and len(prefix) > 1:
                self.completer.setCompletionPrefix(prefix)
                matches = self.completer.model().match(
                    self.completer.model().index(0, 0),
                    Qt.DisplayRole,
                    prefix,
                    -1,
                    Qt.MatchStartsWith
                )
                if matches:
                    self.insertCompletion(matches[0].data())
                    return
        super().keyPressEvent(event)

    def textUnderCursor(self):
        cursor = self.textCursor()
        cursor.select(cursor.WordUnderCursor)
        return cursor.selectedText()

    def lineNumberAreaWidth(self):
        digits = len(str(max(1, self.blockCount())))
        space = 4 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#252526"))

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        font_color = QColor("#888888")
        fm = self.fontMetrics()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(font_color)
                painter.drawText(0, top, self.lineNumberArea.width() - 6, fm.height(),
                                 Qt.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            blockNumber += 1

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor("#2a2a2a")
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)


class CodeEditor(QMainWindow):
    def __init__(self):
        self.proc = None
        self.input_line = QLineEdit()


        super().__init__()
        self.setWindowTitle("PyQt5 Code Editor")
        app.setStyleSheet("""
            QMainWindow {
                background-color: #252526;
            }
            QSplitter::handle {
                background-color: #252526;
            }
            QWidget {
                background-color: #252526;
                color: #ffffff;
            }
            QMenuBar, QMenu {
                background-color: #252526;
                color: #ffffff;
            }
            QMenu::item:selected {  
                background-color: #222222;
            }
        """)

        self.setGeometry(200, 200, 1000, 600)
        self.filepath = None

        central = QWidget()
        main_layout = QHBoxLayout(central)

        sidebar = QFrame()
        sidebar.setFixedWidth(90)
        sidebar.setStyleSheet("background-color: #252526;")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(5, 5, 5, 5)
        side_layout.setSpacing(12)

        def add_menu_button(icon, text, menu):
            btn = QToolButton()
            btn.setIcon(QIcon.fromTheme(icon))
            btn.setText(text)
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setMenu(menu)
            btn.setPopupMode(QToolButton.InstantPopup)
            btn.setStyleSheet("color: white;")
            side_layout.addWidget(btn)
            return btn

        def add_button(icon, text, callback):
            btn = QToolButton()
            btn.setIcon(QIcon.fromTheme(icon))
            btn.setText(text)
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setStyleSheet("color: white;")
            btn.clicked.connect(callback)
            side_layout.addWidget(btn)
            return btn
        
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Введите данные для input() и нажмите Enter")
        self.input_edit.returnPressed.connect(self.send_input_to_script)
        self.input_edit.hide()  # скрываем, пока не понадобится
        main_layout.addWidget(self.input_edit)

        file_menu = QMenu()
        file_menu.addAction("Открыть (Ctrl+O)", self.open_file)
        file_menu.addAction("Сохранить (Ctrl+S)", self.save_file)
        add_menu_button("document-open", "Файл    ", file_menu)

        edit_menu = QMenu()
        edit_menu.addAction("Выделить всё (Ctrl+A)", lambda: self.text_edit.selectAll())
        edit_menu.addAction("Вырезать (Ctrl+X)", lambda: self.text_edit.cut())
        edit_menu.addAction("Копировать (Ctrl+C)", lambda: self.text_edit.copy())
        edit_menu.addAction("Вставить (Ctrl+V)", lambda: self.text_edit.paste())
        add_menu_button("edit-copy", "Правка  ", edit_menu)

        add_button("system-run", "Запуск  ", self.run_script)
        side_layout.addStretch(1)

        splitter = QSplitter(Qt.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background-color: #252526; }")

        self.text_edit = CodeEditorWidget()
        PythonHighlighter(self.text_edit.document())
        self.text_edit.setStyleSheet("background: #1e1e1e; color: #d4d4d4;")
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setStyleSheet("background: #1e1e1e; color: #0f0; font-family: Consolas;")

        splitter.addWidget(self.text_edit)
        splitter.addWidget(self.output_edit)
        splitter.setSizes([400, 200])
        splitter.addWidget(self.text_edit)
        splitter.addWidget(self.output_edit)
        splitter.addWidget(self.input_line)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(splitter)
        self.setCentralWidget(central)
        
        self.input_line.setPlaceholderText("Введите данные для input() и Enter")
        self.input_line.returnPressed.connect(self.send_input)

        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.open_file)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_file)
        QShortcut(QKeySequence("F5"), self).activated.connect(self.run_script)
        QShortcut(QKeySequence("Ctrl+A"), self).activated.connect(self.text_edit.selectAll)
        QShortcut(QKeySequence("Ctrl+X"), self).activated.connect(self.text_edit.cut)
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(self.text_edit.copy)
        QShortcut(QKeySequence("Ctrl+V"), self).activated.connect(self.text_edit.paste)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Открыть файл", "", "Python Files (*.py);;Text Files (*.txt);;All Files (*)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.text_edit.setPlainText(f.read())
            self.filepath = path
            self.setWindowTitle(f"{path} - PyQt5 Code Editor")

    def save_file(self):
        if not self.filepath:
            path, _ = QFileDialog.getSaveFileName(self, "Сохранить файл", "", "Python Files (*.py);;Text Files (*.txt);;All Files (*)")
            if not path:
                return
            self.filepath = path
        with open(self.filepath, "w", encoding="utf-8") as f:
            f.write(self.text_edit.toPlainText())
        self.setWindowTitle(f"{self.filepath} - PyQt5 Code Editor")

    def run_script(self):



        if hasattr(self, "process") and self.process:
            self.process.kill()

        self.process = QProcess()
        self.process.setProgram(sys.executable)
        self.process.setArguments([self.filepath])
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(self.read_output)
        self.process.start()

        self.save_file()
        if not self.filepath:
            return

        self.output_edit.clear()

        self.proc = subprocess.Popen(
            [sys.executable, "-u", self.filepath],  # -u = без буфера
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        self.output_edit.append("=== Скрипт запущен ===\n")
        self.output_edit.setReadOnly(False)  # разрешаем писать в консоль

        from threading import Thread
        def read_output():
            for line in self.proc.stdout:
                self.output_edit.moveCursor(self.output_edit.textCursor().End)
                self.output_edit.insertPlainText(line)
                self.output_edit.moveCursor(self.output_edit.textCursor().End)

            self.output_edit.append("\n=== Скрипт завершён ===")
            self.proc = None
            self.output_edit.setReadOnly(True)

        Thread(target=read_output, daemon=True).start()

    def show_output(self, text):
        self.output_edit.append(text)

    def show_input_field(self, prompt):
        self.output_edit.append(prompt)
        self.input_edit.show()
        self.input_edit.setFocus()

    def send_input_to_script(self):
        text = self.input_edit.text()
        self.input_edit.clear()
        self.input_edit.hide()
        self.worker.send_input(text)

    def script_finished(self):
        self.output_edit.append("\n--- Процесс завершён ---")

    def keyPressEvent(self, event):
        if self.proc and event.key() == Qt.Key_Return:
            cursor = self.output_edit.textCursor()
            cursor.movePosition(cursor.End)
            self.output_edit.setTextCursor(cursor)

            text = self.output_edit.toPlainText().splitlines()[-1]  # берём последнюю строку
            self.proc.stdin.write(text + "\n")
            self.proc.stdin.flush()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if hasattr(self, "thread") and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()
        event.accept()
    def read_output(self):
        data = self.process.readAllStandardOutput().data().decode("utf-8")
        self.output_edit.moveCursor(self.output_edit.textCursor().End)  
        self.output_edit.insertPlainText(data)

    def send_input(self):
        text = self.input_line.text() + "\n"
        self.process.write(text.encode("utf-8"))
        self.input_line.clear()



if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = CodeEditor()
    editor.show()
    sys.exit(app.exec_())
