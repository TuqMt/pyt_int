import sys
import subprocess
import threading
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QAction, QFileDialog, QVBoxLayout, QWidget, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject


class Worker(QObject):
    output_ready = pyqtSignal(str)

    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath

    def run(self):
        try:
            proc = subprocess.Popen(
                [sys.executable, self.filepath],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            out, err = proc.communicate()
            output = out + ("\n" + err if err else "")
            self.output_ready.emit(output if output.strip() else "Нет вывода")
        except Exception as e:
            self.output_ready.emit(f"Ошибка запуска: {e}")


class CodeEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt5 Code Editor")
        self.setGeometry(200, 200, 900, 600)

        self.filepath = None

        
        central = QWidget()
        layout = QVBoxLayout(central)

        splitter = QSplitter(Qt.Vertical)

        self.text_edit = QTextEdit()
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setStyleSheet("background: #222; color: #0f0;")

        splitter.addWidget(self.text_edit)
        splitter.addWidget(self.output_edit)
        splitter.setSizes([400, 200])

        layout.addWidget(splitter)
        self.setCentralWidget(central)

        
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Файл")
        run_menu = menubar.addMenu("Запуск")
        edit_menu = menubar.addMenu("Правка")

  
        open_action = QAction("Открыть", self)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        save_action = QAction("Сохранить", self)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

     
        run_action = QAction("Запустить", self)
        run_action.triggered.connect(self.run_script)
        run_menu.addAction(run_action)

        select_all_action = QAction("Выделить всё", self)
        select_all_action.triggered.connect(self.text_edit.selectAll)
        edit_menu.addAction(select_all_action)

        cut_action = QAction("Вырезать", self)
        cut_action.triggered.connect(self.text_edit.cut)
        edit_menu.addAction(cut_action)

        copy_action = QAction("Копировать", self)
        copy_action.triggered.connect(self.text_edit.copy)
        edit_menu.addAction(copy_action)

        paste_action = QAction("Вставить", self)
        paste_action.triggered.connect(self.text_edit.paste)
        edit_menu.addAction(paste_action)

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
        self.save_file()
        if not self.filepath:
            return

        self.output_edit.clear()

        self.worker = Worker(self.filepath)
        self.worker.output_ready.connect(self.show_output)

        thread = threading.Thread(target=self.worker.run, daemon=True)
        thread.start()

    def show_output(self, text):
        self.output_edit.setPlainText(text)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = CodeEditor()
    editor.show()
    sys.exit(app.exec_())
